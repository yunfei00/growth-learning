"""Parent-authored assisted reading and cached narration tests."""

import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.integrations.tts import dashscope as tts_module
from app.integrations.tts.dashscope import DashScopeTTSProvider
from app.schemas.knowledge import CharacterCreate
from app.services.character_catalog import create_character
from app.services.manual_story import MAX_TTS_PARAGRAPH_CHARS, split_story_paragraphs

pytestmark = pytest.mark.anyio
PASSWORD = "parent-story-tests-password"


async def register_and_login(client: httpx.AsyncClient, email: str) -> dict:
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": "故事家长", "password": PASSWORD},
    )
    assert registered.status_code == 201
    assert (
        await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    ).status_code == 200
    return registered.json()


async def create_household(client: httpx.AsyncClient) -> dict:
    family = (await client.post("/api/v1/families", json={"name": "辅助阅读家庭"})).json()
    child_response = await client.post(
        f"/api/v1/families/{family['id']}/children",
        json={"display_name": "小读者", "birth_date": "2021-06-26"},
    )
    assert child_response.status_code == 201
    return child_response.json()


def test_pasted_story_is_chunked_for_tts_without_changing_order() -> None:
    text = "春" * (MAX_TTS_PARAGRAPH_CHARS + 35)
    paragraphs = split_story_paragraphs(text)
    assert "".join(paragraphs) == text
    assert len(paragraphs) == 2
    assert all(len(item) <= MAX_TTS_PARAGRAPH_CHARS for item in paragraphs)


async def test_parent_can_save_story_without_any_mastery_gate(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await register_and_login(client, "parent-manual-story@example.com")
    child = await create_household(client)
    async with session_factory() as session:
        for character, pinyin in [("春", "chūn"), ("天", "tiān"), ("花", "huā")]:
            await create_character(
                session,
                CharacterCreate(
                    character=character,
                    pinyin=pinyin,
                    common_words=[f"{character}天"],
                    simple_meaning=f"{character}的简单解释",
                ),
            )
        await session.commit()

    response = await client.post(
        f"/api/v1/children/{child['id']}/stories/manual",
        json={"title": "春天", "content": "春天来了。\n花开了。"},
    )
    assert response.status_code == 201
    payload = response.json()
    version = payload["version"]
    assert version["provider"] == "parent_manual"
    assert version["model"] == "parent-authored"
    assert version["target_characters"] == []
    assert version["actual_usable_known_coverage"] == 0
    assert {item["character"] for item in version["glossary"]} >= {"春", "天", "花"}

    start = await client.post(
        f"/api/v1/children/{child['id']}/story-versions/{version['id']}/reading/start",
        json={"reading_mode": "with_help"},
    )
    assert start.status_code == 200
    reading = start.json()
    finish = await client.post(
        f"/api/v1/children/{child['id']}/reading-sessions/{reading['id']}/complete",
        json={},
    )
    assert finish.status_code == 200
    assert finish.json()["story_exposure_count"] == 0


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        *,
        body: dict | None = None,
        content: bytes = b"",
        content_type: str = "audio/wav",
    ) -> None:
        self.status_code = status_code
        self._body = body
        self.content = content
        self.headers = {"content-type": content_type}

    def json(self) -> dict:
        if self._body is None:
            raise ValueError("not json")
        return self._body


class FakeAsyncClient:
    def __init__(self, captured: dict, **_kwargs) -> None:
        self.captured = captured

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args) -> None:
        return None

    async def post(self, url: str, *, headers: dict, json: dict) -> FakeResponse:
        self.captured.update({"url": url, "headers": headers, "json": json})
        return FakeResponse(
            200,
            body={
                "request_id": "tts-request-1",
                "output": {"audio": {"url": "https://audio.example/story.wav"}},
                "usage": {"characters": 6},
            },
        )

    async def get(self, url: str) -> FakeResponse:
        self.captured["audio_url"] = url
        return FakeResponse(200, content=b"RIFFfake-wav")


async def test_dashscope_tts_downloads_ephemeral_audio_for_private_cache(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        tts_module.httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(captured, **kwargs),
    )
    provider = DashScopeTTSProvider(
        api_key="server-secret",
        base_url="https://workspace.example/generation",
        model="qwen3-tts-flash",
        voice="Cherry",
    )

    result = await provider.synthesize("春天来了。")

    assert result.audio == b"RIFFfake-wav"
    assert result.request_id == "tts-request-1"
    assert captured["json"] == {
        "model": "qwen3-tts-flash",
        "input": {"text": "春天来了。", "voice": "Cherry", "language_type": "Chinese"},
    }
    assert captured["audio_url"] == "https://audio.example/story.wav"
    assert "server-secret" not in str(captured["json"])
