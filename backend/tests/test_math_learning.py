"""Phase 18 catalog, generator, evidence, mastery, isolation, and regression tests."""

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
    LearningRecord,
    MathCatalogRelease,
    MathExerciseAttempt,
    MathProblemTemplate,
    MathSkill,
    PinyinItem,
    SystemRole,
    User,
)
from app.services.mastery import MathMasteryPolicy, mastery_policy_for_type
from app.services.math_catalog import (
    MATH_CATALOG_VERSION,
    MATH_COURSE_KEY,
    MATH_GENERATOR_VERSION,
    MATH_SKILL_SEEDS,
    import_math_foundation,
    math_catalog_counts,
    stable_math_point_id,
)
from app.services.math_problem_generator import math_problem_generators
from app.services.story_generation import build_mastery_snapshot

pytestmark = pytest.mark.anyio
PASSWORD = "phase-18-tests-only"


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
    client: httpx.AsyncClient, *, name: str = "数学孩子"
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
        result = await import_math_foundation(session)
        assert result.errors == []


async def answers_for_session(
    session_factory: async_sessionmaker[AsyncSession], session_id: str
) -> list[tuple[str, object]]:
    async with session_factory() as session:
        attempts = list(
            (
                await session.scalars(
                    select(MathExerciseAttempt)
                    .where(MathExerciseAttempt.session_id == uuid.UUID(session_id))
                    .order_by(MathExerciseAttempt.created_at, MathExerciseAttempt.id)
                )
            ).all()
        )
        return [(str(attempt.id), attempt.expected_answer) for attempt in attempts]


def math_assessment(
    when: datetime,
    representation: str,
    *,
    outcome: str = "correct",
    hint_used: bool = False,
    correct_problems: int = 2,
) -> AssessmentItem:
    return AssessmentItem(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        child_id=uuid.uuid4(),
        knowledge_point_id=uuid.uuid4(),
        evaluator_user_id=uuid.uuid4(),
        outcome=outcome,
        hint_used=hint_used,
        skill_dimension="independent",
        evidence_metadata={
            "representations": [representation],
            "first_answer_correct_count": correct_problems,
            "problem_count": correct_problems,
        },
        assessed_at=when,
    )


async def test_catalog_has_stable_skill_ids_templates_relations_and_course(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        first = await import_math_foundation(session)
        assert first.errors == []
        assert first.catalog_size == 68
        assert first.created == 68
        assert first.template_count == 151
        assert first.templates_created == 153
        assert first.relations_created == 13
        assert first.course_created is True
        assert await math_catalog_counts(session) == {
            "classification": 4,
            "quantity": 10,
            "number_symbol": 14,
            "comparison": 4,
            "sequence": 4,
            "composition": 9,
            "operation": 6,
            "pattern": 3,
            "geometry": 6,
            "spatial": 4,
            "measurement": 4,
        }
        rows = (
            await session.execute(
                select(KnowledgePoint, MathSkill).join(MathSkill).order_by(MathSkill.order_index)
            )
        ).all()
        assert len(rows) == len(MATH_SKILL_SEEDS) == 68
        assert len({point.canonical_key for point, _skill in rows}) == 68
        assert all(point.subject == "math" and point.type == "math_skill" for point, _ in rows)
        assert all(point.id == stable_math_point_id(point.canonical_key) for point, _ in rows)
        front_behind = next(
            point for point, _skill in rows if point.canonical_key == "math:spatial:front-behind"
        )
        assert front_behind.status == "archived"
        front_templates = list(
            await session.scalars(
                select(MathProblemTemplate).where(
                    MathProblemTemplate.knowledge_point_id == front_behind.id
                )
            )
        )
        assert front_templates and all(
            template.status == "archived" for template in front_templates
        )
        original_order = [point.canonical_key for point, _skill in rows]
        original_ids = {point.canonical_key: point.id for point, _skill in rows}

        second = await import_math_foundation(session)
        assert second.errors == []
        assert second.created == second.updated == second.templates_created == 0
        assert second.relations_created == 0
        assert second.skipped == 68 and second.course_created is False
        reloaded = (
            await session.execute(
                select(KnowledgePoint, MathSkill).join(MathSkill).order_by(MathSkill.order_index)
            )
        ).all()
        assert [point.canonical_key for point, _skill in reloaded] == original_order
        assert {point.canonical_key: point.id for point, _skill in reloaded} == original_ids
        assert await session.scalar(select(func.count()).select_from(KnowledgeRelation)) == 13
        release = await session.scalar(select(MathCatalogRelease))
        assert release is not None
        assert release.catalog_version == MATH_CATALOG_VERSION
        assert release.item_count == 68 and release.template_count == 151
        course = await session.scalar(select(Course).where(Course.system_key == MATH_COURSE_KEY))
        assert course is not None and course.subject == "math"
        units = list(
            await session.scalars(
                select(CourseUnit)
                .where(CourseUnit.course_id == course.id)
                .order_by(CourseUnit.order_index)
            )
        )
        assert len(units) == 19
        assert units[0].title == "配对、一样和不一样"
        assert units[-1].title == "综合生活数学"


async def test_generator_is_reproducible_valid_and_not_position_hardcoded(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await import_math_foundation(session)
        templates = list(await session.scalars(select(MathProblemTemplate)))
        assert {template.config_json["generator_key"] for template in templates} >= {
            "quantity_choice_v1",
            "numeral_quantity_match_v1",
            "compare_quantity_v1",
            "number_sequence_v1",
            "composition_v1",
            "joining_v1",
            "taking_away_v1",
            "pattern_v1",
            "shape_choice_v1",
        }
        for template in templates:
            first = math_problem_generators.generate(template, 18376)
            second = math_problem_generators.generate(template, 18376)
            assert first == second
            assert first.generator_version == MATH_GENERATOR_VERSION
            option_values = [option["value"] for option in first.render_payload["options"]]
            assert option_values.count(first.expected_answer) == 1
        subtraction = next(
            item for item in templates if item.config_json["generator_key"] == "taking_away_v1"
        )
        answer_positions = set()
        snapshots = set()
        for seed in range(20):
            generated = math_problem_generators.generate(subtraction, seed)
            visual = generated.render_payload["visual"]
            assert int(visual["start_count"]) >= int(visual["removed_count"])
            assert int(generated.expected_answer) >= 0
            options = [option["value"] for option in generated.render_payload["options"]]
            assert len(options) == len(set(options)) == 3
            answer_positions.add(options.index(generated.expected_answer))
            snapshots.add(str(generated.render_payload))
        assert len(answer_positions) > 1
        assert len(snapshots) > 1

        classification = next(
            item
            for item in templates
            if item.config_json["skill_code"] == "classification:sort-by-shape"
        )
        classification_positions = set()
        for seed in range(20):
            generated = math_problem_generators.generate(classification, seed)
            values = [option["value"] for option in generated.render_payload["options"]]
            classification_positions.add(values.index(generated.expected_answer))
        assert len(classification_positions) > 1

        numeral_zero = next(
            item
            for item in templates
            if item.config_json["skill_code"] == "number_symbol:recognize-0"
        )
        zero = math_problem_generators.generate(numeral_zero, 18)
        assert zero.render_payload["visual"]["numeral"] == 0
        assert zero.render_payload["visual"]["empty_meaning"] is True


async def test_child_visual_contracts_zero_policy_and_spatial_tokens(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await import_math_foundation(session)
        templates = list(await session.scalars(select(MathProblemTemplate)))

        comparisons = [
            item
            for item in templates
            if item.config_json["generator_key"] == "compare_quantity_v1"
            and item.config_json.get("relation") != "equal"
        ]
        assert comparisons
        for seed in range(100):
            generated = math_problem_generators.generate(comparisons[seed % len(comparisons)], seed)
            visual = generated.render_payload["visual"]
            assert int(visual["left_count"]) >= 1
            assert int(visual["right_count"]) >= 1
            assert visual["left_count"] != visual["right_count"]
            assert {option["value"] for option in generated.render_payload["options"]} == {
                "left",
                "right",
            }

        for template in templates:
            generator_key = template.config_json["generator_key"]
            generated = math_problem_generators.generate(template, 29)
            visual = generated.render_payload["visual"]
            if generator_key in {"quantity_choice_v1", "numeral_quantity_match_v1"}:
                if "count" in visual:
                    assert int(visual["count"]) >= 1
                if generator_key == "numeral_quantity_match_v1":
                    assert all(
                        int(option["count"]) >= 1 for option in generated.render_payload["options"]
                    )
            if generator_key == "composition_v1":
                assert all(int(value) >= 1 for value in visual["groups"])
            if generator_key == "joining_v1":
                assert int(visual["first_count"]) >= 1
                assert int(visual["second_count"]) >= 1
            if generator_key == "taking_away_v1":
                assert int(visual["start_count"]) >= 2
                assert 1 <= int(visual["removed_count"]) < int(visual["start_count"])
                assert int(visual["remaining_count"]) >= 1

        zero_template = next(
            item
            for item in templates
            if item.config_json["skill_code"] == "number_symbol:recognize-0"
        )
        zero = math_problem_generators.generate(zero_template, 8)
        assert zero.render_payload["visual"] == {
            "numeral": 0,
            "empty_meaning": True,
            "aria_label": "盘子里一个也没有，用0表示",
        }

        for relation in ("up-down", "left-right", "inside-outside"):
            spatial = next(
                item for item in templates if item.config_json.get("relation") == relation
            )
            generated = math_problem_generators.generate(spatial, 31)
            objects = generated.render_payload["visual"]["objects"]
            options = generated.render_payload["options"]
            assert {value["key"] for value in objects} == {"a", "b"}
            assert {value["shape"] for value in objects} == {"circle", "square"}
            assert all(
                {"key", "shape", "color", "size", "label"} <= value.keys() for value in objects
            )
            assert {option["token"]["key"] for option in options} == {
                value["key"] for value in objects
            }
            assert all(
                option["token"]
                == next(value for value in objects if value["key"] == option["token"]["key"])
                for option in options
            )

        token_fields = {"key", "shape", "color", "size", "label"}
        for generator_key in (
            "pattern_v1",
            "shape_choice_v1",
            "classification_v1",
            "measurement_compare_v1",
        ):
            matching = [
                item for item in templates if item.config_json["generator_key"] == generator_key
            ]
            assert matching
            for template in matching:
                generated = math_problem_generators.generate(template, 47)
                payload = generated.render_payload
                option_tokens = [
                    option["token"] for option in payload["options"] if "token" in option
                ]
                assert all(token_fields <= token.keys() for token in option_tokens)
                if generator_key in {"pattern_v1", "measurement_compare_v1"}:
                    visual_tokens = payload["visual"].get("sequence") or payload["visual"].get(
                        "objects"
                    )
                    assert visual_tokens and all(
                        token_fields <= token.keys() for token in visual_tokens
                    )


def test_math_policy_is_independent_varied_and_cross_day() -> None:
    policy = mastery_policy_for_type("math_skill")
    assert isinstance(policy, MathMasteryPolicy)
    assert policy.key == "math-v1"
    assert mastery_policy_for_type("chinese_character").key == "chinese-character-v1"
    assert mastery_policy_for_type("pinyin_initial").key == "pinyin-v1"
    start = datetime(2026, 8, 1, 8, tzinfo=UTC)
    same_day = [math_assessment(start + timedelta(minutes=index), "dots") for index in range(5)]
    projection = policy.recompute([], same_day, knowledge_type="math_skill")
    assert projection.state_code == "proficient"
    assert projection.dimensions_json["transfer"] == "practicing"

    stable = [
        math_assessment(start, "dots"),
        math_assessment(start + timedelta(days=3), "objects"),
        math_assessment(start + timedelta(days=8), "story"),
    ]
    projection = policy.recompute([], stable, knowledge_type="math_skill")
    assert projection.state_code == "stable"
    assert projection.dimensions_json["transfer"] == "stable"

    hinted = [
        math_assessment(
            start + timedelta(days=day),
            representation,
            outcome="hinted_correct",
            hint_used=True,
        )
        for day, representation in ((0, "dots"), (3, "objects"), (8, "story"))
    ]
    projection = policy.recompute([], hinted, knowledge_type="math_skill")
    assert projection.state_code == "practicing"
    assert projection.dimensions_json["independent"] == "unlearned"

    same_representation = [
        math_assessment(start + timedelta(days=day), "dots") for day in (0, 3, 8)
    ] + [
        math_assessment(
            start + timedelta(days=day),
            representation,
            outcome="hinted_correct",
            hint_used=True,
        )
        for day, representation in ((4, "objects"), (7, "story"))
    ]
    projection = policy.recompute([], same_representation, knowledge_type="math_skill")
    assert projection.state_code == "proficient"
    assert projection.dimensions_json["transfer"] == "practicing"
    assert projection.dimensions_json["representation"]["independent_types"] == ["dots"]


async def test_practice_and_assessment_preserve_distinct_evidence(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await import_catalog(session_factory)
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as parent:
        await register(parent, "phase18-parent@example.com", "数学爸爸")
        _, child = await create_family_child(parent)
        child_id = child["id"]
        listing = await parent.get(f"/api/v1/children/{child_id}/math/skills?page_size=100")
        assert listing.status_code == 200 and listing.json()["total"] == 67
        skill_id = next(
            item["knowledge_point_id"]
            for item in listing.json()["items"]
            if item["canonical_key"] == "math:quantity:count-within-3"
        )
        detail = await parent.get(f"/api/v1/children/{child_id}/math/skills/{skill_id}")
        assert detail.status_code == 200
        assert detail.json()["policy_key"] == "math-v1"
        assert detail.json()["templates"]
        assert detail.json()["common_difficulties"]
        today = await parent.get(f"/api/v1/children/{child_id}/math/today")
        assert today.status_code == 200 and today.json()["target_count"] == 1
        today_skill_id = today.json()["items"][0]["knowledge_point_id"]

        practice = await parent.post(
            f"/api/v1/children/{child_id}/math/sessions",
            json={
                "knowledge_point_id": skill_id,
                "mode": "practice",
                "problem_count": 3,
                "seed": 18376,
                "dimension": "understanding",
            },
        )
        assert practice.status_code == 201, practice.text
        practice_json = practice.json()
        answers = await answers_for_session(session_factory, practice_json["session_id"])
        first_id, first_expected = answers[0]
        wrong = int(first_expected) + 20 if isinstance(first_expected, int) else "not-the-answer"
        first_try = await parent.post(
            f"/api/v1/children/{child_id}/math/sessions/{practice_json['session_id']}/attempts/{first_id}/answer",
            json={"submitted_answer": wrong, "hint_used": False},
        )
        assert first_try.status_code == 200 and first_try.json()["outcome"] == "incorrect"
        retry = await parent.post(
            f"/api/v1/children/{child_id}/math/sessions/{practice_json['session_id']}/attempts/{first_id}/answer",
            json={"submitted_answer": first_expected, "hint_used": True},
        )
        assert retry.status_code == 200
        assert retry.json()["outcome"] == "uncertain"
        for attempt_id, expected in answers[1:]:
            response = await parent.post(
                f"/api/v1/children/{child_id}/math/sessions/{practice_json['session_id']}/attempts/{attempt_id}/answer",
                json={"submitted_answer": expected, "hint_used": False},
            )
            assert response.status_code == 200, response.text

        async with session_factory() as db:
            attempts = list(
                await db.scalars(
                    select(MathExerciseAttempt).where(
                        MathExerciseAttempt.session_id == uuid.UUID(practice_json["session_id"])
                    )
                )
            )
            first = next(item for item in attempts if str(item.id) == first_id)
            assert first.first_answer == wrong
            assert first.submitted_answer == first_expected
            assert first.attempt_count == 2 and first.hint_used is True
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(LearningRecord)
                    .where(LearningRecord.session_id == uuid.UUID(practice_json["session_id"]))
                )
                == 1
            )
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(AssessmentItem)
                    .where(AssessmentItem.session_id == uuid.UUID(practice_json["session_id"]))
                )
                == 0
            )
            state = await db.scalar(
                select(ChildKnowledgeState).where(
                    ChildKnowledgeState.child_id == uuid.UUID(child_id),
                    ChildKnowledgeState.knowledge_point_id == uuid.UUID(skill_id),
                )
            )
            assert state is not None and state.state_code == "introduced"

        assessment = await parent.post(
            f"/api/v1/children/{child_id}/math/sessions",
            json={
                "knowledge_point_id": skill_id,
                "mode": "assessment",
                "problem_count": 3,
                "seed": 300,
                "dimension": "independent",
            },
        )
        assert assessment.status_code == 201
        assessment_json = assessment.json()
        for attempt_id, expected in await answers_for_session(
            session_factory, assessment_json["session_id"]
        ):
            response = await parent.post(
                f"/api/v1/children/{child_id}/math/sessions/{assessment_json['session_id']}/attempts/{attempt_id}/answer",
                json={"submitted_answer": expected, "hint_used": False},
            )
            assert response.status_code == 200, response.text

        async with session_factory() as db:
            assessment_item = await db.scalar(
                select(AssessmentItem).where(
                    AssessmentItem.session_id == uuid.UUID(assessment_json["session_id"])
                )
            )
            assert assessment_item is not None
            assert assessment_item.outcome == "correct"
            assert assessment_item.evidence_metadata["problem_count"] == 3
            assert assessment_item.evidence_metadata["first_answer_correct_count"] == 3
            assert assessment_item.evidence_metadata["representations"]
            schedule = await db.scalar(
                select(ChildReviewSchedule).where(
                    ChildReviewSchedule.child_id == uuid.UUID(child_id),
                    ChildReviewSchedule.knowledge_point_id == uuid.UUID(skill_id),
                )
            )
            assert schedule is not None and schedule.algorithm_version == "math-review-v1"
        history = await parent.get(f"/api/v1/children/{child_id}/math/history")
        assert history.status_code == 200
        assert {item["mode"] for item in history.json()["items"]} == {
            "practice",
            "assessment",
        }
        assert {item["actor_display_name"] for item in history.json()["items"]} == {"数学爸爸"}

        offline = await parent.post(
            f"/api/v1/children/{child_id}/math/skills/{skill_id}/offline-observations",
            json={"outcome": "hinted_correct"},
        )
        assert offline.status_code == 201, offline.text
        assert offline.json()["outcome"] == "hinted_correct"
        history = await parent.get(f"/api/v1/children/{child_id}/math/history")
        assert {item["mode"] for item in history.json()["items"]} == {
            "practice",
            "assessment",
            "offline",
        }

        today_practice = await parent.post(
            f"/api/v1/children/{child_id}/math/sessions",
            json={
                "knowledge_point_id": today_skill_id,
                "mode": "practice",
                "problem_count": 1,
                "seed": 42,
                "dimension": "understanding",
            },
        )
        assert today_practice.status_code == 201, today_practice.text
        today_attempt, today_expected = (
            await answers_for_session(session_factory, today_practice.json()["session_id"])
        )[0]
        today_answer = await parent.post(
            f"/api/v1/children/{child_id}/math/sessions/{today_practice.json()['session_id']}/attempts/{today_attempt}/answer",
            json={"submitted_answer": today_expected, "hint_used": False},
        )
        assert today_answer.status_code == 200, today_answer.text
        today_after = await parent.get(f"/api/v1/children/{child_id}/math/today")
        assert today_after.json()["completed_count"] == 1
        assert today_after.json()["status"] == "completed"


async def test_family_sharing_sibling_admin_and_story_isolation(
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
        await register(father, "phase18-father@example.com", "爸爸")
        mother_payload = await register(mother, "phase18-mother@example.com", "妈妈")
        await register(stranger, "phase18-stranger@example.com", "陌生家长")
        admin_payload = await register(admin, "phase18-admin@example.com", "系统管理员")
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
        await create_family_child(stranger, name="别家孩子")
        invitation = await father.post(
            f"/api/v1/families/{family['id']}/invitations",
            json={
                "email_constraint": "phase18-mother@example.com",
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
        skill_id = str(stable_math_point_id("math:quantity:recognize-1"))
        practice = await father.post(
            f"/api/v1/children/{child['id']}/math/sessions",
            json={
                "knowledge_point_id": skill_id,
                "mode": "practice",
                "problem_count": 1,
                "seed": 1,
                "dimension": "understanding",
            },
        )
        assert practice.status_code == 201
        attempt_id, expected = (
            await answers_for_session(session_factory, practice.json()["session_id"])
        )[0]
        assert (
            await father.post(
                f"/api/v1/children/{child['id']}/math/sessions/{practice.json()['session_id']}/attempts/{attempt_id}/answer",
                json={"submitted_answer": expected, "hint_used": False},
            )
        ).status_code == 200
        shared = await mother.get(f"/api/v1/children/{child['id']}/math/overview")
        assert shared.status_code == 200 and shared.json()["learned"] == 1
        sibling_overview = await father.get(f"/api/v1/children/{sibling['id']}/math/overview")
        assert sibling_overview.status_code == 200 and sibling_overview.json()["learned"] == 0
        assert (
            await stranger.get(f"/api/v1/children/{child['id']}/math/history")
        ).status_code == 404
        assert (
            await stranger.post(
                f"/api/v1/children/{child['id']}/math/skills/{skill_id}/offline-observations",
                json={"outcome": "correct"},
            )
        ).status_code == 404
        assert (await admin.get(f"/api/v1/children/{child['id']}/math/history")).status_code == 404
        history = await mother.get(f"/api/v1/children/{child['id']}/math/history")
        assert history.status_code == 200
        assert history.json()["items"][0]["actor_display_name"] == "爸爸"

        members = await father.get(f"/api/v1/families/{family['id']}/members")
        assert members.status_code == 200
        mother_member = next(
            item for item in members.json() if item["user"]["id"] == mother_payload["id"]
        )
        removed = await father.delete(
            f"/api/v1/families/{family['id']}/members/{mother_member['id']}"
        )
        assert removed.status_code == 204
        assert (await mother.get(f"/api/v1/children/{child['id']}/math/history")).status_code == 404

        async with session_factory() as db:
            assert await db.scalar(select(func.count()).select_from(PinyinItem)) == 0
            snapshot = await build_mastery_snapshot(db, uuid.UUID(child["id"]))
            assert snapshot.catalog_size == 0 and snapshot.characters == ()


async def test_admin_math_can_filter_archive_restore_and_import(
    test_app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await import_catalog(session_factory)
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as admin:
        payload = await register(admin, "phase18-content-admin@example.com", "数学管理员")
        async with session_factory() as db:
            user = await db.get(User, uuid.UUID(payload["id"]))
            assert user is not None
            user.system_role = SystemRole.ADMIN
            await db.commit()
        listing = await admin.get("/api/v1/admin/math?domain=quantity&search=数清")
        assert listing.status_code == 200 and listing.json()["items"]
        item = listing.json()["items"][0]
        archived = await admin.patch(
            f"/api/v1/admin/math/{item['knowledge_point_id']}",
            json={"status": "archived", "parent_tip": "管理后台维护提示"},
        )
        assert archived.status_code == 200
        assert archived.json()["status"] == "archived"
        assert archived.json()["parent_tip"] == "管理后台维护提示"
        public = await admin.get("/api/v1/math/skills?page_size=100")
        assert public.status_code == 200 and public.json()["total"] == 66
        restored = await admin.patch(
            f"/api/v1/admin/math/{item['knowledge_point_id']}", json={"status": "active"}
        )
        assert restored.status_code == 200 and restored.json()["status"] == "active"
        imported = await admin.post("/api/v1/admin/math/import-foundation")
        assert imported.status_code == 200, imported.text
        assert imported.json()["created"] == 0
        assert imported.json()["catalog_size"] == 68
        assert imported.json()["template_count"] == 151
