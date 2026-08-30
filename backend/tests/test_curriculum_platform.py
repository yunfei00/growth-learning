"""Curriculum Platform V1 release, structure, validation, and portability boundaries."""

import uuid

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    ActivityKnowledgePoint,
    ChildCourseEnrollment,
    Course,
    CourseActivityProgress,
    CourseLesson,
    CoursePlatformEvent,
    CourseUnit,
    CurriculumRelease,
    KnowledgePoint,
    LearningActivity,
    LearningRecord,
    MathProblemTemplate,
    MathSkill,
    PlatformAuditLog,
    SystemRole,
    User,
)

pytestmark = pytest.mark.anyio
PASSWORD = "curriculum-platform-tests-only"


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


async def make_admin(
    client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> dict:
    user = await register(client, "curriculum-admin@example.com", "课程管理员")
    async with session_factory() as session:
        row = await session.get(User, uuid.UUID(user["id"]))
        assert row is not None
        row.system_role = SystemRole.ADMIN
        await session.commit()
    return user


async def seed_math_point(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[KnowledgePoint, KnowledgePoint]:
    async with session_factory() as session:
        point = KnowledgePoint(
            subject="math",
            type="math_skill",
            status="active",
            title="认识数量1～5",
            canonical_key="math:number:recognize-1-5",
            source_type="project_curated",
        )
        other = KnowledgePoint(
            subject="english",
            type="english_word",
            status="active",
            title="cat",
            canonical_key="en-word:cat-curriculum-test",
            source_type="project_curated",
        )
        session.add_all([point, other])
        await session.flush()
        session.add(
            MathSkill(
                knowledge_point_id=point.id,
                domain="quantity",
                skill_code="curriculum-test-recognize-1-5",
                difficulty_level=1,
                title=point.title,
                child_instruction="数一数。",
                parent_tip="用真实物体练习。",
                representation_types=["dots"],
                generator_key="quantity",
                settings_json={},
                order_index=9900,
                catalog_version="curriculum-test-v1",
            )
        )
        await session.flush()
        session.add(
            MathProblemTemplate(
                knowledge_point_id=point.id,
                template_key="curriculum-test:quantity",
                representation_type="dots",
                difficulty=1,
                generator_version="math-generator-v1",
                config_json={"minimum": 1, "maximum": 5},
                status="active",
                order_index=0,
            )
        )
        await session.commit()
        return point, other


def release_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "curriculum_key": "gl:grade1:math:semester1",
        "release_version": "2026-v1",
        "education_stage": "primary",
        "grade_level": 1,
        "semester": "semester_1",
        "subject": "math",
        "title": "一年级上 · 数学",
        "description": "课程平台结构测试",
        "source_type": "project_curated",
        "source_name": "Growth Learning",
        "license": "project_owned",
    }
    payload.update(overrides)
    return payload


async def create_parent_family(client: httpx.AsyncClient) -> tuple[dict, dict, dict]:
    await register(client, "curriculum-parent@example.com", "课程家长")
    family = (await client.post("/api/v1/families", json={"name": "课程测试家庭"})).json()
    first = (
        await client.post(
            f"/api/v1/families/{family['id']}/children",
            json={
                "display_name": "一年级孩子",
                "birth_date": "2019-05-01",
                "current_grade_level": 1,
                "school_year": "2026-2027",
            },
        )
    ).json()
    second = (
        await client.post(
            f"/api/v1/families/{family['id']}/children",
            json={"display_name": "另一个孩子", "birth_date": "2020-05-01"},
        )
    ).json()
    return family, first, second


async def test_grade_semester_contracts_foundation_compatibility_and_child_grade(
    test_app: FastAPI, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as admin:
        await make_admin(admin, session_factory)
        valid_payloads = [
            release_payload(),
            release_payload(
                curriculum_key="gl:grade1:math:semester2",
                release_version="2026-v1",
                semester="semester_2",
            ),
            release_payload(
                curriculum_key="gl:grade9:math:semester1",
                education_stage="junior_middle",
                grade_level=9,
            ),
            release_payload(
                curriculum_key="gl:foundation:math:full-year",
                education_stage="foundation",
                grade_level=None,
                semester="full_year",
            ),
        ]
        for payload in valid_payloads:
            response = await admin.post("/api/v1/admin/curriculum/releases", json=payload)
            assert response.status_code == 201, response.text
        invalid_payloads = [
            release_payload(curriculum_key="gl:bad:grade0", grade_level=0),
            release_payload(curriculum_key="gl:bad:grade10", grade_level=10),
            release_payload(
                curriculum_key="gl:bad:primary8", education_stage="primary", grade_level=8
            ),
            release_payload(
                curriculum_key="gl:bad:middle2",
                education_stage="junior_middle",
                grade_level=2,
            ),
        ]
        for payload in invalid_payloads:
            assert (
                await admin.post("/api/v1/admin/curriculum/releases", json=payload)
            ).status_code == 422
        async with session_factory() as session:
            foundation = await session.scalar(
                select(Course).where(Course.curriculum_key == "gl:foundation:math:full-year")
            )
            assert foundation is not None
            assert foundation.education_stage == "foundation"
            assert foundation.grade_level is None and foundation.semester == "full_year"


async def test_release_workflow_builder_validation_preview_version_pin_and_archive(
    test_app: FastAPI, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    point, other = await seed_math_point(session_factory)
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as admin,
        httpx.AsyncClient(transport=transport, base_url="http://test") as parent,
    ):
        await make_admin(admin, session_factory)
        _, child, second_child = await create_parent_family(parent)
        created = await admin.post("/api/v1/admin/curriculum/releases", json=release_payload())
        assert created.status_code == 201, created.text
        release = created.json()
        release_id = release["id"]
        course_id = release["course_id"]
        assert release["status"] == "draft" and release["course"]["status"] == "draft"
        assert release["grade_level_label"] == "一年级"

        assert (
            await parent.get(
                f"/api/v1/courses?child_id={child['id']}&grade_level=1&semester=semester_1"
            )
        ).json() == []
        empty_report = (
            await admin.get(f"/api/v1/admin/curriculum/releases/{release_id}/validate")
        ).json()
        assert empty_report["valid"] is False
        assert {issue["code"] for issue in empty_report["issues"]} == {"missing_unit"}

        release = (
            await admin.post(
                f"/api/v1/admin/curriculum/releases/{release_id}/units",
                json={"title": "测试课程结构"},
            )
        ).json()
        unit_id = release["course"]["units"][0]["id"]
        no_lesson = (
            await admin.get(f"/api/v1/admin/curriculum/releases/{release_id}/validate")
        ).json()
        assert any(issue["code"] == "missing_lesson" for issue in no_lesson["issues"])
        release = (
            await admin.post(
                f"/api/v1/admin/curriculum/units/{unit_id}/lessons",
                json={"title": "测试 Lesson", "estimated_minutes": 15},
            )
        ).json()
        lesson_id = release["course"]["units"][0]["lessons"][0]["id"]
        release = (
            await admin.post(
                f"/api/v1/admin/curriculum/lessons/{lesson_id}/activities",
                json={"title": "数量观察", "activity_type": "knowledge_learning"},
            )
        ).json()
        activity_id = release["course"]["units"][0]["lessons"][0]["activities"][0]["id"]
        mismatch = await admin.post(
            f"/api/v1/admin/curriculum/activities/{activity_id}/knowledge-points",
            json={"knowledge_point_id": str(other.id)},
        )
        assert mismatch.status_code == 422
        release = (
            await admin.post(
                f"/api/v1/admin/curriculum/activities/{activity_id}/knowledge-points",
                json={
                    "knowledge_point_id": str(point.id),
                    "role": "primary",
                    "reference_code": point.canonical_key,
                },
            )
        ).json()
        mapping_id = release["course"]["units"][0]["lessons"][0]["activities"][0]["points"][0][
            "mapping_id"
        ]
        assert mapping_id

        async with session_factory() as session:
            evidence_before = int(
                await session.scalar(select(func.count()).select_from(LearningRecord)) or 0
            )
        preview = await admin.get(f"/api/v1/admin/curriculum/releases/{release_id}/preview")
        assert preview.status_code == 200
        assert preview.json()["preview_mode"] is True
        assert preview.json()["writes_learning_data"] is False
        async with session_factory() as session:
            evidence_after = int(
                await session.scalar(select(func.count()).select_from(LearningRecord)) or 0
            )
        assert evidence_after == evidence_before

        report = (
            await admin.get(f"/api/v1/admin/curriculum/releases/{release_id}/validate")
        ).json()
        assert report["valid"] is True and report["error_count"] == 0
        assert report["statistics"] == {
            "units": 1,
            "lessons": 1,
            "activities": 1,
            "knowledge_points": 1,
        }
        submitted = await admin.post(
            f"/api/v1/admin/curriculum/releases/{release_id}/transition/submit", json={}
        )
        assert submitted.json()["status"] == "in_review"
        locked = await admin.patch(
            f"/api/v1/admin/curriculum/nodes/unit/{unit_id}", json={"title": "不允许"}
        )
        assert locked.status_code == 422
        reviewed = await admin.post(
            f"/api/v1/admin/curriculum/releases/{release_id}/transition/review", json={}
        )
        assert reviewed.json()["reviewed_by_user_id"] is not None
        published = await admin.post(
            f"/api/v1/admin/curriculum/releases/{release_id}/transition/publish", json={}
        )
        assert published.status_code == 200, published.text
        assert published.json()["status"] == "published"
        assert published.json()["validation_snapshot"]["valid"] is True
        assert (
            await admin.patch(
                f"/api/v1/admin/curriculum/nodes/activity/{activity_id}",
                json={"title": "发布后不能改"},
            )
        ).status_code == 422
        assert (
            await admin.patch(
                f"/api/v1/admin/courses/{course_id}", json={"title": "旧接口也不能改"}
            )
        ).status_code == 422

        public = await parent.get(
            f"/api/v1/courses?child_id={child['id']}&grade_level=1&semester=semester_1&subject=math"
        )
        assert [item["id"] for item in public.json()] == [course_id]
        enrollment = await parent.post(
            f"/api/v1/children/{child['id']}/course-enrollments",
            json={"course_id": course_id, "status": "active"},
        )
        assert enrollment.status_code == 200, enrollment.text
        assert enrollment.json()["curriculum_release_id"] == release_id
        assert enrollment.json()["curriculum_version"] == "2026-v1"

        cloned = await admin.post(
            f"/api/v1/admin/curriculum/releases/{release_id}/new-version",
            json={"release_version": "2026-v2", "change_summary": "结构调整"},
        )
        assert cloned.status_code == 200, cloned.text
        clone = cloned.json()
        assert clone["status"] == "draft" and clone["id"] != release_id
        assert clone["course_id"] != course_id
        assert clone["course"]["units"][0]["id"] != unit_id
        cloned_point = clone["course"]["units"][0]["lessons"][0]["activities"][0]["points"][0]
        assert cloned_point["knowledge_point_id"] == str(point.id)
        async with session_factory() as session:
            assert (
                await session.scalar(select(func.count()).select_from(ChildCourseEnrollment)) == 1
            )
            assert await session.scalar(select(func.count()).select_from(LearningRecord)) == 0

        archived = await admin.post(
            f"/api/v1/admin/curriculum/releases/{release_id}/transition/archive", json={}
        )
        assert archived.json()["status"] == "archived"
        existing_history = await parent.get(
            f"/api/v1/courses?child_id={child['id']}&grade_level=1&semester=semester_1"
        )
        assert course_id in {item["id"] for item in existing_history.json()}
        new_browser = await parent.get(
            f"/api/v1/courses?child_id={second_child['id']}&grade_level=1&semester=semester_1"
        )
        assert course_id not in {item["id"] for item in new_browser.json()}
        blocked_enrollment = await parent.post(
            f"/api/v1/children/{second_child['id']}/course-enrollments",
            json={"course_id": course_id, "status": "active"},
        )
        assert blocked_enrollment.status_code == 404

        async with session_factory() as session:
            audit_events = set(await session.scalars(select(PlatformAuditLog.event_type)))
            assert {
                "course_created",
                "course_updated",
                "curriculum_submitted",
                "curriculum_reviewed",
                "curriculum_published",
                "curriculum_archived",
                "curriculum_version_created",
            }.issubset(audit_events)
            course_events = set(await session.scalars(select(CoursePlatformEvent.event_type)))
            assert "course_started" in course_events


async def test_curriculum_export_dry_run_idempotent_import_and_unknown_knowledge(
    test_app: FastAPI, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    point, _ = await seed_math_point(session_factory)
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as admin:
        await make_admin(admin, session_factory)
        document = {
            "schema_version": "gl-curriculum-v1",
            "curriculum_version": "2026-import-v1",
            "course": release_payload(
                curriculum_key="gl:grade1:math:semester2-import",
                release_version="2026-import-v1",
                semester="semester_2",
            ),
            "units": [
                {
                    "title": "导入 Unit",
                    "lessons": [
                        {
                            "title": "导入 Lesson",
                            "activities": [
                                {
                                    "title": "导入 Activity",
                                    "activity_type": "knowledge_learning",
                                    "knowledge_points": [
                                        {
                                            "canonical_key": point.canonical_key,
                                            "role": "primary",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        async with session_factory() as session:
            before = int(
                await session.scalar(select(func.count()).select_from(CurriculumRelease)) or 0
            )
        dry_run = await admin.post("/api/v1/admin/curriculum/import?dry_run=true", json=document)
        assert dry_run.status_code == 200, dry_run.text
        assert dry_run.json()["dry_run"] is True
        assert dry_run.json()["will_create"]
        async with session_factory() as session:
            after_dry_run = int(
                await session.scalar(select(func.count()).select_from(CurriculumRelease)) or 0
            )
        assert after_dry_run == before

        imported = await admin.post("/api/v1/admin/curriculum/import?dry_run=false", json=document)
        assert imported.status_code == 200, imported.text
        assert imported.json()["errors"] == []
        release_id = imported.json()["release_id"]
        exported = await admin.get(f"/api/v1/admin/curriculum/releases/{release_id}/export")
        assert exported.json()["course"]["curriculum_key"] == document["course"]["curriculum_key"]
        assert "children" not in exported.json()
        repeated = await admin.post("/api/v1/admin/curriculum/import?dry_run=false", json=document)
        assert repeated.json()["idempotent"] is True
        async with session_factory() as session:
            assert (
                await session.scalar(select(func.count()).select_from(CurriculumRelease))
                == before + 1
            )

        unknown = {**document, "curriculum_version": "2026-unknown-v1"}
        unknown["course"] = {
            **document["course"],
            "release_version": "2026-unknown-v1",
            "curriculum_key": "gl:grade1:math:unknown",
        }
        unknown["units"] = [
            {
                "title": "未知知识点",
                "lessons": [
                    {
                        "title": "未知",
                        "activities": [
                            {
                                "title": "未知",
                                "activity_type": "knowledge_learning",
                                "knowledge_points": [
                                    {"canonical_key": "math:unknown:never-create"}
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
        rejected = await admin.post("/api/v1/admin/curriculum/import?dry_run=false", json=unknown)
        assert rejected.json()["errors"] == ["Unknown KnowledgePoint: math:unknown:never-create"]
        async with session_factory() as session:
            assert not await session.scalar(
                select(KnowledgePoint.id).where(
                    KnowledgePoint.canonical_key == "math:unknown:never-create"
                )
            )


async def test_legacy_course_ids_enrollment_progress_and_evidence_are_untouched(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        user = User(
            email="legacy-curriculum@example.com",
            display_name="历史课程家长",
            password_hash="test-only",
        )
        session.add(user)
        await session.flush()
        course = Course(
            subject="math",
            title="历史数学启蒙",
            source_type="system",
            created_by_user_id=user.id,
            status="enabled",
            system_key="legacy-math-foundation-test",
            reference_metadata={},
        )
        session.add(course)
        await session.flush()
        course_id = course.id
        assert course.education_stage == "foundation"
        assert course.grade_level is None and course.semester == "full_year"
        assert course.curriculum_release_id is None
        assert course.id == course_id
        assert (
            await session.scalar(
                select(func.count())
                .select_from(CourseUnit)
                .where(CourseUnit.course_id == course.id)
            )
            == 0
        )
        assert await session.scalar(select(func.count()).select_from(CourseLesson)) == 0
        assert await session.scalar(select(func.count()).select_from(LearningActivity)) == 0
        assert await session.scalar(select(func.count()).select_from(ActivityKnowledgePoint)) == 0
        assert await session.scalar(select(func.count()).select_from(ChildCourseEnrollment)) == 0
        assert await session.scalar(select(func.count()).select_from(CourseActivityProgress)) == 0
        assert await session.scalar(select(func.count()).select_from(LearningRecord)) == 0
