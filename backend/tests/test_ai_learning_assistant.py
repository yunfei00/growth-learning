"""Phase 13 AI helpers remain auxiliary to canonical learning evidence."""

import uuid

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1.learning import get_learning_ai_provider
from app.integrations.ai.fake import FakeAIProvider
from app.models import ChildKnowledgeState, LearningRecord
from app.schemas.knowledge import CharacterCreate
from app.services.character_catalog import create_character

pytestmark = pytest.mark.anyio


async def test_character_ai_explanation_does_not_modify_mastery_or_learning_records(
    client: httpx.AsyncClient,
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    email = f"ai-helper-{uuid.uuid4().hex}@example.com"
    password = "ai-helper-test-password"
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": "AI 测试家长", "password": password},
    )
    assert registered.status_code == 201
    assert (
        await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    ).status_code == 200
    family = await client.post("/api/v1/families", json={"name": "AI 学习助手家庭"})
    child = await client.post(
        f"/api/v1/families/{family.json()['id']}/children",
        json={"display_name": "小学习者", "birth_date": "2020-06-01"},
    )
    assert child.status_code == 201

    async with session_factory() as session:
        point, _ = await create_character(
            session,
            CharacterCreate(
                character="日",
                pinyin="rì",
                simple_meaning="太阳；一天。",
                common_words=["日出", "生日"],
                example_sentence="太阳出来了。",
                parent_tip="指着太阳帮助孩子理解。",
            ),
        )
        point_id = point.id

    fake = FakeAIProvider(
        [
            """{"simple_explanation":"太阳，也可以表示一天。","words":["日出","生日","日光"],"example_sentence":"红日慢慢升起来了。","parent_tip":"早晨看太阳时，指一指天空，再一起找‘日’字。"}"""
        ]
    )
    test_app.dependency_overrides[get_learning_ai_provider] = lambda: fake
    test_app.state.settings.ai_provider = "openai_compatible"
    test_app.state.settings.ai_api_key = SecretStr("test-ai-key")
    test_app.state.settings.ai_model = "test-model"

    async with session_factory() as session:
        records_before = int(
            await session.scalar(select(func.count()).select_from(LearningRecord)) or 0
        )
        states_before = int(
            await session.scalar(select(func.count()).select_from(ChildKnowledgeState)) or 0
        )

    response = await client.post(
        f"/api/v1/children/{child.json()['id']}/characters/{point_id}/ai-assistance"
    )
    assert response.status_code == 200, response.text
    assert response.json()["simple_explanation"].startswith("太阳")
    assert response.json()["words"] == ["日出", "生日", "日光"]
    assert response.json()["mastery_directly_modified"] is False
    assert fake.requests[0].json_response is True

    async with session_factory() as session:
        assert (
            int(await session.scalar(select(func.count()).select_from(LearningRecord)) or 0)
            == records_before
        )
        assert (
            int(await session.scalar(select(func.count()).select_from(ChildKnowledgeState)) or 0)
            == states_before
        )

    test_app.dependency_overrides.pop(get_learning_ai_provider, None)
