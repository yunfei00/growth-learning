"""Phase 19 catalog, audio boundary, evidence, mastery, access, and admin tests."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    AssessmentItem,
    ChildKnowledgeState,
    ChildReviewSchedule,
    Course,
    CourseUnit,
    EnglishCatalogRelease,
    EnglishExerciseAttempt,
    EnglishItem,
    EnglishPracticeItem,
    KnowledgePoint,
    LearningRecord,
    SystemRole,
    User,
)
from app.services.english_audio import english_audio_provider
from app.services.english_catalog import (
    COURSE_UNITS,
    ENGLISH_CATALOG_VERSION,
    ENGLISH_COURSE_KEY,
    ENGLISH_GENERATOR_VERSION,
    ENGLISH_SEEDS,
    STATIC_VISUAL_WORDS,
    import_english_foundation,
    stable_english_point_id,
)
from app.services.english_problem_generator import generate_english_problem
from app.services.english_visual import english_visual_provider
from app.services.mastery import EnglishMasteryPolicy, mastery_policy_for_type

pytestmark = pytest.mark.anyio
PASSWORD = "phase-19-tests-only"


async def register(client: httpx.AsyncClient, email: str, name: str) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": name, "password": PASSWORD},
    )
    assert response.status_code == 201, response.text
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return response.json()


async def create_family_child(
    client: httpx.AsyncClient, *, name: str = "英语孩子"
) -> tuple[dict, dict]:
    family_response = await client.post("/api/v1/families", json={"name": f"{name}家庭"})
    assert family_response.status_code == 201, family_response.text
    family = family_response.json()
    child_response = await client.post(
        f"/api/v1/families/{family['id']}/children",
        json={"display_name": name, "birth_date": "2021-08-29"},
    )
    assert child_response.status_code == 201, child_response.text
    return family, child_response.json()


async def import_catalog(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        result = await import_english_foundation(session)
        assert result.errors == []


async def answers_for_session(
    session_factory: async_sessionmaker[AsyncSession], session_id: str
) -> list[tuple[str, object]]:
    async with session_factory() as session:
        attempts = list(
            await session.scalars(
                select(EnglishExerciseAttempt)
                .where(EnglishExerciseAttempt.session_id == uuid.UUID(session_id))
                .order_by(EnglishExerciseAttempt.created_at, EnglishExerciseAttempt.id)
            )
        )
        return [(str(value.id), value.expected_answer) for value in attempts]


def english_assessment(
    when: datetime, dimension: str, *, outcome: str = "correct"
) -> AssessmentItem:
    return AssessmentItem(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        child_id=uuid.uuid4(),
        knowledge_point_id=uuid.uuid4(),
        evaluator_user_id=uuid.uuid4(),
        outcome=outcome,
        hint_used=outcome != "correct",
        skill_dimension=dimension,
        evidence_metadata={"problem_count": 3, "first_answer_correct_count": 3},
        assessed_at=when,
    )


async def test_catalog_is_bounded_stable_idempotent_and_has_21_unit_course(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        first = await import_english_foundation(session)
        assert first.errors == []
        assert first.catalog_size == len(ENGLISH_SEEDS) == 217
        assert (first.word_count, first.letter_count, first.phonics_count, first.phrase_count) == (
            132,
            26,
            44,
            15,
        )
        assert first.practice_item_count == 375
        assert first.created == 217 and first.course_created is True
        rows = (
            await session.execute(
                select(KnowledgePoint, EnglishItem)
                .join(EnglishItem)
                .order_by(EnglishItem.order_index)
            )
        ).all()
        assert len(rows) == 217
        assert all(point.id == stable_english_point_id(point.canonical_key) for point, _ in rows)
        assert {point.type for point, _ in rows} == {
            "english_word",
            "english_letter",
            "english_phonics",
            "english_phrase",
        }
        original = [(point.id, point.canonical_key, item.order_index) for point, item in rows]
        second = await import_english_foundation(session)
        assert second.errors == []
        assert second.created == second.updated == second.practice_items_created == 0
        assert second.skipped == 217 and second.course_created is False
        reloaded = (
            await session.execute(
                select(KnowledgePoint, EnglishItem)
                .join(EnglishItem)
                .order_by(EnglishItem.order_index)
            )
        ).all()
        assert [
            (point.id, point.canonical_key, item.order_index) for point, item in reloaded
        ] == original
        assert await session.scalar(select(func.count()).select_from(EnglishPracticeItem)) == 375
        release = await session.scalar(select(EnglishCatalogRelease))
        assert release is not None
        assert release.catalog_version == ENGLISH_CATALOG_VERSION
        course = await session.scalar(select(Course).where(Course.system_key == ENGLISH_COURSE_KEY))
        assert course is not None and course.subject == "english"
        units = list(
            await session.scalars(
                select(CourseUnit)
                .where(CourseUnit.course_id == course.id)
                .order_by(CourseUnit.order_index)
            )
        )
        assert len(units) == len(COURSE_UNITS) == 21


async def test_audio_visual_and_generators_are_safe_and_reproducible(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await import_english_foundation(session)
        for canonical_key in (
            "english:word:cat",
            "english:word:red",
            "english:letter:a",
            "english:phonics:consonant-m",
            "english:phonics:cvc-cat",
            "english:phrase:hello",
        ):
            row = (
                await session.execute(
                    select(KnowledgePoint, EnglishItem)
                    .join(EnglishItem)
                    .where(KnowledgePoint.canonical_key == canonical_key)
                )
            ).one()
            _point, item = row
            audio = english_audio_provider.resolve(item)
            visual = english_visual_provider.resolve(item)
            assert audio.accent == "en-US"
            assert visual.license and visual.source
            if item.kind == "phonics":
                assert audio.strategy in {"safe_example_word", "phonics_unavailable", "curated"}
                if item.category != "cvc":
                    assert audio.speech_text != item.text
            else:
                assert audio.strategy in {"curated", "tts"}
        assert frozenset({"cat", "dog", "apple", "ball", "sun", "moon"}) == STATIC_VISUAL_WORDS
        for word in sorted(STATIC_VISUAL_WORDS):
            item = await session.scalar(
                select(EnglishItem)
                .join(KnowledgePoint)
                .where(KnowledgePoint.canonical_key == f"english:word:{word}")
            )
            assert item is not None
            visual = english_visual_provider.resolve(item)
            assert visual.visual_type == "static_image"
            assert visual.image_url == f"/english/visuals/{word}.svg"
            assert visual.visual_key

        templates = list(
            await session.scalars(
                select(EnglishPracticeItem).where(
                    EnglishPracticeItem.template_key.in_(
                        {
                            "english:word:cat:listen_choose_visual:v1",
                            "english:word:cat:visual_choose_audio:v1",
                            "english:letter:a:letter_match:v1",
                            "english:letter:a:case_match:v1",
                            "english:phonics:consonant-m:phonics_choose:v1",
                            "english:phonics:cvc-cat:blending:v1",
                            "english:phrase:hello:phrase_listening:v1",
                        }
                    )
                )
            )
        )
        assert len(templates) == 7
        for template in templates:
            first = await generate_english_problem(session, template, 19001)
            second = await generate_english_problem(session, template, 19001)
            assert first == second
            assert first.generator_version == ENGLISH_GENERATOR_VERSION
            assert sum(option["value"] == first.expected_answer for option in first.options) == 1
            assert all(option["assessment_alt"].startswith("选项") for option in first.options)
            if first.prompt.get("hide_target_text"):
                assert "text" not in first.prompt
            if template.practice_kind == "visual_choose_audio":
                assert first.prompt.get("visual") is not None
            else:
                assert "visual" not in first.prompt


def test_four_english_mastery_policies_require_independent_cross_day_evidence() -> None:
    policies = {
        "english_word": ("english-word-v1", ("listening", "meaning")),
        "english_letter": ("english-letter-v1", ("letter_name", "case_matching")),
        "english_phonics": ("english-phonics-v1", ("sound_recognition",)),
        "english_phrase": ("english-phrase-v1", ("listening", "meaning")),
    }
    start = datetime(2026, 8, 1, 8, tzinfo=UTC)
    for knowledge_type, (key, dimensions) in policies.items():
        policy = mastery_policy_for_type(knowledge_type)
        assert isinstance(policy, EnglishMasteryPolicy) and policy.key == key
        same_day = [
            english_assessment(start + timedelta(minutes=index), dimension)
            for dimension in dimensions
            for index in range(3)
        ]
        projection = policy.recompute([], same_day, knowledge_type=knowledge_type)
        assert projection.state_code == "practicing"
        assert projection.state_code != "stable"
        across_days = [
            english_assessment(start + timedelta(days=day), dimension)
            for dimension in dimensions
            for day in (0, 3, 8)
        ]
        projection = policy.recompute([], across_days, knowledge_type=knowledge_type)
        assert projection.state_code == "stable"
        assert projection.dimensions_json["speaking_is_required"] is False
    word = mastery_policy_for_type("english_word")
    speaking_only = [
        english_assessment(start + timedelta(days=day), "speaking") for day in (0, 3, 8)
    ]
    assert (
        word.recompute([], speaking_only, knowledge_type="english_word").state_code == "practicing"
    )


async def test_practice_assessment_today_history_and_phonics_boundary(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await import_catalog(session_factory)
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as parent:
        await register(parent, "phase19-parent@example.com", "英语爸爸")
        _, child = await create_family_child(parent)
        child_id = child["id"]
        overview = await parent.get(f"/api/v1/children/{child_id}/english/overview")
        assert overview.status_code == 200 and overview.json()["total"] == 217
        assert overview.json()["letters_total"] == 26
        today = await parent.get(f"/api/v1/children/{child_id}/english/today")
        assert today.status_code == 200 and today.json()["target_count"] == 3
        item_id = today.json()["items"][0]["knowledge_point_id"]
        detail = await parent.get(f"/api/v1/children/{child_id}/english/items/{item_id}")
        assert detail.status_code == 200 and detail.json()["policy_key"] == "english-word-v1"
        assert detail.json()["audio"]["accent"] == "en-US"

        practice = await parent.post(
            f"/api/v1/children/{child_id}/english/sessions",
            json={
                "knowledge_point_id": item_id,
                "mode": "practice",
                "exercise_count": 3,
                "dimension": "listening",
                "seed": 19,
            },
        )
        assert practice.status_code == 201, practice.text
        answers = await answers_for_session(session_factory, practice.json()["session_id"])
        first_id, expected = answers[0]
        wrong = "english:word:not-the-answer"
        wrong_response = await parent.post(
            f"/api/v1/children/{child_id}/english/sessions/{practice.json()['session_id']}/attempts/{first_id}/answer",
            json={"submitted_answer": wrong, "hint_used": False, "audio_replays": 2},
        )
        assert wrong_response.status_code == 200 and wrong_response.json()["outcome"] == "incorrect"
        retry = await parent.post(
            f"/api/v1/children/{child_id}/english/sessions/{practice.json()['session_id']}/attempts/{first_id}/answer",
            json={"submitted_answer": expected, "hint_used": True, "audio_replays": 1},
        )
        assert retry.status_code == 200 and retry.json()["outcome"] == "hinted_correct"
        assert retry.json()["audio_replay_count"] == 3
        for attempt_id, value in answers[1:]:
            response = await parent.post(
                f"/api/v1/children/{child_id}/english/sessions/{practice.json()['session_id']}/attempts/{attempt_id}/answer",
                json={"submitted_answer": value, "hint_used": False, "audio_replays": 4},
            )
            assert response.status_code == 200, response.text
        async with session_factory() as db:
            raw = await db.get(EnglishExerciseAttempt, uuid.UUID(first_id))
            assert raw is not None
            assert raw.first_answer == wrong and raw.submitted_answer == expected
            assert raw.attempt_count == 2 and raw.audio_replay_count == 3
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(LearningRecord)
                    .where(LearningRecord.session_id == uuid.UUID(practice.json()["session_id"]))
                )
                == 1
            )

        today_after = await parent.get(f"/api/v1/children/{child_id}/english/today")
        assert today_after.json()["completed_count"] == 1
        history = await parent.get(f"/api/v1/children/{child_id}/english/history")
        assert history.status_code == 200
        assert history.json()["items"][0]["actor_display_name"] == "英语爸爸"

        assessment = await parent.post(
            f"/api/v1/children/{child_id}/english/sessions",
            json={
                "knowledge_point_id": item_id,
                "mode": "assessment",
                "exercise_count": 3,
                "dimension": "meaning",
                "seed": 29,
            },
        )
        assert assessment.status_code == 201, assessment.text
        for attempt_id, value in await answers_for_session(
            session_factory, assessment.json()["session_id"]
        ):
            response = await parent.post(
                f"/api/v1/children/{child_id}/english/sessions/{assessment.json()['session_id']}/attempts/{attempt_id}/answer",
                json={"submitted_answer": value, "hint_used": False, "audio_replays": 3},
            )
            assert response.status_code == 200, response.text
        async with session_factory() as db:
            schedule = await db.scalar(
                select(ChildReviewSchedule).where(
                    ChildReviewSchedule.child_id == uuid.UUID(child_id),
                    ChildReviewSchedule.knowledge_point_id == uuid.UUID(item_id),
                )
            )
            assert schedule is not None and schedule.algorithm_version == "english-review-v1"
            state = await db.scalar(
                select(ChildKnowledgeState).where(
                    ChildKnowledgeState.child_id == uuid.UUID(child_id),
                    ChildKnowledgeState.knowledge_point_id == uuid.UUID(item_id),
                )
            )
            assert state is not None and state.policy_key == "english-word-v1"

        observation = await parent.post(
            f"/api/v1/children/{child_id}/english/items/{item_id}/speaking-observations",
            json={"observation": "willing_to_repeat"},
        )
        assert observation.status_code == 201 and observation.json()["dimension"] == "speaking"
        phonics_id = str(stable_english_point_id("english:phonics:consonant-m"))
        generic = await parent.post(
            f"/api/v1/children/{child_id}/assessment-sessions",
            json={
                "source": "phase19_bypass_check",
                "assessment_kind": "practice_check",
                "items": [{"knowledge_point_id": phonics_id, "outcome": "correct"}],
            },
        )
        assert generic.status_code == 422
        assert "English exercise session" in generic.json()["detail"]


async def test_family_sharing_sibling_and_system_admin_isolation(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await import_catalog(session_factory)
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as father,
        httpx.AsyncClient(transport=transport, base_url="http://test") as mother,
        httpx.AsyncClient(transport=transport, base_url="http://test") as stranger,
        httpx.AsyncClient(transport=transport, base_url="http://test") as admin,
    ):
        await register(father, "phase19-father@example.com", "爸爸")
        mother_payload = await register(mother, "phase19-mother@example.com", "妈妈")
        await register(stranger, "phase19-stranger@example.com", "陌生家长")
        admin_payload = await register(admin, "phase19-admin@example.com", "系统管理员")
        async with session_factory() as db:
            user = await db.get(User, uuid.UUID(admin_payload["id"]))
            assert user is not None
            user.system_role = SystemRole.ADMIN
            await db.commit()
        family, child = await create_family_child(father, name="大毛")
        sibling = (
            await father.post(
                f"/api/v1/families/{family['id']}/children",
                json={"display_name": "老二", "birth_date": "2023-01-01"},
            )
        ).json()
        invitation = await father.post(
            f"/api/v1/families/{family['id']}/invitations",
            json={
                "email_constraint": "phase19-mother@example.com",
                "role_to_grant": "companion",
                "expires_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            },
        )
        assert invitation.status_code == 201
        assert (
            await mother.post(
                "/api/v1/family-invitations/accept",
                json={"invitation_code": invitation.json()["invitation_code"]},
            )
        ).status_code == 200
        word_id = str(stable_english_point_id("english:word:cat"))
        practice = await father.post(
            f"/api/v1/children/{child['id']}/english/sessions",
            json={
                "knowledge_point_id": word_id,
                "mode": "practice",
                "exercise_count": 1,
                "seed": 1,
            },
        )
        assert practice.status_code == 201
        attempt_id, expected = (
            await answers_for_session(session_factory, practice.json()["session_id"])
        )[0]
        assert (
            await father.post(
                f"/api/v1/children/{child['id']}/english/sessions/{practice.json()['session_id']}/attempts/{attempt_id}/answer",
                json={"submitted_answer": expected, "hint_used": False},
            )
        ).status_code == 200
        shared = await mother.get(f"/api/v1/children/{child['id']}/english/history")
        assert (
            shared.status_code == 200 and shared.json()["items"][0]["actor_display_name"] == "爸爸"
        )
        sibling_overview = await father.get(f"/api/v1/children/{sibling['id']}/english/overview")
        assert sibling_overview.status_code == 200 and sibling_overview.json()["learned"] == 0
        assert (
            await stranger.get(f"/api/v1/children/{child['id']}/english/history")
        ).status_code == 404
        assert (
            await admin.get(f"/api/v1/children/{child['id']}/english/history")
        ).status_code == 404

        members = await father.get(f"/api/v1/families/{family['id']}/members")
        mother_member = next(
            item for item in members.json() if item["user"]["id"] == mother_payload["id"]
        )
        removed = await father.delete(
            f"/api/v1/families/{family['id']}/members/{mother_member['id']}"
        )
        assert removed.status_code == 204
        assert (
            await mother.get(f"/api/v1/children/{child['id']}/english/history")
        ).status_code == 404


async def test_admin_can_filter_edit_archive_restore_and_import(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await import_catalog(session_factory)
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as admin:
        payload = await register(admin, "phase19-content-admin@example.com", "英语管理员")
        async with session_factory() as db:
            user = await db.get(User, uuid.UUID(payload["id"]))
            assert user is not None
            user.system_role = SystemRole.ADMIN
            await db.commit()
        listing = await admin.get("/api/v1/admin/english?kind=word&category=animals&search=cat")
        assert listing.status_code == 200 and listing.json()["total"] == 1
        item = listing.json()["items"][0]
        archived = await admin.patch(
            f"/api/v1/admin/english/{item['knowledge_point_id']}",
            json={"status": "archived", "parent_tip": "管理后台维护的亲子提示"},
        )
        assert archived.status_code == 200
        assert archived.json()["status"] == "archived"
        assert archived.json()["parent_tip"] == "管理后台维护的亲子提示"
        public = await admin.get("/api/v1/english/items?kind=word&page_size=250")
        assert public.status_code == 200 and public.json()["total"] == 131
        restored = await admin.patch(
            f"/api/v1/admin/english/{item['knowledge_point_id']}", json={"status": "active"}
        )
        assert restored.status_code == 200 and restored.json()["status"] == "active"
        imported = await admin.post("/api/v1/admin/english/import-foundation")
        assert imported.status_code == 200, imported.text
        assert imported.json()["catalog_size"] == 217
