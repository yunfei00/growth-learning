"""Phase 16 multi-subject catalog, evidence, course, and mastery boundaries."""

import uuid

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    AssessmentItem,
    ChildKnowledgeState,
    ChildReviewSchedule,
    LearningRecord,
    SystemRole,
    User,
)

pytestmark = pytest.mark.anyio
PASSWORD = "phase-16-tests-only"


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


async def make_system_admin(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> dict:
    user_payload = await register(client, "phase16-admin@example.com", "Phase 16 管理员")
    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(user_payload["id"]))
        assert user is not None
        user.system_role = SystemRole.ADMIN
        await session.commit()
    return user_payload


async def create_parent_child(client: httpx.AsyncClient) -> tuple[dict, dict]:
    await register(client, "phase16-parent@example.com", "Phase 16 家长")
    family = (await client.post("/api/v1/families", json={"name": "Phase 16 家庭"})).json()
    child_response = await client.post(
        f"/api/v1/families/{family['id']}/children",
        json={"display_name": "多学科孩子", "birth_date": "2021-05-01"},
    )
    assert child_response.status_code == 201
    return family, child_response.json()


async def create_knowledge(
    admin: httpx.AsyncClient,
    *,
    subject: str,
    knowledge_type: str,
    title: str,
    canonical_key: str,
) -> dict:
    response = await admin.post(
        "/api/v1/admin/knowledge",
        json={
            "subject": subject,
            "type": knowledge_type,
            "title": title,
            "canonical_key": canonical_key,
            "source_type": "test",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_admin_knowledge_filters_type_subject_constraints_and_empty_state(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as admin:
        await make_system_admin(admin, session_factory)
        pinyin = await create_knowledge(
            admin,
            subject="chinese",
            knowledge_type="pinyin_initial",
            title="声母 b",
            canonical_key="zh-pinyin-initial:b",
        )
        math = await create_knowledge(
            admin,
            subject="math",
            knowledge_type="math_skill",
            title="10 以内加法",
            canonical_key="math:add-within-10",
        )
        english = await create_knowledge(
            admin,
            subject="english",
            knowledge_type="english_word",
            title="cat",
            canonical_key="en-word:cat",
        )

        math_page = await admin.get("/api/v1/admin/knowledge?subject=math")
        assert math_page.status_code == 200
        assert [item["id"] for item in math_page.json()["items"]] == [math["id"]]
        assert math_page.json()["items"][0]["mastery_projection_status"] == "configured"
        assert math_page.json()["items"][0]["mastery_policy_key"] == "math-v1"
        pinyin_page = await admin.get("/api/v1/admin/knowledge?type=pinyin_initial&search=b")
        assert [item["id"] for item in pinyin_page.json()["items"]] == [pinyin["id"]]
        assert (await admin.get(f"/api/v1/admin/knowledge/{english['id']}")).status_code == 200
        empty = await admin.get("/api/v1/admin/knowledge?subject=science")
        assert empty.json()["items"] == [] and empty.json()["total"] == 0

        mismatch = await admin.post(
            "/api/v1/admin/knowledge",
            json={
                "subject": "math",
                "type": "english_word",
                "title": "invalid",
                "canonical_key": "invalid:word",
                "source_type": "test",
            },
        )
        assert mismatch.status_code == 422
        character_via_generic = await admin.post(
            "/api/v1/admin/knowledge",
            json={
                "subject": "chinese",
                "type": "chinese_character",
                "title": "人",
                "canonical_key": "zh-char:人",
                "source_type": "test",
            },
        )
        assert character_via_generic.status_code == 422


async def test_generic_learning_projects_math_but_generic_assessment_cannot_bypass_generator(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as admin,
        httpx.AsyncClient(transport=transport, base_url="http://test") as parent,
    ):
        await make_system_admin(admin, session_factory)
        _, child = await create_parent_child(parent)
        math = await create_knowledge(
            admin,
            subject="math",
            knowledge_type="math_skill",
            title="10 以内加法",
            canonical_key="math:add-within-10",
        )
        english = await create_knowledge(
            admin,
            subject="english",
            knowledge_type="english_word",
            title="cat",
            canonical_key="en-word:cat",
        )

        learning = await parent.post(
            f"/api/v1/children/{child['id']}/learning-sessions",
            json={
                "source": "phase16_generic",
                "items": [
                    {"knowledge_point_id": math["id"], "activity_type": "guided_practice"},
                    {"knowledge_point_id": english["id"], "activity_type": "applied"},
                ],
            },
        )
        assert learning.status_code == 201, learning.text
        assert learning.json()["mastery_projection"] == "configured"
        assert learning.json()["projection_unavailable_knowledge_point_ids"] == []
        assessment = await parent.post(
            f"/api/v1/children/{child['id']}/assessment-sessions",
            json={
                "source": "phase16_math_check",
                "assessment_kind": "math_check",
                "items": [
                    {
                        "knowledge_point_id": math["id"],
                        "outcome": "correct",
                        "skill_dimension": "accuracy",
                        "evidence_metadata": {"problem_count": 5, "representation": "objects"},
                    }
                ],
            },
        )
        assert assessment.status_code == 422, assessment.text
        assert "deterministic Math session" in assessment.json()["detail"]
        character_summary = await parent.get(f"/api/v1/children/{child['id']}/characters/summary")
        assert character_summary.status_code == 200
        assert character_summary.json()["total_enabled"] == 0
        assert character_summary.json()["learning_records"] == 0
        assert character_summary.json()["assessment_items"] == 0
        character_history = await parent.get(
            f"/api/v1/children/{child['id']}/character-learning-history"
        )
        assert character_history.json()["total_records"] == 0
        assert character_history.json()["distinct_characters"] == 0
        achievements = await parent.get(f"/api/v1/children/{child['id']}/achievements")
        assert achievements.status_code == 200
        assert achievements.json()["achievements"] == []

        async with session_factory() as session:
            child_id = uuid.UUID(child["id"])
            point_ids = [uuid.UUID(math["id"]), uuid.UUID(english["id"])]
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(LearningRecord)
                    .where(
                        LearningRecord.child_id == child_id,
                        LearningRecord.knowledge_point_id.in_(point_ids),
                    )
                )
                == 2
            )
            assert not await session.scalar(
                select(AssessmentItem.id).where(
                    AssessmentItem.knowledge_point_id == uuid.UUID(math["id"])
                )
            )
            state = await session.scalar(
                select(ChildKnowledgeState).where(
                    ChildKnowledgeState.child_id == child_id,
                    ChildKnowledgeState.knowledge_point_id == uuid.UUID(math["id"]),
                )
            )
            assert state is not None
            assert state.policy_key == "math-v1" and state.state_code == "introduced"
            english_state = await session.scalar(
                select(ChildKnowledgeState).where(
                    ChildKnowledgeState.child_id == child_id,
                    ChildKnowledgeState.knowledge_point_id == uuid.UUID(english["id"]),
                )
            )
            assert english_state is not None
            assert english_state.policy_key == "english-word-v1"
            assert english_state.state_code == "introduced"
            math_schedule = await session.scalar(
                select(ChildReviewSchedule).where(
                    ChildReviewSchedule.child_id == child_id,
                    ChildReviewSchedule.knowledge_point_id == uuid.UUID(math["id"]),
                )
            )
            assert math_schedule is not None
            assert math_schedule.algorithm_version == "math-review-v1"

        math_detail = await admin.get(f"/api/v1/admin/knowledge/{math['id']}")
        assert math_detail.json()["learning_evidence_count"] == 1
        assert math_detail.json()["assessment_evidence_count"] == 0
        assert math_detail.json()["child_state_count"] == 1


async def test_system_course_subject_isolation_generic_completion_and_filtering(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as admin,
        httpx.AsyncClient(transport=transport, base_url="http://test") as parent,
    ):
        await make_system_admin(admin, session_factory)
        _, child = await create_parent_child(parent)
        math = await create_knowledge(
            admin,
            subject="math",
            knowledge_type="math_skill",
            title="按规律排序",
            canonical_key="math:sequence-pattern",
        )
        english = await create_knowledge(
            admin,
            subject="english",
            knowledge_type="english_word",
            title="dog",
            canonical_key="en-word:dog",
        )

        def payload(point_id: str) -> dict:
            return {
                "subject": "math",
                "title": "数学基础路径",
                "source_type": "system",
                "units": [
                    {
                        "title": "规律",
                        "activities": [
                            {
                                "title": "引导练习",
                                "activity_type": "guided_practice",
                                "knowledge_points": [
                                    {"knowledge_point_id": point_id, "role": "primary"}
                                ],
                            }
                        ],
                    }
                ],
            }

        mismatch = await admin.post("/api/v1/admin/courses", json=payload(english["id"]))
        assert mismatch.status_code == 422
        created = await admin.post("/api/v1/admin/courses", json=payload(math["id"]))
        assert created.status_code == 201, created.text
        course = created.json()
        assert course["subject"] == "math"
        assert course["projection_unavailable_count"] == 0
        assert course["units"][0]["activities"][0]["points"][0]["mastery_level"] == "unlearned"
        assert course["units"][0]["activities"][0]["points"][0]["projection_status"] == "configured"

        math_courses = await parent.get(f"/api/v1/courses?child_id={child['id']}&subject=math")
        assert [item["id"] for item in math_courses.json()] == [course["id"]]
        english_courses = await parent.get(
            f"/api/v1/courses?child_id={child['id']}&subject=english"
        )
        assert english_courses.json() == []
        enrollment = await parent.post(
            f"/api/v1/children/{child['id']}/course-enrollments",
            json={"course_id": course["id"], "status": "active"},
        )
        assert enrollment.status_code == 200
        activity_id = course["units"][0]["activities"][0]["id"]
        completed = await parent.post(
            f"/api/v1/children/{child['id']}/course-activities/{activity_id}/complete"
        )
        assert completed.status_code == 200, completed.text
        assert completed.json()["learning_records_created"] == 1
        repeated = await parent.post(
            f"/api/v1/children/{child['id']}/course-activities/{activity_id}/complete"
        )
        assert repeated.json()["learning_records_created"] == 1

        async with session_factory() as session:
            child_id = uuid.UUID(child["id"])
            point_id = uuid.UUID(math["id"])
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(LearningRecord)
                    .where(
                        LearningRecord.child_id == child_id,
                        LearningRecord.knowledge_point_id == point_id,
                    )
                )
                == 1
            )
            state = await session.scalar(
                select(ChildKnowledgeState).where(
                    ChildKnowledgeState.child_id == child_id,
                    ChildKnowledgeState.knowledge_point_id == point_id,
                )
            )
            assert state is not None
            assert state.policy_key == "math-v1" and state.state_code == "introduced"
