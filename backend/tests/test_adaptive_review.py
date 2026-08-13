"""Adaptive review, daily planning, periodic assessment, and privacy tests."""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    AssessmentItem,
    ChildKnowledgeState,
    ChildReviewSchedule,
    FamilyMember,
    FamilyRole,
    LearningRecord,
    SystemRole,
    User,
)
from app.schemas.knowledge import CharacterCreate
from app.services.character_catalog import create_character
from app.services.review_planning import (
    INTERVALS,
    project_review_schedule,
    recommend_new_load,
    recompute_child_review_schedules,
)

pytestmark = pytest.mark.anyio
PASSWORD = "local-test-password-only"


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


async def create_family_and_child(client: httpx.AsyncClient, suffix: str = "") -> tuple[dict, dict]:
    family_response = await client.post("/api/v1/families", json={"name": f"复习家庭{suffix}"})
    assert family_response.status_code == 201
    family = family_response.json()
    child_response = await client.post(
        f"/api/v1/families/{family['id']}/children",
        json={"display_name": f"小树{suffix}", "birth_date": "2021-03-15"},
    )
    assert child_response.status_code == 201
    return family, child_response.json()


async def seed_characters(
    session_factory: async_sessionmaker[AsyncSession], count: int
) -> list[str]:
    starter = list("人山水火木林森日月田土大小上下中一二三四五六七八九十口")
    assert count <= len(starter)
    output: list[str] = []
    async with session_factory() as session:
        for index, character in enumerate(starter[:count]):
            point, _ = await create_character(
                session,
                CharacterCreate(
                    character=character,
                    pinyin=f"pin{index}",
                    common_words=[f"{character}字"],
                    simple_meaning="测试释义",
                ),
            )
            output.append(str(point.id))
    return output


def _evidence(outcomes: list[str]) -> tuple[list[SimpleNamespace], list[SimpleNamespace]]:
    started = datetime(2026, 1, 1, 9, tzinfo=UTC)
    learning = [SimpleNamespace(id=uuid.uuid4(), learned_at=started, activity_type="introduced")]
    assessments = [
        SimpleNamespace(
            id=uuid.uuid4(),
            assessed_at=started + timedelta(days=index + 1),
            outcome=outcome,
        )
        for index, outcome in enumerate(outcomes)
    ]
    return learning, assessments


async def test_review_v1_interval_progression_and_outcomes_are_distinct() -> None:
    learning, correct_items = _evidence(["correct", "correct", "correct"])
    assert project_review_schedule(learning, correct_items[:1]).interval_days == 3
    assert project_review_schedule(learning, correct_items[:2]).interval_days == 7
    assert project_review_schedule(learning, correct_items).interval_days == 14

    outcomes = {}
    for outcome in ("correct", "hinted_correct", "uncertain", "incorrect"):
        projection = project_review_schedule(
            learning,
            [
                *correct_items,
                SimpleNamespace(
                    id=uuid.uuid4(),
                    assessed_at=datetime(2026, 1, 5, 9, tzinfo=UTC),
                    outcome=outcome,
                ),
            ],
        )
        outcomes[outcome] = projection.interval_days
    assert outcomes == {
        "correct": 30,
        "hinted_correct": 7,
        "uncertain": 3,
        "incorrect": 1,
    }

    _, maintenance_items = _evidence(["correct"] * 8)
    assert project_review_schedule(learning, maintenance_items).interval_days == INTERVALS[-1]


async def test_dynamic_new_load_is_explainable_and_recovers() -> None:
    assert recommend_new_load(5, 30, 15, 10, 0.8, 0.1)[0] == 0
    assert recommend_new_load(5, 15, 15, 10, 0.8, 0.1)[0] == 2
    assert recommend_new_load(5, 2, 15, 10, 0.4, 0.6)[0] == 1
    count, reason = recommend_new_load(5, 2, 15, 10, 0.9, 0.1)
    assert count == 5
    assert "稳定" in reason


async def test_daily_plan_persists_exact_new_character_cards(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await register_and_login(client, "daily-new-cards@example.com")
    _, child = await create_family_and_child(client)
    await seed_characters(session_factory, 8)

    first = await client.get(f"/api/v1/children/{child['id']}/today")
    second = await client.get(f"/api/v1/children/{child['id']}/today")
    assert first.status_code == second.status_code == 200
    new_items = [item for item in first.json()["items"] if item["item_kind"] == "new"]
    assert len(new_items) == first.json()["recommended_new_count"] == 5
    assert [item["knowledge_point_id"] for item in new_items] == [
        item["knowledge_point_id"] for item in second.json()["items"] if item["item_kind"] == "new"
    ]
    assert all(item["common_words"] and item["simple_meaning"] for item in new_items)


async def test_daily_plan_is_idempotent_capacity_limited_and_priority_ordered(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await register_and_login(client, "daily-plan@example.com")
    _, child = await create_family_and_child(client)
    point_ids = await seed_characters(session_factory, 8)
    learned = await client.post(
        f"/api/v1/children/{child['id']}/learning-sessions",
        json={"items": [{"knowledge_point_id": point_id} for point_id in point_ids[:6]]},
    )
    assert learned.status_code == 201
    settings = await client.patch(
        f"/api/v1/children/{child['id']}/learning-settings",
        json={"daily_review_capacity": 3, "max_new_characters_per_day": 5},
    )
    assert settings.status_code == 200

    async with session_factory() as session:
        schedules = list((await session.scalars(select(ChildReviewSchedule))).all())
        assert len(schedules) == 6
        records = {
            str(record.knowledge_point_id): record
            for record in (await session.scalars(select(LearningRecord))).all()
        }
        offsets = [6, 6, 5, 4, 3, 7]
        evidence_now = datetime.now(UTC)
        for point_id, days_ago in zip(point_ids[:6], offsets, strict=True):
            records[point_id].learned_at = evidence_now - timedelta(days=days_ago)
        priority = await session.scalar(
            select(ChildKnowledgeState).where(
                ChildKnowledgeState.knowledge_point_id == uuid.UUID(point_ids[0])
            )
        )
        assert priority is not None
        priority.is_priority = True
        mastery_before = priority.mastery_score
        await session.commit()

    first = await client.get(f"/api/v1/children/{child['id']}/today")
    second = await client.get(f"/api/v1/children/{child['id']}/today")
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["due_count"] == 6
    assert first.json()["review_count"] == 3
    assert first.json()["estimated_backlog_days"] == 2
    assert first.json()["recommended_new_count"] == 0
    review_items = [item for item in first.json()["items"] if item["item_kind"] == "review"]
    assert [item["knowledge_point_id"] for item in review_items] == [
        point_ids[5],
        point_ids[0],
        point_ids[1],
    ]

    async with session_factory() as session:
        priority = await session.scalar(
            select(ChildKnowledgeState).where(
                ChildKnowledgeState.knowledge_point_id == uuid.UUID(point_ids[0])
            )
        )
        assert priority is not None
        assert priority.mastery_score == mastery_before


async def test_daily_review_resumes_and_never_duplicates_evidence(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await register_and_login(client, "resume-review@example.com")
    _, child = await create_family_and_child(client)
    point_ids = await seed_characters(session_factory, 4)
    await client.post(
        f"/api/v1/children/{child['id']}/learning-sessions",
        json={"items": [{"knowledge_point_id": point_id} for point_id in point_ids]},
    )
    await client.patch(
        f"/api/v1/children/{child['id']}/learning-settings",
        json={"daily_review_capacity": 3, "max_new_characters_per_day": 0},
    )
    async with session_factory() as session:
        for record in (await session.scalars(select(LearningRecord))).all():
            record.learned_at = datetime.now(UTC) - timedelta(days=2)
        await session.commit()

    started = await client.post(f"/api/v1/children/{child['id']}/reviews/start")
    assert started.status_code == 200
    session_payload = started.json()
    assert session_payload["total_items"] == 3
    first_target = session_payload["targets"][0]
    submitted = await client.post(
        f"/api/v1/children/{child['id']}/planned-assessments/{session_payload['id']}/items",
        json={
            "items": [
                {
                    "knowledge_point_id": first_target["knowledge_point_id"],
                    "outcome": "uncertain",
                    "response_time_ms": 1400,
                }
            ]
        },
    )
    assert submitted.status_code == 200
    assert submitted.json()["completed_items"] == 1

    resumed = await client.post(f"/api/v1/children/{child['id']}/reviews/start")
    assert resumed.status_code == 200
    assert resumed.json()["id"] == session_payload["id"]
    assert resumed.json()["completed_items"] == 1
    duplicate = await client.post(
        f"/api/v1/children/{child['id']}/planned-assessments/{session_payload['id']}/items",
        json={
            "items": [
                {"knowledge_point_id": first_target["knowledge_point_id"], "outcome": "correct"}
            ]
        },
    )
    assert duplicate.status_code == 409

    remaining = [item for item in resumed.json()["targets"] if item["outcome"] is None]
    completed = await client.post(
        f"/api/v1/children/{child['id']}/planned-assessments/{session_payload['id']}/items",
        json={
            "items": [
                {
                    "knowledge_point_id": item["knowledge_point_id"],
                    "outcome": "correct" if index == 0 else "incorrect",
                    "response_time_ms": 1000 + index,
                }
                for index, item in enumerate(remaining)
            ],
            "complete": True,
        },
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["completed_items"] == 3
    async with session_factory() as session:
        assert int(await session.scalar(select(func.count()).select_from(AssessmentItem)) or 0) == 3


async def test_weekly_monthly_unseen_sampling_and_catalog_bounded_estimate(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await register_and_login(client, "periodic@example.com")
    _, child = await create_family_and_child(client)
    point_ids = await seed_characters(session_factory, 25)
    await client.post(
        f"/api/v1/children/{child['id']}/learning-sessions",
        json={"items": [{"knowledge_point_id": point_id} for point_id in point_ids[:8]]},
    )

    weekly = await client.post(f"/api/v1/children/{child['id']}/weekly-check/start")
    assert weekly.status_code == 200
    weekly_classes = {item["sampling_class"] for item in weekly.json()["targets"]}
    assert weekly.json()["total_items"] == 8
    assert weekly_classes & {"weak_or_priority", "recently_learned"}

    monthly = await client.post(f"/api/v1/children/{child['id']}/monthly-assessment/start")
    assert monthly.status_code == 200
    monthly_payload = monthly.json()
    assert monthly_payload["total_items"] == 25
    assert any(
        target["sampling_class"] == "unseen_not_system_taught"
        for target in monthly_payload["targets"]
    )
    completed = await client.post(
        f"/api/v1/children/{child['id']}/planned-assessments/{monthly_payload['id']}/items",
        json={
            "items": [
                {
                    "knowledge_point_id": item["knowledge_point_id"],
                    "outcome": "correct",
                    "response_time_ms": 900,
                }
                for item in monthly_payload["targets"]
            ],
            "complete": True,
        },
    )
    assert completed.status_code == 200
    estimate = await client.get(f"/api/v1/children/{child['id']}/literacy-estimate")
    assert estimate.status_code == 200
    assert estimate.json()["is_sufficient"] is True
    assert estimate.json()["catalog_size"] == 25
    assert 0 <= estimate.json()["estimate"] <= 25
    assert "当前系统字库范围" in estimate.json()["limitation"]

    history = await client.get(f"/api/v1/children/{child['id']}/assessment-history")
    assert history.status_code == 200
    assert {item["source"] for item in history.json()} == {
        "weekly_check",
        "monthly_assessment",
    }


async def test_insufficient_literacy_data_is_explicit(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await register_and_login(client, "insufficient@example.com")
    _, child = await create_family_and_child(client)
    await seed_characters(session_factory, 5)
    estimate = await client.get(f"/api/v1/children/{child['id']}/literacy-estimate")
    assert estimate.status_code == 200
    assert estimate.json()["catalog_size"] == 5
    assert estimate.json()["is_sufficient"] is False
    assert estimate.json()["estimate"] is None


async def test_recompute_preserves_raw_evidence(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await register_and_login(client, "review-recompute@example.com")
    _, child = await create_family_and_child(client)
    point_ids = await seed_characters(session_factory, 2)
    await client.post(
        f"/api/v1/children/{child['id']}/learning-sessions",
        json={"items": [{"knowledge_point_id": point_id} for point_id in point_ids]},
    )
    await client.post(
        f"/api/v1/children/{child['id']}/assessment-sessions",
        json={"items": [{"knowledge_point_id": point_ids[0], "outcome": "correct"}]},
    )
    child_id = uuid.UUID(child["id"])
    async with session_factory() as session:
        raw_before = (
            int(await session.scalar(select(func.count()).select_from(LearningRecord)) or 0),
            int(await session.scalar(select(func.count()).select_from(AssessmentItem)) or 0),
        )
        assert await recompute_child_review_schedules(session, child_id) == 2
        await session.commit()
        first = {
            row.knowledge_point_id: (row.interval_stage, row.next_review_at, row.last_outcome)
            for row in (await session.scalars(select(ChildReviewSchedule))).all()
        }
        assert await recompute_child_review_schedules(session, child_id) == 2
        await session.commit()
        second = {
            row.knowledge_point_id: (row.interval_stage, row.next_review_at, row.last_outcome)
            for row in (await session.scalars(select(ChildReviewSchedule))).all()
        }
        assert first == second
        assert raw_before == (
            int(await session.scalar(select(func.count()).select_from(LearningRecord)) or 0),
            int(await session.scalar(select(func.count()).select_from(AssessmentItem)) or 0),
        )


async def test_admin_companion_cross_family_and_system_admin_boundaries(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as owner,
        httpx.AsyncClient(transport=transport, base_url="http://test") as companion,
        httpx.AsyncClient(transport=transport, base_url="http://test") as outsider,
    ):
        await register_and_login(owner, "phase5-owner@example.com")
        family, child = await create_family_and_child(owner)
        companion_user = await register_and_login(companion, "phase5-companion@example.com")
        outsider_user = await register_and_login(outsider, "phase5-system-admin@example.com")
        point_ids = await seed_characters(session_factory, 1)
        await owner.post(
            f"/api/v1/children/{child['id']}/learning-sessions",
            json={"items": [{"knowledge_point_id": point_ids[0]}]},
        )
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
            record = await session.scalar(select(LearningRecord))
            assert record is not None
            record.learned_at = datetime.now(UTC) - timedelta(days=2)
            await session.commit()

        assert (
            await owner.patch(
                f"/api/v1/children/{child['id']}/learning-settings",
                json={"daily_review_capacity": 10},
            )
        ).status_code == 200
        assert (await companion.get(f"/api/v1/children/{child['id']}/today")).status_code == 200
        assert (
            await companion.post(f"/api/v1/children/{child['id']}/reviews/start")
        ).status_code == 200
        assert (
            await companion.patch(
                f"/api/v1/children/{child['id']}/learning-settings",
                json={"daily_review_capacity": 20},
            )
        ).status_code == 403

        private_paths = [
            f"/api/v1/children/{child['id']}/today",
            f"/api/v1/children/{child['id']}/reviews/backlog",
            f"/api/v1/children/{child['id']}/learning-settings",
            f"/api/v1/children/{child['id']}/literacy-estimate",
        ]
        for path in private_paths:
            assert (await outsider.get(path)).status_code == 404
        assert (
            await outsider.post(f"/api/v1/children/{child['id']}/weekly-check/start")
        ).status_code == 404
