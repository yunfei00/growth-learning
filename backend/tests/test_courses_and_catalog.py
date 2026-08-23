"""Reusable course, catalog provenance, and historical compatibility tests."""

import uuid
from datetime import UTC, date, datetime

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    ActivityKnowledgePoint,
    AssessmentSession,
    CatalogRelease,
    CharacterCatalogEntry,
    Child,
    ChildCourseEnrollment,
    ChildKnowledgeState,
    ChineseCharacter,
    Course,
    CourseActivityProgress,
    CourseUnit,
    ExperimentKnowledgePoint,
    Family,
    FamilyMember,
    FamilyRole,
    LearningRecord,
    LiteracyEstimate,
    ScienceExperiment,
    Story,
    StoryGenerationRun,
    StoryKnowledgePoint,
    StoryVersion,
    SystemRole,
    User,
)
from app.schemas.knowledge import CharacterCreate
from app.services.character_catalog import (
    create_character,
    import_characters,
    import_expanded_catalog,
    load_starter_dataset,
)
from app.services.child_character_learning import get_character_navigation
from app.services.review_planning import latest_literacy_estimate

pytestmark = pytest.mark.anyio
PASSWORD = "course-catalog-tests-only"


async def register(client: httpx.AsyncClient, email: str, name: str = "课程家长") -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": name, "password": PASSWORD},
    )
    assert response.status_code == 201
    assert (
        await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    ).status_code == 200
    return response.json()


async def family_with_children(client: httpx.AsyncClient, suffix: str) -> tuple[dict, dict, dict]:
    family = (await client.post("/api/v1/families", json={"name": f"课程家庭{suffix}"})).json()
    children = []
    for name in ("老大", "老二"):
        response = await client.post(
            f"/api/v1/families/{family['id']}/children",
            json={"display_name": f"{name}{suffix}", "birth_date": "2021-05-01"},
        )
        assert response.status_code == 201
        children.append(response.json())
    return family, children[0], children[1]


async def seed_points(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[str]:
    output: list[str] = []
    async with session_factory() as session:
        for character, pinyin in [
            ("山", "shān"),
            ("水", "shuǐ"),
            ("火", "huǒ"),
            ("木", "mù"),
            ("田", "tián"),
            ("人", "rén"),
        ]:
            point, _ = await create_character(
                session,
                CharacterCreate(
                    character=character,
                    pinyin=pinyin,
                    common_words=[f"{character}字"],
                    simple_meaning="测试释义",
                ),
            )
            output.append(str(point.id))
    return output


def course_payload(point_ids: list[str], *, source_type: str = "family") -> dict:
    return {
        "title": "本周主题识字",
        "description": "只引用系统知识点",
        "source_type": source_type,
        "reference_metadata": {},
        "units": [
            {
                "title": "第一单元",
                "activities": [
                    {
                        "title": "按顺序学习",
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


async def test_catalog_import_is_idempotent_preserves_ids_and_historical_links(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        starter = await import_characters(session, load_starter_dataset())
        assert starter.created == 200
        old_ids = dict(
            (
                await session.execute(
                    select(
                        ChineseCharacter.character,
                        ChineseCharacter.knowledge_point_id,
                    )
                )
            ).all()
        )
        old_point_id = old_ids["山"]
        user = User(
            email="history@example.com",
            display_name="历史家长",
            password_hash="test-only-hash",
        )
        family = Family(name="历史家庭")
        session.add_all([user, family])
        await session.flush()
        child = Child(
            family_id=family.id,
            display_name="历史孩子",
            birth_date=date(2021, 1, 1),
        )
        session.add(child)
        await session.flush()
        assessment = AssessmentSession(
            child_id=child.id,
            evaluator_user_id=user.id,
            status="completed",
            source="monthly_assessment",
        )
        story = Story(child_id=child.id, created_by_user_id=user.id, theme="nature")
        experiment = ScienceExperiment(
            canonical_key="history-science",
            title="历史实验",
            description="保留链接",
            age_min=4,
            difficulty="intro",
            estimated_duration_minutes=10,
            guiding_question="会发生什么？",
            expected_phenomenon="可观察",
            child_friendly_explanation="简单解释",
            parent_scientific_explanation="家长解释",
            safety_notes=[],
            common_failure_reasons=[],
            follow_up_questions=[],
            likely_child_questions=[],
            steps=["观察"],
            status="enabled",
            source_type="system",
        )
        session.add_all([assessment, story, experiment])
        await session.flush()
        run = StoryGenerationRun(
            child_id=child.id,
            requested_by_user_id=user.id,
            story_id=story.id,
            request_key="history-story",
            status="succeeded",
            difficulty="normal",
            theme="nature",
            target_knowledge_point_ids=[str(old_point_id)],
            provider="fake",
            model="fake",
            prompt_version="story-v1",
            attempt_count=1,
        )
        session.add(run)
        await session.flush()
        version = StoryVersion(
            story_id=story.id,
            generation_run_id=run.id,
            version_number=1,
            title="历史故事",
            paragraphs=["山。"],
            theme="nature",
            difficulty="normal",
            requested_known_coverage=0.9,
            actual_strong_known_coverage=1.0,
            actual_usable_known_coverage=1.0,
            actual_target_coverage=0.0,
            actual_unexpected_coverage=0.0,
            unique_known_coverage=1.0,
            total_han_occurrences=1,
            unique_han_count=1,
            unexpected_characters=[],
            target_characters=[],
            mastery_snapshot={"known": [str(old_point_id)]},
            snapshot_at=datetime.now(UTC),
            coverage_policy_version="coverage-v1",
            analyzer_version="analyzer-v1",
            prompt_version="story-v1",
            provider="fake",
            model="fake",
        )
        session.add(version)
        await session.flush()
        session.add_all(
            [
                LiteracyEstimate(
                    child_id=child.id,
                    assessment_session_id=assessment.id,
                    catalog_size=200,
                    catalog_version="growth-starter-v1",
                    sample_size=20,
                    known_count=10,
                    unknown_count=10,
                    sampling_method="legacy",
                    sampling_version="sampling-v1",
                    estimate=100,
                    is_sufficient=True,
                ),
                StoryKnowledgePoint(
                    story_version_id=version.id,
                    knowledge_point_id=old_point_id,
                    role="strong_known",
                    occurrence_count=1,
                    mastery_level_at_generation="stable",
                ),
                ExperimentKnowledgePoint(
                    experiment_id=experiment.id,
                    knowledge_point_id=old_point_id,
                    exposure_enabled=True,
                ),
            ]
        )
        await session.commit()

        first = await import_expanded_catalog(session)
        assert (first.created, first.preserved, first.catalog_size) == (1000, 200, 1200)
        assert first.errors == [] and first.course_created is True
        after_ids = dict(
            (
                await session.execute(
                    select(
                        ChineseCharacter.character,
                        ChineseCharacter.knowledge_point_id,
                    ).where(ChineseCharacter.character.in_(old_ids))
                )
            ).all()
        )
        assert after_ids == old_ids
        assert await session.scalar(select(func.count()).select_from(CharacterCatalogEntry)) == 1200
        assert await session.scalar(select(func.count()).select_from(CourseUnit)) == 4
        assert (
            await session.scalar(select(func.count()).select_from(ActivityKnowledgePoint)) == 1200
        )
        old_estimate = await session.scalar(select(LiteracyEstimate))
        assert old_estimate is not None
        assert (old_estimate.catalog_size, old_estimate.catalog_version) == (
            200,
            "growth-starter-v1",
        )
        new_child = Child(
            family_id=family.id,
            display_name="新目录孩子",
            birth_date=date(2022, 1, 1),
        )
        session.add(new_child)
        await session.commit()
        new_frame = await latest_literacy_estimate(session, new_child.id)
        assert (new_frame.catalog_size, new_frame.catalog_version) == (
            1200,
            "growth-chinese-v2-unihan-2026",
        )
        persisted_version = await session.get(StoryVersion, version.id)
        assert persisted_version is not None
        assert persisted_version.mastery_snapshot == {"known": [str(old_point_id)]}
        assert persisted_version.actual_strong_known_coverage == 1.0
        science_link = await session.scalar(select(ExperimentKnowledgePoint))
        assert science_link is not None and science_link.knowledge_point_id == old_point_id

        second = await import_expanded_catalog(session)
        assert second.created == 0
        assert second.preserved == 1200
        assert second.course_created is False
        assert await session.scalar(select(func.count()).select_from(CatalogRelease)) == 1
        assert await session.scalar(select(func.count()).select_from(Course)) == 1

        current_release_id = await session.scalar(
            select(CatalogRelease.id).where(CatalogRelease.is_current.is_(True))
        )
        assert current_release_id is not None
        ordered_point_ids = list(
            (
                await session.scalars(
                    select(CharacterCatalogEntry.knowledge_point_id)
                    .where(CharacterCatalogEntry.catalog_release_id == current_release_id)
                    .order_by(CharacterCatalogEntry.order_index)
                )
            ).all()
        )
        assert len(ordered_point_ids) == 1200

        async def system_navigation(position: int):
            result = await get_character_navigation(
                session,
                child.id,
                ordered_point_ids[position - 1],
                sequence="system_path",
                context_id=None,
                item_kind=None,
                mastery_level=None,
                priority=None,
                sort_by="character",
                sort_order="asc",
            )
            assert result is not None
            return result

        ninth = await system_navigation(9)
        tenth = await system_navigation(10)
        eleventh = await system_navigation(11)
        ninetieth = await system_navigation(90)
        first_character = await system_navigation(1)
        last_character = await system_navigation(1200)
        assert ninth.next and ninth.next.knowledge_point_id == ordered_point_ids[9]
        assert tenth.previous and tenth.previous.knowledge_point_id == ordered_point_ids[8]
        assert tenth.next and tenth.next.knowledge_point_id == ordered_point_ids[10]
        assert eleventh.previous and eleventh.previous.knowledge_point_id == ordered_point_ids[9]
        assert ninetieth.next and ninetieth.next.knowledge_point_id == ordered_point_ids[90]
        assert (tenth.group, eleventh.group, ninetieth.group) == (1, 2, 9)
        assert first_character.previous is None
        assert last_character.next is None


async def test_family_course_order_progress_copy_and_companion_boundary(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as parent,
        httpx.AsyncClient(transport=transport, base_url="http://test") as companion,
        httpx.AsyncClient(transport=transport, base_url="http://test") as outsider,
    ):
        await register(parent, "course-parent@example.com")
        family, child_a, child_b = await family_with_children(parent, "A")
        companion_user = await register(companion, "course-companion@example.com")
        await register(outsider, "course-outsider@example.com")
        outside_family, outside_child, _ = await family_with_children(outsider, "B")
        assert outside_family["id"] != family["id"]
        point_ids = await seed_points(session_factory)
        ordered = [point_ids[2], point_ids[0], point_ids[1]]
        async with session_factory() as session:
            session.add(
                FamilyMember(
                    family_id=uuid.UUID(family["id"]),
                    user_id=uuid.UUID(companion_user["id"]),
                    role=FamilyRole.COMPANION,
                )
            )
            await session.commit()

        denied = await companion.post(
            f"/api/v1/families/{family['id']}/courses", json=course_payload(ordered)
        )
        assert denied.status_code == 403
        created = await parent.post(
            f"/api/v1/families/{family['id']}/courses", json=course_payload(ordered)
        )
        assert created.status_code == 200
        course = created.json()
        assert [
            point["knowledge_point_id"] for point in course["units"][0]["activities"][0]["points"]
        ] == ordered
        assert course["progress_percent"] == 0

        assert (
            await outsider.get(f"/api/v1/courses/{course['id']}?child_id={outside_child['id']}")
        ).status_code == 404
        enrollment = await parent.post(
            f"/api/v1/children/{child_a['id']}/course-enrollments",
            json={"course_id": course["id"], "status": "active", "path_order": 0},
        )
        assert enrollment.status_code == 200
        plan = await parent.get(f"/api/v1/children/{child_a['id']}/today")
        new_items = [item for item in plan.json()["items"] if item["item_kind"] == "new"]
        assert [item["knowledge_point_id"] for item in new_items[:3]] == ordered
        assert all(item["selection_reason"] == "active_course_order" for item in new_items[:3])

        activity_id = course["units"][0]["activities"][0]["id"]
        completed = await companion.post(
            f"/api/v1/children/{child_a['id']}/course-activities/{activity_id}/complete"
        )
        assert completed.status_code == 200
        assert completed.json()["learning_records_created"] == 3
        repeated = await companion.post(
            f"/api/v1/children/{child_a['id']}/course-activities/{activity_id}/complete"
        )
        assert repeated.status_code == 200
        async with session_factory() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(LearningRecord)
                    .where(LearningRecord.child_id == uuid.UUID(child_a["id"]))
                )
                == 3
            )
            states = list(
                (
                    await session.scalars(
                        select(ChildKnowledgeState).where(
                            ChildKnowledgeState.child_id == uuid.UUID(child_a["id"])
                        )
                    )
                ).all()
            )
            assert {state.mastery_level for state in states} == {"introduced"}
            assert (
                await session.scalar(select(func.count()).select_from(CourseActivityProgress)) == 1
            )

        copied = await parent.post(
            f"/api/v1/children/{child_a['id']}/course-path/copy",
            json={"target_child_id": child_b["id"]},
        )
        assert copied.status_code == 200
        assert copied.json() == {
            "copied_enrollments": 1,
            "mastery_copied": False,
            "history_copied": False,
        }
        async with session_factory() as session:
            target_enrollment = await session.scalar(
                select(ChildCourseEnrollment).where(
                    ChildCourseEnrollment.child_id == uuid.UUID(child_b["id"])
                )
            )
            assert target_enrollment is not None and target_enrollment.status == "planned"
            assert not await session.scalar(
                select(ChildKnowledgeState.id).where(
                    ChildKnowledgeState.child_id == uuid.UUID(child_b["id"])
                )
            )
            assert not await session.scalar(
                select(LearningRecord.id).where(LearningRecord.child_id == uuid.UUID(child_b["id"]))
            )
        assert (
            await companion.patch(
                f"/api/v1/children/{child_b['id']}/course-enrollments/{target_enrollment.id}",
                json={"status": "active"},
            )
        ).status_code == 403

        activated = await parent.patch(
            f"/api/v1/children/{child_b['id']}/course-enrollments/{target_enrollment.id}",
            json={"status": "active"},
        )
        assert activated.status_code == 200
        await parent.patch(
            f"/api/v1/children/{child_b['id']}/learning-settings",
            json={"max_new_characters_per_day": 0},
        )
        no_new = await parent.get(f"/api/v1/children/{child_b['id']}/today")
        assert no_new.json()["recommended_new_count"] == 0
        assert not [item for item in no_new.json()["items"] if item["item_kind"] == "new"]


async def test_teacher_course_requires_parent_authorization_and_admin_has_no_child_access(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as parent,
        httpx.AsyncClient(transport=transport, base_url="http://test") as teacher,
        httpx.AsyncClient(transport=transport, base_url="http://test") as admin,
    ):
        await register(parent, "teacher-course-parent@example.com")
        _, child, _ = await family_with_children(parent, "T")
        await register(teacher, "teacher-course@example.com", "课程老师")
        admin_user = await register(admin, "course-system-admin@example.com", "系统管理员")
        point_ids = await seed_points(session_factory)
        async with session_factory() as session:
            user = await session.get(User, uuid.UUID(admin_user["id"]))
            assert user is not None
            user.system_role = SystemRole.ADMIN
            await session.commit()

        profile = await teacher.post("/api/v1/teacher/profile", json={"display_name": "课程老师"})
        assert profile.status_code == 201
        teacher_course = await teacher.post(
            "/api/v1/teacher/courses",
            json=course_payload(point_ids[:2], source_type="teacher"),
        )
        assert teacher_course.status_code == 200
        course_id = teacher_course.json()["id"]
        before = await parent.get(f"/api/v1/courses?child_id={child['id']}")
        assert course_id not in {course["id"] for course in before.json()}
        assert (
            await parent.post(
                f"/api/v1/children/{child['id']}/course-enrollments",
                json={"course_id": course_id, "status": "active"},
            )
        ).status_code == 404

        connected = await parent.post(
            f"/api/v1/children/{child['id']}/teacher-connections",
            json={"code": profile.json()["teacher_code"]},
        )
        assert connected.status_code == 201
        after = await parent.get(f"/api/v1/courses?child_id={child['id']}")
        assert course_id in {course["id"] for course in after.json()}
        assert (
            await parent.post(
                f"/api/v1/children/{child['id']}/course-enrollments",
                json={"course_id": course_id, "status": "active"},
            )
        ).status_code == 200
        assert (await admin.get(f"/api/v1/courses?child_id={child['id']}")).status_code == 404
