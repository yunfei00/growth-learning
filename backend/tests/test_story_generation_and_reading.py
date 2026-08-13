"""Structured generation, immutable storybook, reading evidence, and privacy tests."""

import json
import uuid

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1.stories import get_story_ai_provider
from app.integrations.ai.fake import FakeAIProvider
from app.models import (
    AssessmentItem,
    Child,
    ChildKnowledgeState,
    DailyReadingTask,
    FamilyMember,
    FamilyRole,
    LearningActivityType,
    LearningRecord,
    MasteryLevel,
    ReadingQuestion,
    StoryGenerationRun,
    StoryGenerationStatus,
    StoryVersion,
    SystemRole,
    User,
)
from app.schemas.knowledge import CharacterCreate
from app.schemas.story import (
    ReadingAnswerInput,
    ReadingAnswersSubmit,
    ReadingCompleteRequest,
    ReadingSessionStart,
    StoryGenerationRequest,
)
from app.services.character_catalog import create_character
from app.services.review_planning import get_or_create_daily_plan
from app.services.story_generation import StoryGenerationError, generate_story
from app.services.story_reading import (
    complete_reading,
    start_or_resume_reading,
    submit_reading_answers,
)

pytestmark = pytest.mark.anyio
PASSWORD = "story-tests-only-password"
CATALOG = list(
    "".join(
        [
            "人大小上下日月水火山木田土子女天中文手口目耳足雨风云",
            "花草鸟鱼牛马门车路家白红见来去河船",
        ]
    )
)


async def register_and_login(client: httpx.AsyncClient, email: str) -> dict:
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": "测试家长", "password": PASSWORD},
    )
    assert registered.status_code == 201
    assert (
        await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    ).status_code == 200
    return registered.json()


async def create_household(client: httpx.AsyncClient) -> tuple[dict, dict]:
    family = (await client.post("/api/v1/families", json={"name": "故事家庭"})).json()
    child_response = await client.post(
        f"/api/v1/families/{family['id']}/children",
        json={"display_name": "小读者", "birth_date": "2020-05-01"},
    )
    assert child_response.status_code == 201
    return family, child_response.json()


async def seed_mastery_catalog(
    session_factory: async_sessionmaker[AsyncSession], child_id: str
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    point_ids: list[uuid.UUID] = []
    async with session_factory() as session:
        for character in CATALOG:
            point, _ = await create_character(
                session,
                CharacterCreate(
                    character=character,
                    pinyin="test",
                    common_words=[f"{character}字"],
                    simple_meaning=f"{character}的简单解释",
                ),
            )
            point_ids.append(point.id)
        for index, point_id in enumerate(point_ids):
            session.add(
                ChildKnowledgeState(
                    child_id=uuid.UUID(child_id),
                    knowledge_point_id=point_id,
                    mastery_level=(
                        MasteryLevel.PROFICIENT
                        if index < len(CATALOG) - 2
                        else MasteryLevel.RECOGNIZING
                    ),
                    mastery_score=0.75 if index < len(CATALOG) - 2 else 0.25,
                    is_priority=index >= len(CATALOG) - 2,
                    incorrect_count=1 if index >= len(CATALOG) - 2 else 0,
                )
            )
        await session.commit()
    return point_ids[:-2], point_ids[-2:]


def valid_story_json(known_characters: list[str], targets: list[str]) -> str:
    # Title + body = 36 known and 4 target occurrences: 90% / 10%, 38 unique.
    body = "".join(known_characters[:35]) + targets[0] + targets[1] + targets[0]
    return json.dumps(
        {
            "title": known_characters[35] + targets[1],
            "paragraphs": [body],
            "summary": "家长陪读的安全故事",
            "questions": [
                {
                    "question": "故事里出现了什么？",
                    "options": ["河", "星", "雪"],
                    "correct_option_index": 0,
                },
                {
                    "question": "故事适合怎样阅读？",
                    "options": ["家长陪读", "不读", "跳过"],
                    "correct_option_index": 0,
                },
            ],
        },
        ensure_ascii=False,
    )


def invalid_story_json() -> str:
    return json.dumps(
        {
            "title": "鬼怪",
            "paragraphs": ["鬼" * 60],
            "questions": [
                {"question": "谁？", "options": ["鬼", "人"], "correct_option_index": 0},
                {"question": "哪？", "options": ["鬼", "山"], "correct_option_index": 0},
            ],
        },
        ensure_ascii=False,
    )


async def load_child_and_user(
    session_factory: async_sessionmaker[AsyncSession], child_id: str, user_id: str
) -> tuple[Child, User]:
    async with session_factory() as session:
        child = await session.get(Child, uuid.UUID(child_id))
        user = await session.get(User, uuid.UUID(user_id))
        assert child is not None and user is not None
        return child, user


async def test_fake_provider_repair_then_success_and_snapshot_immutability(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user = await register_and_login(client, "story-pipeline@example.com")
    _, child_payload = await create_household(client)
    strong_ids, target_ids = await seed_mastery_catalog(session_factory, child_payload["id"])
    child, _ = await load_child_and_user(session_factory, child_payload["id"], user["id"])
    provider = FakeAIProvider([invalid_story_json(), valid_story_json(CATALOG[:-2], CATALOG[-2:])])

    async with session_factory() as session:
        run, version = await generate_story(
            session,
            child=child,
            requested_by_user_id=uuid.UUID(user["id"]),
            payload=StoryGenerationRequest(
                difficulty="normal",
                theme="animals",
                target_knowledge_point_ids=target_ids,
                request_key="repair-success-request",
            ),
            provider=provider,
            provider_name="fake",
            configured_model="deterministic-test-model",
        )
        assert run.attempt_count == 2
        assert version.actual_usable_known_coverage == 0.9
        assert version.actual_target_coverage == 0.1
        snapshot_before = version.mastery_snapshot
        title_before = version.title
        version_id = version.id
        story_id = version.story_id

    assert len(provider.requests) == 2
    assert provider.requests[0].json_response is True
    prompt = provider.requests[0].messages[-1].content
    assert child_payload["display_name"] not in prompt
    assert "story-pipeline@example.com" not in prompt
    assert "birth_date" not in prompt

    async with session_factory() as session:
        state = await session.scalar(
            select(ChildKnowledgeState).where(
                ChildKnowledgeState.child_id == uuid.UUID(child_payload["id"]),
                ChildKnowledgeState.knowledge_point_id == strong_ids[0],
            )
        )
        assert state is not None
        state.mastery_level = MasteryLevel.UNLEARNED
        await session.commit()
        old_version = await session.get(StoryVersion, version_id)
        assert old_version is not None
        assert old_version.mastery_snapshot == snapshot_before

        second_provider = FakeAIProvider([valid_story_json(CATALOG[:-2], CATALOG[-2:])])
        _, second_version = await generate_story(
            session,
            child=child,
            requested_by_user_id=uuid.UUID(user["id"]),
            payload=StoryGenerationRequest(
                difficulty="normal",
                theme="nature",
                target_knowledge_point_ids=target_ids,
                story_id=story_id,
            ),
            provider=second_provider,
            provider_name="fake",
            configured_model="deterministic-test-model",
        )
        assert second_version.version_number == 2
        old_version = await session.get(StoryVersion, version_id)
        assert old_version is not None
        assert old_version.version_number == 1
        assert old_version.title == title_before


async def test_generation_stops_after_three_invalid_attempts(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user = await register_and_login(client, "story-max-retry@example.com")
    _, child_payload = await create_household(client)
    _, target_ids = await seed_mastery_catalog(session_factory, child_payload["id"])
    child, _ = await load_child_and_user(session_factory, child_payload["id"], user["id"])
    provider = FakeAIProvider([invalid_story_json()] * 3)
    async with session_factory() as session:
        with pytest.raises(StoryGenerationError, match="有限重试") as error:
            await generate_story(
                session,
                child=child,
                requested_by_user_id=uuid.UUID(user["id"]),
                payload=StoryGenerationRequest(
                    difficulty="normal",
                    theme="space",
                    target_knowledge_point_ids=target_ids,
                ),
                provider=provider,
                provider_name="fake",
                configured_model="deterministic-test-model",
            )
        assert error.value.category == "validation_failed"
        run = await session.scalar(select(StoryGenerationRun))
        assert run is not None
        assert run.status == StoryGenerationStatus.FAILED
        assert run.attempt_count == 3
    assert len(provider.requests) == 3


async def test_reading_resume_comprehension_exposure_and_daily_task(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user = await register_and_login(client, "reading-evidence@example.com")
    _, child_payload = await create_household(client)
    _, target_ids = await seed_mastery_catalog(session_factory, child_payload["id"])
    child, _ = await load_child_and_user(session_factory, child_payload["id"], user["id"])

    async with session_factory() as session:
        plan = await get_or_create_daily_plan(session, child.id)
        assert plan.reading.status == "needs_story"
        _, version = await generate_story(
            session,
            child=child,
            requested_by_user_id=uuid.UUID(user["id"]),
            payload=StoryGenerationRequest(
                difficulty="normal",
                theme="science",
                target_knowledge_point_ids=target_ids,
            ),
            provider=FakeAIProvider([valid_story_json(CATALOG[:-2], CATALOG[-2:])]),
            provider_name="fake",
            configured_model="deterministic-test-model",
        )
        task = await session.scalar(select(DailyReadingTask))
        assert task is not None and task.status == "pending"

        started = await start_or_resume_reading(
            session,
            child_id=child.id,
            story_version_id=version.id,
            evaluator_user_id=uuid.UUID(user["id"]),
            payload=ReadingSessionStart(reading_mode="with_help"),
        )
        resumed = await start_or_resume_reading(
            session,
            child_id=child.id,
            story_version_id=version.id,
            evaluator_user_id=uuid.UUID(user["id"]),
            payload=ReadingSessionStart(reading_mode="with_help"),
        )
        assert resumed.id == started.id
        task = await session.scalar(select(DailyReadingTask))
        assert task is not None and task.status == "in_progress"

        persisted_questions = list(
            (
                await session.scalars(
                    select(ReadingQuestion)
                    .where(ReadingQuestion.story_version_id == version.id)
                    .order_by(ReadingQuestion.position)
                )
            ).all()
        )
        answered = await submit_reading_answers(
            session,
            child_id=child.id,
            reading_session_id=started.id,
            evaluator_user_id=uuid.UUID(user["id"]),
            payload=ReadingAnswersSubmit(
                answers=[
                    ReadingAnswerInput(
                        question_id=question.id,
                        selected_option_index=question.correct_option_index,
                        outcome="correct",
                    )
                    for question in persisted_questions
                ]
            ),
        )
        assert len(answered.answers) == 2
        assessments_before = int(
            await session.scalar(select(func.count()).select_from(AssessmentItem)) or 0
        )
        completed = await complete_reading(
            session,
            child_id=child.id,
            reading_session_id=started.id,
            evaluator_user_id=uuid.UUID(user["id"]),
            payload=ReadingCompleteRequest(duration_seconds=180, parent_note="一起读完"),
        )
        completed_again = await complete_reading(
            session,
            child_id=child.id,
            reading_session_id=started.id,
            evaluator_user_id=uuid.UUID(user["id"]),
            payload=ReadingCompleteRequest(duration_seconds=999),
        )
        assert completed.status == "completed"
        assert completed_again.id == completed.id
        assert completed_again.duration_seconds == 180
        assert completed.story_exposure_count == 2
        assert (
            int(await session.scalar(select(func.count()).select_from(AssessmentItem)) or 0)
            == assessments_before
        )
        exposures = int(
            await session.scalar(
                select(func.count())
                .select_from(LearningRecord)
                .where(LearningRecord.activity_type == LearningActivityType.STORY_EXPOSURE)
            )
            or 0
        )
        assert exposures == 2
        task = await session.scalar(select(DailyReadingTask))
        assert task is not None and task.status == "completed"


async def test_provider_disabled_and_household_story_privacy(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as owner,
        httpx.AsyncClient(transport=transport, base_url="http://test") as companion,
        httpx.AsyncClient(transport=transport, base_url="http://test") as outsider,
    ):
        owner_user = await register_and_login(owner, "story-owner@example.com")
        family, child_payload = await create_household(owner)
        _, target_ids = await seed_mastery_catalog(session_factory, child_payload["id"])
        companion_user = await register_and_login(companion, "story-companion@example.com")
        outsider_user = await register_and_login(outsider, "story-system-admin@example.com")
        async with session_factory() as session:
            session.add(
                FamilyMember(
                    family_id=uuid.UUID(family["id"]),
                    user_id=uuid.UUID(companion_user["id"]),
                    role=FamilyRole.COMPANION,
                )
            )
            system_admin = await session.get(User, uuid.UUID(outsider_user["id"]))
            assert system_admin is not None
            system_admin.system_role = SystemRole.ADMIN
            await session.commit()

        context = await owner.get(f"/api/v1/children/{child_payload['id']}/reading-context")
        assert context.status_code == 200
        assert context.json()["provider_configured"] is False
        disabled = await owner.post(
            f"/api/v1/children/{child_payload['id']}/stories/generate",
            json={
                "difficulty": "normal",
                "theme": "animals",
                "target_knowledge_point_ids": [str(point_id) for point_id in target_ids],
            },
        )
        assert disabled.status_code == 503
        assert disabled.json()["detail"] == "AI 服务尚未配置"

        test_app.state.settings.ai_provider = "openai_compatible"
        test_app.state.settings.ai_api_key = SecretStr("test-only-key")
        test_app.state.settings.ai_model = "deterministic-test-model"
        fake = FakeAIProvider([valid_story_json(CATALOG[:-2], CATALOG[-2:])])
        test_app.dependency_overrides[get_story_ai_provider] = lambda: fake
        generated = await owner.post(
            f"/api/v1/children/{child_payload['id']}/stories/generate",
            json={
                "difficulty": "normal",
                "theme": "animals",
                "target_knowledge_point_ids": [str(point_id) for point_id in target_ids],
            },
        )
        assert generated.status_code == 201, generated.text
        version_id = generated.json()["version"]["id"]
        assert (
            await companion.get(
                f"/api/v1/children/{child_payload['id']}/story-versions/{version_id}"
            )
        ).status_code == 200
        assert (
            await companion.post(
                f"/api/v1/children/{child_payload['id']}/stories/generate",
                json={
                    "difficulty": "normal",
                    "theme": "animals",
                    "target_knowledge_point_ids": [str(point_id) for point_id in target_ids],
                },
            )
        ).status_code == 403
        private_path = f"/api/v1/children/{child_payload['id']}/story-versions/{version_id}"
        assert (await outsider.get(private_path)).status_code == 404
        assert (
            await outsider.get(f"/api/v1/children/{child_payload['id']}/reading-summary")
        ).status_code == 404
        assert owner_user["system_role"] == "user"
