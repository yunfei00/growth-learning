"""Teacher authorization, canonical evidence reuse, and privacy boundary tests."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1.growth import get_growth_storage
from app.models import (
    AssessmentItem,
    ChildKnowledgeState,
    ClassroomMembership,
    FamilyMember,
    FamilyRole,
    GrowthEvent,
    LearningRecord,
    SystemRole,
    TeacherAssignmentProgress,
    TeacherChildRelation,
    TeacherObservation,
    TeacherProfile,
    User,
)
from app.schemas.knowledge import CharacterCreate
from app.services.character_catalog import create_character

pytestmark = pytest.mark.anyio
PASSWORD = "teacher-collaboration-tests-only"


async def register(client: httpx.AsyncClient, email: str, name: str) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": name, "password": PASSWORD},
    )
    assert response.status_code == 201
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200
    return response.json()


async def seed_characters(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[str]:
    values = [("山", "shān"), ("水", "shuǐ"), ("火", "huǒ"), ("木", "mù")]
    result: list[str] = []
    async with session_factory() as session:
        for character, pinyin in values:
            point, _ = await create_character(
                session,
                CharacterCreate(
                    character=character,
                    pinyin=pinyin,
                    common_words=[f"{character}字"],
                    simple_meaning="验收释义",
                ),
            )
            result.append(str(point.id))
    return result


async def test_parent_authorized_teacher_assignment_evidence_and_revocation(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as parent,
        httpx.AsyncClient(transport=transport, base_url="http://test") as companion,
        httpx.AsyncClient(transport=transport, base_url="http://test") as teacher,
        httpx.AsyncClient(transport=transport, base_url="http://test") as teacher_b,
        httpx.AsyncClient(transport=transport, base_url="http://test") as system_admin,
    ):
        test_app.dependency_overrides[get_growth_storage] = lambda: object()
        await register(parent, "teacher-parent@example.com", "家长")
        family = (await parent.post("/api/v1/families", json={"name": "教师协作家庭"})).json()
        child_a = (
            await parent.post(
                f"/api/v1/families/{family['id']}/children",
                json={"display_name": "老大", "birth_date": "2020-05-01"},
            )
        ).json()
        child_b = (
            await parent.post(
                f"/api/v1/families/{family['id']}/children",
                json={"display_name": "老二", "birth_date": "2022-05-01"},
            )
        ).json()
        companion_user = await register(companion, "teacher-companion@example.com", "陪伴者")
        teacher_user = await register(teacher, "teacher-a@example.com", "王老师账号")
        await register(teacher_b, "teacher-b@example.com", "李老师账号")
        admin_user = await register(system_admin, "teacher-system@example.com", "平台管理员")
        point_ids = await seed_characters(session_factory)

        async with session_factory() as session:
            session.add(
                FamilyMember(
                    family_id=uuid.UUID(family["id"]),
                    user_id=uuid.UUID(companion_user["id"]),
                    role=FamilyRole.COMPANION,
                )
            )
            admin = await session.get(User, uuid.UUID(admin_user["id"]))
            assert admin is not None
            admin.system_role = SystemRole.ADMIN
            await session.commit()

        teacher_profile = await teacher.post(
            "/api/v1/teacher/profile",
            json={
                "display_name": "王老师",
                "organization_name": "社区阅读小组",
                "short_bio": "陪伴儿童识字阅读",
            },
        )
        assert teacher_profile.status_code == 201
        teacher_code = teacher_profile.json()["teacher_code"]
        assert teacher_code.startswith("t_") and len(teacher_code) >= 20
        current_profile = await teacher.get("/api/v1/teacher/profile")
        assert current_profile.json()["id"] == teacher_profile.json()["id"]
        assert (
            await teacher.post("/api/v1/teacher/profile", json={"display_name": "重复"})
        ).json()["teacher_code"] == teacher_code

        second_profile = await teacher_b.post(
            "/api/v1/teacher/profile", json={"display_name": "李老师"}
        )
        assert second_profile.status_code == 201
        assert second_profile.json()["teacher_code"] != teacher_code

        resolved = await parent.get(f"/api/v1/teacher/connections/resolve?code={teacher_code}")
        assert resolved.status_code == 200
        assert resolved.json() == {
            "kind": "teacher",
            "teacher": {
                "id": teacher_profile.json()["id"],
                "display_name": "王老师",
                "organization_name": "社区阅读小组",
                "short_bio": "陪伴儿童识字阅读",
            },
            "classroom": None,
        }
        assert (
            await companion.post(
                f"/api/v1/children/{child_a['id']}/teacher-connections",
                json={"code": teacher_code},
            )
        ).status_code == 403
        assert (
            await teacher.post(
                f"/api/v1/children/{child_a['id']}/teacher-connections",
                json={"code": teacher_code},
            )
        ).status_code == 404

        relation = await parent.post(
            f"/api/v1/children/{child_a['id']}/teacher-connections",
            json={"code": teacher_code},
        )
        assert relation.status_code == 201
        assert relation.json()["status"] == "active"
        relation_id = relation.json()["id"]
        students = await teacher.get("/api/v1/teacher/students")
        assert students.status_code == 200
        assert [student["display_name"] for student in students.json()] == ["老大"]
        assert (await teacher.get(f"/api/v1/teacher/students/{child_b['id']}")).status_code == 404

        classroom = await teacher.post(
            "/api/v1/teacher/classrooms",
            json={"name": "大一班识字小组", "description": "轻量识字协作"},
        )
        assert classroom.status_code == 201
        class_code = classroom.json()["class_code"]
        assert class_code.startswith("c_") and len(class_code) >= 20
        class_resolve = await parent.get(f"/api/v1/teacher/connections/resolve?code={class_code}")
        assert class_resolve.status_code == 200
        assert class_resolve.json()["kind"] == "classroom"
        async with session_factory() as session:
            assert await session.scalar(select(func.count()).select_from(ClassroomMembership)) == 0
        assert (await teacher.get(f"/api/v1/teacher/students/{child_b['id']}")).status_code == 404
        joined = await parent.post(
            f"/api/v1/children/{child_a['id']}/teacher-connections",
            json={"code": class_code},
        )
        assert joined.status_code == 201
        assert (
            await teacher_b.patch(
                f"/api/v1/teacher/classrooms/{classroom.json()['id']}",
                json={"status": "archived"},
            )
        ).status_code == 404
        unauthorized_target = await teacher.post(
            "/api/v1/teacher/assignments",
            json={
                "title": "不应创建",
                "instructions": "不能选择未获授权的兄弟姐妹。",
                "assignment_type": "recognition_check",
                "target_child_ids": [child_b["id"]],
                "knowledge_point_ids": point_ids[:1],
            },
        )
        assert unauthorized_target.status_code == 403

        check = await teacher.post(
            "/api/v1/teacher/assignments",
            json={
                "classroom_id": classroom.json()["id"],
                "title": "认字小挑战",
                "instructions": "依次辨认山、水、火、木。",
                "assignment_type": "recognition_check",
                "due_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
                "target_child_ids": [child_a["id"]],
                "knowledge_point_ids": point_ids,
            },
        )
        assert check.status_code == 201, check.text
        assignment_id = check.json()["id"]
        assert check.json()["status"] == "draft"
        assert (
            await teacher_b.get(f"/api/v1/teacher/assignments/{assignment_id}")
        ).status_code == 404
        published = await teacher.post(f"/api/v1/teacher/assignments/{assignment_id}/publish")
        assert published.status_code == 200
        assert published.json()["status"] == "published"

        household_tasks = await parent.get(f"/api/v1/children/{child_a['id']}/teacher-tasks")
        assert household_tasks.status_code == 200
        assert household_tasks.json()[0]["title"] == "认字小挑战"
        started = await teacher.post(
            f"/api/v1/children/{child_a['id']}/teacher-tasks/{assignment_id}/start"
        )
        assert started.status_code == 200
        assessment_session_id = started.json()["assessment_session_id"]
        partial = await teacher.post(
            f"/api/v1/children/{child_a['id']}/teacher-tasks/{assignment_id}/progress",
            json={
                "assessment_items": [
                    {"knowledge_point_id": point_ids[0], "outcome": "correct"},
                    {"knowledge_point_id": point_ids[1], "outcome": "hinted_correct"},
                ]
            },
        )
        assert partial.status_code == 200
        assert partial.json()["completed_item_count"] == 2
        resumed = await teacher.post(
            f"/api/v1/children/{child_a['id']}/teacher-tasks/{assignment_id}/start"
        )
        assert resumed.json()["assessment_session_id"] == assessment_session_id
        assert resumed.json()["completed_item_count"] == 2
        completed = await teacher.post(
            f"/api/v1/children/{child_a['id']}/teacher-tasks/{assignment_id}/progress",
            json={
                "assessment_items": [
                    {"knowledge_point_id": point_ids[2], "outcome": "uncertain"},
                    {"knowledge_point_id": point_ids[3], "outcome": "incorrect"},
                ],
                "complete": True,
            },
        )
        assert completed.status_code == 200, completed.text
        assert completed.json()["progress_status"] == "completed"
        retry = await teacher.post(
            f"/api/v1/children/{child_a['id']}/teacher-tasks/{assignment_id}/progress",
            json={"complete": True},
        )
        assert retry.status_code == 200

        async with session_factory() as session:
            assessment_items = list(
                await session.scalars(
                    select(AssessmentItem).where(
                        AssessmentItem.session_id == uuid.UUID(assessment_session_id)
                    )
                )
            )
            assert len(assessment_items) == 4
            assert {item.outcome for item in assessment_items} == {
                "correct",
                "hinted_correct",
                "uncertain",
                "incorrect",
            }
            assert {item.evaluator_user_id for item in assessment_items} == {
                uuid.UUID(teacher_user["id"])
            }
            assert (
                int(
                    await session.scalar(
                        select(func.count())
                        .select_from(ChildKnowledgeState)
                        .where(ChildKnowledgeState.child_id == uuid.UUID(child_a["id"]))
                    )
                    or 0
                )
                == 4
            )

        analytics = await teacher.get(f"/api/v1/teacher/assignments/{assignment_id}/analytics")
        assert analytics.status_code == 200
        assert analytics.json()["completed"] == 1
        assert analytics.json()["outcome_counts"] == {
            "correct": 1,
            "hinted_correct": 1,
            "uncertain": 1,
            "incorrect": 1,
        }
        assert analytics.json()["ranking_enabled"] is False
        assert "ranking" not in {
            key.lower() for key in analytics.json() if key != "ranking_enabled"
        }
        assert set(analytics.json()["common_errors"]) == {"火", "木"}

        learning = await teacher.post(
            "/api/v1/teacher/assignments",
            json={
                "title": "识字学习",
                "instructions": "学习山和水。",
                "assignment_type": "character_learning",
                "target_child_ids": [child_a["id"]],
                "knowledge_point_ids": point_ids[:2],
            },
        )
        assert learning.status_code == 201
        learning_id = learning.json()["id"]
        await teacher.post(f"/api/v1/teacher/assignments/{learning_id}/publish")
        await teacher.post(f"/api/v1/children/{child_a['id']}/teacher-tasks/{learning_id}/start")
        learned = await teacher.post(
            f"/api/v1/children/{child_a['id']}/teacher-tasks/{learning_id}/progress",
            json={"learning_point_ids": point_ids[:2], "complete": True},
        )
        assert learned.status_code == 200
        async with session_factory() as session:
            progress = await session.scalar(
                select(TeacherAssignmentProgress).where(
                    TeacherAssignmentProgress.assignment_id == uuid.UUID(learning_id)
                )
            )
            assert progress is not None and progress.learning_session_id is not None
            records = list(
                await session.scalars(
                    select(LearningRecord).where(
                        LearningRecord.session_id == progress.learning_session_id
                    )
                )
            )
            assert len(records) == 2
            assert {record.source for record in records} == {"teacher_assignment"}

        for assignment_type in ("character_review", "reading"):
            payload = {
                "title": f"{assignment_type}任务",
                "instructions": "按现有安全学习流程完成。",
                "assignment_type": assignment_type,
                "target_child_ids": [child_a["id"]],
                "knowledge_point_ids": point_ids[:1]
                if assignment_type == "character_review"
                else [],
            }
            created = await teacher.post("/api/v1/teacher/assignments", json=payload)
            assert created.status_code == 201
            assert (
                await teacher.post(f"/api/v1/teacher/assignments/{created.json()['id']}/publish")
            ).status_code == 200

        async with session_factory() as session:
            mastery_before = {
                state.knowledge_point_id: (state.mastery_level, state.mastery_score)
                for state in await session.scalars(
                    select(ChildKnowledgeState).where(
                        ChildKnowledgeState.child_id == uuid.UUID(child_a["id"])
                    )
                )
            }
        exact_text = "今天‘人、山、水’三个字可以独立认出，‘火’需要提示。"
        observation = await teacher.post(
            f"/api/v1/teacher/students/{child_a['id']}/observations",
            json={
                "category": "recognition",
                "original_text": exact_text,
                "occurred_at": datetime.now(UTC).isoformat(),
                "assignment_id": assignment_id,
                "knowledge_point_ids": point_ids,
            },
        )
        assert observation.status_code == 201, observation.text
        assert observation.json()["original_text"] == exact_text
        async with session_factory() as session:
            saved = await session.get(TeacherObservation, uuid.UUID(observation.json()["id"]))
            assert saved is not None and saved.original_text == exact_text
            mastery_after = {
                state.knowledge_point_id: (state.mastery_level, state.mastery_score)
                for state in await session.scalars(
                    select(ChildKnowledgeState).where(
                        ChildKnowledgeState.child_id == uuid.UUID(child_a["id"])
                    )
                )
            }
            assert mastery_after == mastery_before
            event = await session.scalar(
                select(GrowthEvent).where(
                    GrowthEvent.source_entity_id == saved.id,
                    GrowthEvent.source_type == "teacher",
                )
            )
            assert event is not None and event.body == exact_text
        collaboration = await parent.get(f"/api/v1/children/{child_a['id']}/teacher-collaboration")
        assert collaboration.status_code == 200
        assert exact_text in [
            item["original_text"] for item in collaboration.json()["observations"]
        ]

        private_paths = [
            f"/api/v1/children/{child_a['id']}/growth/events",
            f"/api/v1/children/{child_a['id']}/growth/reports",
            f"/api/v1/children/{child_a['id']}/growth/books",
            f"/api/v1/children/{child_a['id']}/science/media/{uuid.uuid4()}",
        ]
        for path in private_paths:
            assert (await teacher.get(path)).status_code == 404
        assert (
            await teacher.post(f"/api/v1/families/{family['id']}/exports", json={})
        ).status_code == 404
        assert (
            await system_admin.get(f"/api/v1/teacher/students/{child_a['id']}")
        ).status_code == 403
        assert (
            await system_admin.get(f"/api/v1/children/{child_a['id']}/growth/events")
        ).status_code == 404

        assert (
            await companion.post(
                f"/api/v1/children/{child_a['id']}/teacher-connections/{relation_id}/revoke"
            )
        ).status_code == 403
        revoked = await parent.post(
            f"/api/v1/children/{child_a['id']}/teacher-connections/{relation_id}/revoke"
        )
        assert revoked.status_code == 200
        assert revoked.json()["status"] == "revoked"
        assert (await teacher.get(f"/api/v1/teacher/students/{child_a['id']}")).status_code == 404
        assert (
            await teacher.post(
                f"/api/v1/teacher/students/{child_a['id']}/observations",
                json={
                    "category": "other",
                    "original_text": "撤销后不应保存",
                    "occurred_at": datetime.now(UTC).isoformat(),
                },
            )
        ).status_code == 404
        assert (await teacher.get("/api/v1/teacher/students")).json() == []
        masked_history = await teacher.get(f"/api/v1/teacher/assignments/{assignment_id}")
        assert masked_history.status_code == 200
        assert masked_history.json()["targets"][0]["child_name"] == "已撤销学生"
        assert (
            await teacher.post(
                f"/api/v1/children/{child_a['id']}/teacher-tasks/{assignment_id}/start"
            )
        ).status_code == 404
        historical = await parent.get(f"/api/v1/children/{child_a['id']}/teacher-collaboration")
        assert historical.status_code == 200
        assert historical.json()["relations"][0]["status"] == "revoked"
        assert any(item["title"] == "认字小挑战" for item in historical.json()["assignments"])
        assert exact_text in [item["original_text"] for item in historical.json()["observations"]]

        async with session_factory() as session:
            relation_row = await session.get(TeacherChildRelation, uuid.UUID(relation_id))
            assert relation_row is not None and relation_row.revoked_at is not None
            profile = await session.scalar(
                select(TeacherProfile).where(
                    TeacherProfile.user_id == uuid.UUID(teacher_user["id"])
                )
            )
            assert profile is not None
            assert await session.scalar(select(func.count()).select_from(AssessmentItem)) == 4
            assert await session.scalar(select(func.count()).select_from(TeacherObservation)) == 1
        test_app.dependency_overrides.pop(get_growth_storage, None)


async def test_teacher_routes_require_authentication(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/v1/teacher/profile")).status_code == 401
    assert (await client.get("/api/v1/teacher/classrooms")).status_code == 401
    assert (await client.get("/api/v1/teacher/assignments")).status_code == 401
