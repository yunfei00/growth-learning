"""DashScope short-audio ASR adapter tests."""

import json

import pytest

from app.integrations.asr import ASRNoSpeechError, DashScopeASRProvider
from app.integrations.asr import dashscope as dashscope_module

pytestmark = pytest.mark.anyio


class FakeResponse:
    def __init__(self, status_code: int, body: dict) -> None:
        self.status_code = status_code
        self._body = body

    def json(self) -> dict:
        return self._body


class FakeAsyncClient:
    def __init__(self, response: FakeResponse, captured: dict, **_kwargs) -> None:
        self.response = response
        self.captured = captured

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args) -> None:
        return None

    async def post(self, url: str, *, headers: dict, json: dict):
        self.captured.update({"url": url, "headers": headers, "json": json})
        return self.response


async def test_dashscope_transcription_uses_audio_only_without_answer_bias(monkeypatch) -> None:
    captured: dict = {}
    response = FakeResponse(
        200,
        {
            "output": {"text": "冬"},
            "usage": {"duration": 1.4},
            "request_id": "request-test-1",
        },
    )
    monkeypatch.setattr(
        dashscope_module.httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(response, captured, **kwargs),
    )
    provider = DashScopeASRProvider(api_key="test-secret", model="qwen-audio-3.0-asr-flash")

    result = await provider.transcribe(b"short-webm-audio", "audio/webm;codecs=opus")

    assert result.transcript == "冬"
    assert result.provider == "dashscope_qwen_audio_asr"
    assert result.request_id == "request-test-1"
    assert result.usage_duration_seconds == 1.4
    body = captured["json"]
    assert body["model"] == "qwen-audio-3.0-asr-flash"
    assert body["parameters"] == {"format": "webm", "language_hints": ["zh"]}
    data_uri = body["input"]["messages"][0]["content"][0]["input_audio"]["data"]
    assert data_uri.startswith("data:audio/webm;base64,")
    # The ASR adapter has no target-character/pinyin input at all. In particular,
    # it must never inject the expected answer into context or hotwords.
    serialized = json.dumps(body, ensure_ascii=False)
    assert "vocabulary" not in serialized
    assert "input_text" not in serialized
    assert "东" not in serialized


async def test_dashscope_empty_transcript_is_technical_no_speech(monkeypatch) -> None:
    captured: dict = {}
    response = FakeResponse(200, {"output": {"text": ""}, "request_id": "empty"})
    monkeypatch.setattr(
        dashscope_module.httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(response, captured, **kwargs),
    )
    provider = DashScopeASRProvider(api_key="test-secret")

    with pytest.raises(ASRNoSpeechError):
        await provider.transcribe(b"silence", "audio/wav")
