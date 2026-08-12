"""Character evidence, mastery projection, and household privacy tests."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    AssessmentItem,
    AssessmentOutcome,
    AssessmentSession,
    ChildKnowledgeState,
    FamilyMember,
    FamilyRole,
    LearningActivityType,
    LearningRecord,
    LearningSession,
    MasteryLevel,
    SessionStatus,
    SystemRole,
    User,
)
from app.schemas.knowledge import CharacterCreate
from app.services.character_catalog import create_character
from app.services.mastery import recompute_child_states

pytestmark = pytest.mark.anyio
PASSWORD = "local-test-password-only"


async def register_and_login(client: httpx.AsyncClient, email: str) -> dict:
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": "测试家长", "password": PASSWORD},
    )
    assert registered.status_code == 201
    logged_in = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert logged_in.status_code == 200
    return registered.json()


async def create_family_and_child(client: httpx.AsyncClient, suffix: str = "") -> tuple[dict, dict]:
    family_response = await client.post("/api/v1/families", json={"name": f"成长家庭{suffix}"})
    assert family_response.status_code == 201
    family = family_response.json()
    child_response = await client.post(
        f"/api/v1/families/{family['id']}/children",
        json={"display_name": f"小树{suffix}", "birth_date": "2021-03-15"},
    )
    assert child_response.status_code == 201
    return family, child_response.json()


async def seed_character(
    session_factory: async_sessionmaker[AsyncSession], character: str, pinyin: str
) -> str:
    async with session_factory() as session:
        point, _ = await create_character(
            session,
            CharacterCreate(
                character=character,
                pinyin=pinyin,
                common_words=[f"{character}字"],
                simple_meaning="测试释义",
            ),
        )
        return str(point.id)


async def test_learning_and_assessment_create_raw_evidence_and_mastery(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await register_and_login(client, "parent-learning@example.com")
    _, child = await create_family_and_child(client)
    person_id = await seed_character(session_factory, "人", "rén")
    mountain_id = await seed_character(session_factory, "山", "shān")

    summary = await client.get(f"/api/v1/children/{child['id']}/characters/summary")
    assert summary.status_code == 200
    assert summary.json()["unlearned"] == 2

    recommendations = await client.get(
        f"/api/v1/children/{child['id']}/characters/recommendations?mode=new&limit=5"
    )
    assert recommendations.status_code == 200
    assert [item["character"] for item in recommendations.json()] == ["人", "山"]

    learning = await client.post(
        f"/api/v1/children/{child['id']}/learning-sessions",
        json={
            "status": "completed",
            "items": [
                {"knowledge_point_id": person_id, "activity_type": "introduced"},
                {"knowledge_point_id": mountain_id, "activity_type": "introduced"},
            ],
        },
    )
    assert learning.status_code == 201
    assert learning.json()["item_count"] == 2

    assessment = await client.post(
        f"/api/v1/children/{child['id']}/assessment-sessions",
        json={
            "items": [
                {
                    "knowledge_point_id": person_id,
                    "outcome": "correct",
                    "response_time_ms": 1250,
                },
                {
                    "knowledge_point_id": mountain_id,
                    "outcome": "hinted_correct",
                    "response_time_ms": 2600,
                },
            ]
        },
    )
    assert assessment.status_code == 201

    person_detail = await client.get(f"/api/v1/children/{child['id']}/characters/{person_id}")
    assert person_detail.status_code == 200
    assert person_detail.json()["state"]["mastery_level"] == "recognizing"
    assert person_detail.json()["state"]["correct_count"] == 1
    assert person_detail.json()["state"]["average_response_time_ms"] == 1250
    assert [item["evidence_type"] for item in person_detail.json()["timeline"]] == [
        "assessment",
        "learning",
    ]

    summary = await client.get(f"/api/v1/children/{child['id']}/characters/summary")
    assert summary.json() == {
        "total_enabled": 2,
        "unlearned": 0,
        "introduced": 1,
        "recognizing": 1,
        "proficient": 0,
        "stable": 0,
        "priority": 0,
        "learning_records": 2,
        "assessment_items": 2,
    }
    filtered = await client.get(
        f"/api/v1/children/{child['id']}/characters?mastery_level=recognizing"
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["character"] == "人"


async def test_mastery_recompute_is_deterministic_and_preserves_all_evidence(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user = await register_and_login(client, "mastery@example.com")
    _, child_payload = await create_family_and_child(client)
    point_id = uuid.UUID(await seed_character(session_factory, "木", "mù"))
    child_id = uuid.UUID(child_payload["id"])
    user_id = uuid.UUID(user["id"])
    started = datetime(2026, 1, 1, 9, tzinfo=UTC)

    async with session_factory() as session:
        learning_session = LearningSession(
            child_id=child_id,
            actor_user_id=user_id,
            status=SessionStatus.COMPLETED,
            source="test",
            started_at=started,
            completed_at=started,
        )
        session.add(learning_session)
        await session.flush()
        session.add(
            LearningRecord(
                session_id=learning_session.id,
                child_id=child_id,
                knowledge_point_id=point_id,
                actor_user_id=user_id,
                activity_type=LearningActivityType.INTRODUCED,
                source="test",
                learned_at=started,
            )
        )
        for days in (0, 1, 7, 8):
            assessed_at = started + timedelta(days=days)
            assessment_session = AssessmentSession(
                child_id=child_id,
                evaluator_user_id=user_id,
                status=SessionStatus.COMPLETED,
                source="test",
                started_at=assessed_at,
                completed_at=assessed_at,
            )
            session.add(assessment_session)
            await session.flush()
            session.add(
                AssessmentItem(
                    session_id=assessment_session.id,
                    child_id=child_id,
                    knowledge_point_id=point_id,
                    evaluator_user_id=user_id,
                    outcome=AssessmentOutcome.CORRECT,
                    response_time_ms=1000 + days,
                    assessed_at=assessed_at,
                )
            )
        await session.commit()

    async with session_factory() as session:
        assert await recompute_child_states(session, child_id) == 1
        await session.commit()
        state = await session.scalar(select(ChildKnowledgeState))
        assert state is not None
        assert state.mastery_level == MasteryLevel.STABLE
        assert state.correct_count == 4
        assert state.algorithm_version == "v1"
        raw_learning = int(
            await session.scalar(select(func.count()).select_from(LearningRecord)) or 0
        )
        raw_assessments = int(
            await session.scalar(select(func.count()).select_from(AssessmentItem)) or 0
        )

    async with session_factory() as session:
        assert await recompute_child_states(session, child_id) == 1
        await session.commit()
        assert (
            int(await session.scalar(select(func.count()).select_from(LearningRecord)) or 0)
            == raw_learning
        )
        assert (
            int(await session.scalar(select(func.count()).select_from(AssessmentItem)) or 0)
            == raw_assessments
        )

        assessed_at = started + timedelta(days=9)
        wrong_session = AssessmentSession(
            child_id=child_id,
            evaluator_user_id=user_id,
            status=SessionStatus.COMPLETED,
            source="test",
            started_at=assessed_at,
            completed_at=assessed_at,
        )
        session.add(wrong_session)
        await session.flush()
        session.add(
            AssessmentItem(
                session_id=wrong_session.id,
                child_id=child_id,
                knowledge_point_id=point_id,
                evaluator_user_id=user_id,
                outcome=AssessmentOutcome.INCORRECT,
                response_time_ms=1800,
                assessed_at=assessed_at,
            )
        )
        await session.flush()
        assert await recompute_child_states(session, child_id) == 1
        await session.commit()
        state = await session.scalar(select(ChildKnowledgeState))
        assert state is not None
        assert state.mastery_level == MasteryLevel.RECOGNIZING
        assert state.correct_count == 4
        assert state.incorrect_count == 1
        assert state.consecutive_correct == 0
        assert (
            int(await session.scalar(select(func.count()).select_from(ChildKnowledgeState)) or 0)
            == 1
        )


async def test_companion_can_participate_but_cannot_set_priority(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as owner,
        httpx.AsyncClient(transport=transport, base_url="http://test") as companion,
    ):
        await register_and_login(owner, "learning-owner@example.com")
        family, child = await create_family_and_child(owner)
        companion_user = await register_and_login(companion, "learning-companion@example.com")
        point_id = await seed_character(session_factory, "水", "shuǐ")
        async with session_factory() as session:
            session.add(
                FamilyMember(
                    family_id=uuid.UUID(family["id"]),
                    user_id=uuid.UUID(companion_user["id"]),
                    role=FamilyRole.COMPANION,
                )
            )
            await session.commit()

        learning = await companion.post(
            f"/api/v1/children/{child['id']}/learning-sessions",
            json={"items": [{"knowledge_point_id": point_id}]},
        )
        assert learning.status_code == 201
        assessment = await companion.post(
            f"/api/v1/children/{child['id']}/assessment-sessions",
            json={"items": [{"knowledge_point_id": point_id, "outcome": "uncertain"}]},
        )
        assert assessment.status_code == 201
        priority = await companion.patch(
            f"/api/v1/children/{child['id']}/characters/{point_id}/priority",
            json={"is_priority": True},
        )
        assert priority.status_code == 403
        owner_priority = await owner.patch(
            f"/api/v1/children/{child['id']}/characters/{point_id}/priority",
            json={"is_priority": True},
        )
        assert owner_priority.status_code == 200
        assert owner_priority.json()["is_priority"] is True


async def test_cross_family_and_system_admin_without_membership_are_denied(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as owner,
        httpx.AsyncClient(transport=transport, base_url="http://test") as outsider,
    ):
        await register_and_login(owner, "private-owner@example.com")
        _, child = await create_family_and_child(owner)
        point_id = await seed_character(session_factory, "火", "huǒ")
        outsider_user = await register_and_login(outsider, "system-admin-outsider@example.com")
        async with session_factory() as session:
            user = await session.get(User, uuid.UUID(outsider_user["id"]))
            assert user is not None
            user.system_role = SystemRole.ADMIN
            await session.commit()

        paths = [
            f"/api/v1/children/{child['id']}/characters/summary",
            f"/api/v1/children/{child['id']}/characters",
            f"/api/v1/children/{child['id']}/characters/{point_id}",
        ]
        for path in paths:
            assert (await outsider.get(path)).status_code == 404
        assert (
            await outsider.post(
                f"/api/v1/children/{child['id']}/learning-sessions",
                json={"items": [{"knowledge_point_id": point_id}]},
            )
        ).status_code == 404
        assert (
            await outsider.post(
                f"/api/v1/children/{child['id']}/assessment-sessions",
                json={"items": [{"knowledge_point_id": point_id, "outcome": "incorrect"}]},
            )
        ).status_code == 404


async def test_character_learning_routes_require_authentication(client: httpx.AsyncClient) -> None:
    child_id = uuid.uuid4()
    assert (await client.get(f"/api/v1/children/{child_id}/characters/summary")).status_code == 401
    assert (
        await client.post(f"/api/v1/children/{child_id}/learning-sessions", json={"items": []})
    ).status_code == 401
