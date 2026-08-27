"""Phase 17 canonical catalog, learning evidence, policy, and isolation boundaries."""

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
    KnowledgePoint,
    KnowledgeRelation,
    PinyinCatalogRelease,
    PinyinItem,
    PinyinPracticeItem,
    SystemRole,
    User,
)
from app.services.mastery import PinyinMasteryPolicy, mastery_policy_for_type
from app.services.pinyin_catalog import (
    PINYIN_CATALOG_VERSION,
    PINYIN_COURSE_KEY,
    apply_tone_mark,
    import_pinyin_foundation,
    normalize_pinyin,
    pinyin_catalog_counts,
    spell_blend,
    strip_tone_marks,
)
from app.services.story_generation import build_mastery_snapshot

pytestmark = pytest.mark.anyio
PASSWORD = "phase-17-tests-only"


async def register(client: httpx.AsyncClient, email: str, name: str) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": name, "password": PASSWORD},
    )
    assert response.status_code == 201, response.text
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200
    return response.json()


async def create_family_child(
    client: httpx.AsyncClient, *, name: str = "拼音孩子"
) -> tuple[dict, dict]:
    family_response = await client.post("/api/v1/families", json={"name": f"{name}家庭"})
    assert family_response.status_code == 201, family_response.text
    family = family_response.json()
    child_response = await client.post(
        f"/api/v1/families/{family['id']}/children",
        json={"display_name": name, "birth_date": "2021-08-28"},
    )
    assert child_response.status_code == 201, child_response.text
    return family, child_response.json()


async def import_catalog(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        result = await import_pinyin_foundation(session)
        assert result.errors == []


async def make_system_admin(
    client: httpx.AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> dict:
    payload = await register(client, "phase17-admin@example.com", "拼音管理员")
    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(payload["id"]))
        assert user is not None
        user.system_role = SystemRole.ADMIN
        await session.commit()
    return payload


async def point_id(
    session_factory: async_sessionmaker[AsyncSession], canonical_key: str
) -> uuid.UUID:
    async with session_factory() as session:
        value = await session.scalar(
            select(KnowledgePoint.id).where(KnowledgePoint.canonical_key == canonical_key)
        )
        assert value is not None
        return value


def assessment(dimension: str, when: datetime, outcome: str = "correct") -> AssessmentItem:
    return AssessmentItem(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        child_id=uuid.uuid4(),
        knowledge_point_id=uuid.uuid4(),
        evaluator_user_id=uuid.uuid4(),
        outcome=outcome,
        skill_dimension=dimension,
        assessed_at=when,
    )


async def test_catalog_is_complete_versioned_and_idempotent(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        first = await import_pinyin_foundation(session)
        assert first.errors == []
        assert first.catalog_size == 68
        assert first.created == 68
        assert first.practices_created == 18
        assert first.relations_created == 16
        assert first.course_created is True
        counts = await pinyin_catalog_counts(session)
        assert counts == {"initial": 23, "final": 24, "tone": 5, "whole": 16}
        canonical_keys = list(
            await session.scalars(
                select(KnowledgePoint.canonical_key)
                .join(PinyinItem)
                .order_by(PinyinItem.order_index)
            )
        )
        assert len(canonical_keys) == len(set(canonical_keys)) == 68
        assert "chinese:pinyin:initial:zh" in canonical_keys
        assert "chinese:pinyin:final:ü" in canonical_keys
        assert "chinese:pinyin:tone:neutral" in canonical_keys
        assert "chinese:pinyin:whole:ying" in canonical_keys
        original_ids = dict(
            (
                await session.execute(
                    select(KnowledgePoint.canonical_key, KnowledgePoint.id).join(PinyinItem)
                )
            ).all()
        )

        second = await import_pinyin_foundation(session)
        assert second.errors == []
        assert second.created == second.updated == second.relations_created == 0
        assert second.practices_created == 0
        assert second.skipped == 68
        assert second.course_created is False
        assert original_ids == dict(
            (
                await session.execute(
                    select(KnowledgePoint.canonical_key, KnowledgePoint.id).join(PinyinItem)
                )
            ).all()
        )
        assert await session.scalar(select(func.count()).select_from(PinyinPracticeItem)) == 18
        assert await session.scalar(select(func.count()).select_from(KnowledgeRelation)) == 16
        release = await session.scalar(select(PinyinCatalogRelease))
        assert release is not None
        assert release.catalog_version == PINYIN_CATALOG_VERSION
        assert release.item_count == 68 and release.practice_item_count == 18
        course = await session.scalar(select(Course).where(Course.system_key == PINYIN_COURSE_KEY))
        assert course is not None and course.subject == "chinese"
        units = list(
            await session.scalars(
                select(CourseUnit)
                .where(CourseUnit.course_id == course.id)
                .order_by(CourseUnit.order_index)
            )
        )
        assert len(units) == 16
        assert units[0].title == "a o e · 四声初体验"
        assert units[-1].title == "综合拼读"


def test_pinyin_normalization_tone_marks_and_umlaut_rules() -> None:
    assert normalize_pinyin("v") == "ü"
    assert normalize_pinyin("u:") == "ü"
    assert normalize_pinyin("LU:E") == "lüe"
    assert strip_tone_marks("nǚ") == "nü"
    assert apply_tone_mark("a", 1) == "ā"
    assert apply_tone_mark("gui", 3) == "guǐ"
    assert apply_tone_mark("liu", 2) == "liú"
    assert apply_tone_mark("lüe", 4) == "lüè"
    assert spell_blend("j", "ü") == ("ü", "u", "ju")
    assert spell_blend("q", "üe") == ("üe", "ue", "que")
    assert spell_blend("x", "ün") == ("ün", "un", "xun")
    assert spell_blend("n", "ü") == ("ü", "ü", "nü")


def test_pinyin_policy_is_independent_multidimensional_and_cross_day() -> None:
    policy = mastery_policy_for_type("pinyin_initial")
    assert isinstance(policy, PinyinMasteryPolicy)
    assert policy.key == "pinyin-v1"
    assert mastery_policy_for_type("chinese_character").key == "chinese-character-v1"
    start = datetime(2026, 8, 1, 8, tzinfo=UTC)

    one_day = [
        *[assessment("recognition", start + timedelta(minutes=index)) for index in range(5)],
        *[assessment("listening", start + timedelta(minutes=10 + index)) for index in range(5)],
    ]
    projection = policy.recompute([], one_day, knowledge_type="pinyin_initial")
    assert projection.state_code == "practicing"
    assert projection.dimensions_json == {
        "recognition": "practicing",
        "listening": "practicing",
    }

    cross_day = [
        assessment("recognition", start),
        assessment("recognition", start + timedelta(days=2)),
        assessment("listening", start),
        assessment("listening", start + timedelta(days=2)),
    ]
    projection = policy.recompute([], cross_day, knowledge_type="pinyin_initial")
    assert projection.state_code == "proficient"

    stable = [
        *[assessment("recognition", start + timedelta(days=day)) for day in (0, 2, 8)],
        *[assessment("listening", start + timedelta(days=day)) for day in (0, 2, 8)],
    ]
    projection = policy.recompute([], stable, knowledge_type="pinyin_initial")
    assert projection.state_code == "stable"
    independent = policy.recompute(
        [],
        [
            *[assessment("recognition", start + timedelta(days=day)) for day in (0, 2, 8)],
            assessment("listening", start),
        ],
        knowledge_type="pinyin_initial",
    )
    assert independent.state_code == "practicing"
    assert independent.dimensions_json["recognition"] == "stable"
    assert independent.dimensions_json["listening"] == "practicing"

    tone = policy.recompute(
        [],
        [
            *[assessment("tone", start + timedelta(days=day)) for day in (0, 2)],
            *[assessment("listening", start + timedelta(days=day)) for day in (0, 2)],
        ],
        knowledge_type="pinyin_tone",
    )
    assert tone.state_code == "proficient"


async def test_admin_can_archive_restore_and_call_specific_import_route(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await import_catalog(session_factory)
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as admin:
        await make_system_admin(admin, session_factory)
        listing = await admin.get("/api/v1/admin/pinyin?kind=initial&search=b")
        assert listing.status_code == 200
        b_item = next(item for item in listing.json()["items"] if item["symbol"] == "b")

        archived = await admin.patch(
            f"/api/v1/admin/pinyin/{b_item['knowledge_point_id']}",
            json={"status": "archived", "parent_tip": "归档测试提示"},
        )
        assert archived.status_code == 200, archived.text
        assert archived.json()["status"] == "archived"
        assert archived.json()["parent_tip"] == "归档测试提示"
        public = await admin.get("/api/v1/pinyin/items?page_size=100")
        assert public.status_code == 200 and public.json()["total"] == 67

        restored = await admin.patch(
            f"/api/v1/admin/pinyin/{b_item['knowledge_point_id']}",
            json={"status": "active"},
        )
        assert restored.status_code == 200 and restored.json()["status"] == "active"
        imported = await admin.post("/api/v1/admin/pinyin/import-foundation")
        assert imported.status_code == 200, imported.text
        assert imported.json()["created"] == 0
        assert imported.json()["catalog_size"] == 68


async def test_child_api_records_all_evidence_and_keeps_character_domains_clean(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await import_catalog(session_factory)
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as parent:
        await register(parent, "phase17-parent@example.com", "拼音爸爸")
        _, child = await create_family_child(parent)
        child_id = child["id"]

        items = await parent.get(f"/api/v1/children/{child_id}/pinyin/items?page_size=100")
        assert items.status_code == 200
        assert items.json()["total"] == 68
        b_id = next(
            item["knowledge_point_id"] for item in items.json()["items"] if item["symbol"] == "b"
        )
        tone_id = next(
            item["knowledge_point_id"]
            for item in items.json()["items"]
            if item["symbol"] == "tone:1"
        )
        detail = await parent.get(f"/api/v1/children/{child_id}/pinyin/items/{b_id}")
        assert detail.status_code == 200
        assert detail.json()["display_text"] == "b"
        assert detail.json()["audio"] == {
            "mode": "tts_fallback",
            "audio_url": None,
            "speech_text": "玻，玻璃的玻。",
        }
        assert len(detail.json()["listening_options"]) == 3
        assert any(item["display_text"] == "p" for item in detail.json()["confusing"])
        assert detail.json()["previous"] is not None and detail.json()["next"] is not None

        practices = await parent.get("/api/v1/pinyin/practices")
        assert practices.status_code == 200 and practices.json()["total"] == 18
        ju = next(item for item in practices.json()["items"] if item["display_syllable"] == "ju")
        assert ju["underlying_final"] == "ü" and ju["display_final"] == "u"

        today = await parent.get(f"/api/v1/children/{child_id}/pinyin/today")
        assert today.status_code == 200
        assert today.json()["target_count"] == len(today.json()["new_items"]) == 3
        today_item_id = today.json()["new_items"][0]["knowledge_point_id"]

        learning = await parent.post(
            f"/api/v1/children/{child_id}/learning-sessions",
            json={
                "source": "pinyin_card",
                "items": [{"knowledge_point_id": today_item_id, "activity_type": "introduced"}],
            },
        )
        assert learning.status_code == 201 and learning.json()["mastery_projection"] == "configured"

        evidence = (
            (b_id, "recognition", "recognition", "correct"),
            (b_id, "listening_check", "listening", "correct"),
            (tone_id, "listening_check", "tone", "correct"),
            (b_id, "practice_check", "blending", "hinted_correct"),
            (b_id, "oral_check", "pronunciation", "correct"),
        )
        for item_id, assessment_kind, dimension, outcome in evidence:
            response = await parent.post(
                f"/api/v1/children/{child_id}/assessment-sessions",
                json={
                    "source": "pinyin_phase17",
                    "assessment_kind": assessment_kind,
                    "items": [
                        {
                            "knowledge_point_id": item_id,
                            "outcome": outcome,
                            "skill_dimension": dimension,
                            "evidence_metadata": {
                                "source": "adult_observation"
                                if dimension == "pronunciation"
                                else "interactive_task"
                            },
                        }
                    ],
                },
            )
            assert response.status_code == 201, response.text

        overview = await parent.get(f"/api/v1/children/{child_id}/pinyin/overview")
        assert overview.status_code == 200
        assert overview.json()["learned"] == 3
        assert overview.json()["blending_attempts"] == 1
        refreshed_today = await parent.get(f"/api/v1/children/{child_id}/pinyin/today")
        assert refreshed_today.json()["completed_count"] == 1

        history = await parent.get(f"/api/v1/children/{child_id}/pinyin/history")
        assert history.status_code == 200
        assert {item["actor_display_name"] for item in history.json()["items"]} == {"拼音爸爸"}
        dimensions = {
            evidence["dimension"]
            for item in history.json()["items"]
            for evidence in item["evidence"]
            if evidence["dimension"]
        }
        assert dimensions >= {"recognition", "listening", "tone", "blending", "pronunciation"}

        character_summary = await parent.get(f"/api/v1/children/{child_id}/characters/summary")
        assert character_summary.status_code == 200
        assert character_summary.json()["total_enabled"] == 0
        assert character_summary.json()["learning_records"] == 0
        assert character_summary.json()["assessment_items"] == 0
        review = await parent.get(f"/api/v1/children/{child_id}/reviews/backlog")
        assert review.status_code == 200 and review.json()["items"] == []
        achievements = await parent.get(f"/api/v1/children/{child_id}/achievements")
        assert achievements.status_code == 200 and achievements.json()["achievements"] == []

        async with session_factory() as session:
            state = await session.scalar(
                select(ChildKnowledgeState).where(
                    ChildKnowledgeState.child_id == uuid.UUID(child_id),
                    ChildKnowledgeState.knowledge_point_id == uuid.UUID(b_id),
                )
            )
            assert state is not None and state.policy_key == "pinyin-v1"
            assert set(state.dimensions_json) == {
                "recognition",
                "listening",
                "blending",
                "pronunciation",
            }
            schedule = await session.scalar(
                select(ChildReviewSchedule).where(
                    ChildReviewSchedule.child_id == uuid.UUID(child_id),
                    ChildReviewSchedule.knowledge_point_id == uuid.UUID(b_id),
                )
            )
            assert schedule is not None and schedule.algorithm_version == "pinyin-review-v1"
            story_snapshot = await build_mastery_snapshot(session, uuid.UUID(child_id))
            assert story_snapshot.catalog_size == 0
            assert story_snapshot.characters == ()


async def test_sibling_and_family_isolation_with_shared_parent_attribution(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await import_catalog(session_factory)
    transport = httpx.ASGITransport(app=test_app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as father,
        httpx.AsyncClient(transport=transport, base_url="http://test") as mother,
        httpx.AsyncClient(transport=transport, base_url="http://test") as stranger,
    ):
        await register(father, "phase17-father@example.com", "爸爸")
        await register(mother, "phase17-mother@example.com", "妈妈")
        await register(stranger, "phase17-stranger@example.com", "陌生家长")
        family, first_child = await create_family_child(father, name="大毛")
        sibling_response = await father.post(
            f"/api/v1/families/{family['id']}/children",
            json={"display_name": "老二", "birth_date": "2023-01-01"},
        )
        assert sibling_response.status_code == 201
        sibling = sibling_response.json()
        await create_family_child(stranger, name="别家孩子")

        invitation = await father.post(
            f"/api/v1/families/{family['id']}/invitations",
            json={
                "email_constraint": "phase17-mother@example.com",
                "role_to_grant": "companion",
                "expires_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            },
        )
        assert invitation.status_code == 201, invitation.text
        accepted = await mother.post(
            "/api/v1/family-invitations/accept",
            json={"invitation_code": invitation.json()["invitation_code"]},
        )
        assert accepted.status_code == 200

        b_id = str(await point_id(session_factory, "chinese:pinyin:initial:b"))
        learned = await father.post(
            f"/api/v1/children/{first_child['id']}/learning-sessions",
            json={
                "source": "pinyin_card",
                "items": [{"knowledge_point_id": b_id, "activity_type": "introduced"}],
            },
        )
        assert learned.status_code == 201
        assessed = await mother.post(
            f"/api/v1/children/{first_child['id']}/assessment-sessions",
            json={
                "source": "pinyin_listening",
                "assessment_kind": "listening_check",
                "items": [
                    {
                        "knowledge_point_id": b_id,
                        "outcome": "correct",
                        "skill_dimension": "listening",
                    }
                ],
            },
        )
        assert assessed.status_code == 201

        shared = await mother.get(f"/api/v1/children/{first_child['id']}/pinyin/overview")
        assert shared.status_code == 200 and shared.json()["learned"] == 1
        sibling_overview = await father.get(f"/api/v1/children/{sibling['id']}/pinyin/overview")
        assert sibling_overview.status_code == 200 and sibling_overview.json()["learned"] == 0
        denied = await stranger.get(f"/api/v1/children/{first_child['id']}/pinyin/items/{b_id}")
        assert denied.status_code == 404

        history = await father.get(f"/api/v1/children/{first_child['id']}/pinyin/history")
        assert history.status_code == 200
        assert {item["actor_display_name"] for item in history.json()["items"]} == {"爸爸", "妈妈"}
