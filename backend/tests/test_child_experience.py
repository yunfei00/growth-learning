"""Unified child experience, growth projection, achievement, and reward integrity."""

import uuid
from datetime import datetime

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    AssessmentItem,
    AssessmentSession,
    ChildAchievement,
    ChineseCharacter,
    FamilyMember,
    FamilyRole,
    LearningRecord,
    StarLedger,
    SystemRole,
    User,
)
from app.services.character_catalog import import_characters, load_starter_dataset

pytestmark = pytest.mark.anyio
PASSWORD = "phase11-tests-only"


async def register(client: httpx.AsyncClient, email: str, name: str) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": name, "password": PASSWORD},
    )
    assert response.status_code == 201
    assert (
        await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    ).status_code == 200
    return response.json()


async def family_and_children(client: httpx.AsyncClient, suffix: str) -> tuple[dict, dict, dict]:
    family = (await client.post("/api/v1/families", json={"name": f"体验家庭{suffix}"})).json()
    children = []
    for name in ("老大", "老二"):
        response = await client.post(
            f"/api/v1/families/{family['id']}/children",
            json={"display_name": f"{name}{suffix}", "birth_date": "2021-05-01"},
        )
        assert response.status_code == 201
        children.append(response.json())
    return family, children[0], children[1]


async def starter_point_ids(
    session_factory: async_sessionmaker[AsyncSession], count: int
) -> list[str]:
    async with session_factory() as session:
        await import_characters(session, load_starter_dataset())
        return [
            str(point_id)
            for point_id in (
                await session.scalars(
                    select(ChineseCharacter.knowledge_point_id)
                    .order_by(ChineseCharacter.character)
                    .limit(count)
                )
            ).all()
        ]


def course_payload(point_ids: list[str]) -> dict:
    return {
        "title": "儿童体验课程",
        "description": "只引用 canonical KnowledgePoint",
        "source_type": "family",
        "reference_metadata": {},
        "units": [
            {
                "title": "成长单元",
                "activities": [
                    {
                        "title": "种下汉字种子",
                        "activity_type": "character_learning",
                        "knowledge_points": [
                            {"knowledge_point_id": point_id, "role": "primary"}
                            for point_id in point_ids
                        ],
                    }
                ],
            }
        ],
    }


async def test_today_aggregates_without_fake_or_duplicate_evidence(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as parent:
        user = await register(parent, "today-parent@example.com", "今日家长")
        _, child, _ = await family_and_children(parent, "今日")
        await starter_point_ids(session_factory, 20)
        async with session_factory() as session:
            assessment = AssessmentSession(
                child_id=uuid.UUID(child["id"]),
                evaluator_user_id=uuid.UUID(user["id"]),
                status="in_progress",
                source="daily_review",
            )
            session.add(assessment)
            await session.commit()

        first = await parent.get(f"/api/v1/children/{child['id']}/experience/today")
        second = await parent.get(f"/api/v1/children/{child['id']}/experience/today")
        assert first.status_code == second.status_code == 200
        first_payload = first.json()
        second_payload = second.json()
        review = next(item for item in first_payload["tasks"] if item["kind"] == "review")
        assert review["status"] == "in_progress"
        assert review["cta_label"] == "继续复习"
        assert second_payload["continue_task"]["source_id"] == review["source_id"]
        async with session_factory() as session:
            assert await session.scalar(select(func.count()).select_from(LearningRecord)) == 0
            assert await session.scalar(select(func.count()).select_from(AssessmentItem)) == 0
            assert await session.scalar(select(func.count()).select_from(AssessmentSession)) == 1


async def test_growth_tree_progress_is_not_mastery_and_rewards_are_idempotent(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as parent:
        await register(parent, "tree-parent@example.com", "成长树家长")
        family, child, sibling = await family_and_children(parent, "树")
        point_ids = await starter_point_ids(session_factory, 10)
        course = (
            await parent.post(
                f"/api/v1/families/{family['id']}/courses",
                json=course_payload(point_ids),
            )
        ).json()
        assert (
            await parent.post(
                f"/api/v1/children/{child['id']}/course-enrollments",
                json={"course_id": course["id"], "status": "active"},
            )
        ).status_code == 200
        activity_id = course["units"][0]["activities"][0]["id"]
        assert (
            await parent.post(
                f"/api/v1/children/{child['id']}/course-activities/{activity_id}/complete"
            )
        ).status_code == 200

        tree = (await parent.get(f"/api/v1/children/{child['id']}/growth-tree")).json()
        branch = tree["chinese"][0]
        assert branch["course_progress_percent"] == 100
        assert branch["touched"] == 10
        assert branch["familiar"] == 0
        assert tree["mastery_mapping"]["stable"] == "已经很熟悉"

        first = (await parent.get(f"/api/v1/children/{child['id']}/achievements")).json()
        second = (await parent.get(f"/api/v1/children/{child['id']}/achievements")).json()
        assert {item["key"] for item in first["achievements"]} >= {
            "first_learning",
            "learning_10_characters",
        }
        threshold = next(
            item for item in first["achievements"] if item["key"] == "learning_10_characters"
        )
        assert threshold["evidence_snapshot"]["observed_count"] == 10
        assert threshold["evidence_source_id"] is not None
        assert second["star_balance"] == first["star_balance"] == 4
        assert len(second["recent_ledger"]) == 2

        sibling_summary = (
            await parent.get(f"/api/v1/children/{sibling['id']}/achievements")
        ).json()
        assert sibling_summary["achievements"] == []
        assert sibling_summary["star_balance"] == 0
        async with session_factory() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ChildAchievement)
                    .where(ChildAchievement.child_id == uuid.UUID(child["id"]))
                )
                == 2
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(StarLedger)
                    .where(StarLedger.child_id == uuid.UUID(child["id"]))
                )
                == 2
            )
            session.add(
                StarLedger(
                    child_id=uuid.UUID(child["id"]),
                    amount=-1,
                    reason_type="invalid",
                    source_type="test",
                    source_id=uuid.uuid4(),
                    rule_version="test",
                    occurred_at=datetime.now().astimezone(),
                )
            )
            with pytest.raises(IntegrityError):
                await session.commit()


async def test_reward_permissions_and_private_child_experience_boundaries(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as parent,
        httpx.AsyncClient(transport=transport, base_url="http://test") as companion,
        httpx.AsyncClient(transport=transport, base_url="http://test") as outsider,
        httpx.AsyncClient(transport=transport, base_url="http://test") as admin,
        httpx.AsyncClient(transport=transport, base_url="http://test") as teacher,
    ):
        await register(parent, "reward-parent@example.com", "奖励家长")
        family, child, _ = await family_and_children(parent, "奖励")
        companion_user = await register(companion, "reward-companion@example.com", "奖励陪伴者")
        await register(outsider, "reward-outsider@example.com", "外部家长")
        admin_user = await register(admin, "reward-admin@example.com", "系统管理员")
        await register(teacher, "reward-teacher@example.com", "体验老师")
        async with session_factory() as session:
            session.add(
                FamilyMember(
                    family_id=uuid.UUID(family["id"]),
                    user_id=uuid.UUID(companion_user["id"]),
                    role=FamilyRole.COMPANION,
                )
            )
            system_admin = await session.get(User, uuid.UUID(admin_user["id"]))
            assert system_admin is not None
            system_admin.system_role = SystemRole.ADMIN
            await session.commit()

        assert (
            await parent.patch(
                f"/api/v1/families/{family['id']}/reward-settings",
                json={"stars_enabled": True},
            )
        ).status_code == 200
        goal = await parent.post(
            f"/api/v1/families/{family['id']}/reward-goals",
            json={"title": "周末选一本绘本", "required_stars": 10},
        )
        assert goal.status_code == 201
        assert (
            await companion.patch(
                f"/api/v1/families/{family['id']}/reward-settings",
                json={"stars_enabled": False},
            )
        ).status_code == 403
        for private_client in (outsider, admin, teacher):
            assert (
                await private_client.get(f"/api/v1/children/{child['id']}/achievements")
            ).status_code == 404


async def test_assessment_items_never_award_per_answer_stars(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as parent:
        user = await register(parent, "answer-stars@example.com", "答题家长")
        _, child, _ = await family_and_children(parent, "答题")
        point_ids = await starter_point_ids(session_factory, 3)
        async with session_factory() as session:
            completed_at = datetime.now().astimezone()
            assessment = AssessmentSession(
                child_id=uuid.UUID(child["id"]),
                evaluator_user_id=uuid.UUID(user["id"]),
                status="completed",
                source="daily_review",
                started_at=completed_at,
                completed_at=completed_at,
            )
            session.add(assessment)
            await session.flush()
            for index, point_id in enumerate(point_ids):
                session.add(
                    AssessmentItem(
                        session_id=assessment.id,
                        child_id=uuid.UUID(child["id"]),
                        knowledge_point_id=uuid.UUID(point_id),
                        evaluator_user_id=uuid.UUID(user["id"]),
                        outcome=("correct", "hinted_correct", "incorrect")[index],
                        assessed_at=completed_at,
                    )
                )
            await session.commit()

        summary = (await parent.get(f"/api/v1/children/{child['id']}/achievements")).json()
        assert summary["star_balance"] == 4
        assert len(summary["recent_ledger"]) == 2
        assert {entry["reason_type"] for entry in summary["recent_ledger"]} == {
            "achievement",
            "completed_review",
        }
