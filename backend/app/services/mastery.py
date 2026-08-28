"""Deterministic mastery projection built only from preserved raw evidence."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssessmentItem,
    AssessmentKind,
    AssessmentOutcome,
    AssessmentSession,
    ChildKnowledgeState,
    KnowledgePoint,
    KnowledgeType,
    LearningRecord,
    MasteryLevel,
)

ALGORITHM_VERSION = "v1"
CHINESE_CHARACTER_POLICY_KEY = "chinese-character-v1"
PINYIN_POLICY_KEY = "pinyin-v1"
PINYIN_DIMENSIONS = frozenset({"recognition", "listening", "tone", "blending", "pronunciation"})
MATH_POLICY_KEY = "math-v1"
MATH_DIMENSIONS = frozenset({"understanding", "independent", "transfer", "representation"})


class MasteryPolicy(Protocol):
    """A bounded projection algorithm for explicitly supported knowledge types."""

    key: str
    supported_knowledge_types: frozenset[str]
    supported_assessment_kinds: frozenset[str]

    def recompute(
        self,
        learning_records: list[LearningRecord],
        assessment_items: list[AssessmentItem],
        *,
        knowledge_type: str | None = None,
    ) -> "MasteryProjection": ...


class MasteryPolicyRegistry:
    """Small explicit registry; unsupported domains intentionally have no projection."""

    def __init__(self) -> None:
        self._by_knowledge_type: dict[str, MasteryPolicy] = {}

    def register(self, policy: MasteryPolicy) -> None:
        for knowledge_type in policy.supported_knowledge_types:
            if knowledge_type in self._by_knowledge_type:
                raise ValueError(f"Mastery policy already registered for {knowledge_type}")
            self._by_knowledge_type[knowledge_type] = policy

    def for_knowledge_type(self, knowledge_type: str) -> MasteryPolicy | None:
        return self._by_knowledge_type.get(knowledge_type)


@dataclass(frozen=True)
class MasteryProjection:
    """Pure, reproducible output of Mastery V1."""

    mastery_level: str
    mastery_score: float
    first_introduced_at: datetime | None
    last_learning_at: datetime | None
    last_assessed_at: datetime | None
    correct_count: int
    hinted_correct_count: int
    uncertain_count: int
    incorrect_count: int
    consecutive_correct: int
    consecutive_incorrect: int
    average_response_time_ms: float | None
    state_code: str | None = None
    dimensions_json: dict[str, object] = field(default_factory=dict)


def project_mastery(
    learning_records: list[LearningRecord], assessment_items: list[AssessmentItem]
) -> MasteryProjection:
    """Apply conservative Mastery V1 without probabilistic or AI inference.

    Evidence weights are correct +1, hinted +0.5, uncertain -0.25 and
    incorrect -0.75. The score is clamped after dividing by four. A stable
    result additionally requires four independent correct answers across at
    least three dates and seven elapsed days, so a single success can never
    imply durable mastery.
    """

    ordered_items = sorted(assessment_items, key=lambda item: (item.assessed_at, str(item.id)))
    counts = {outcome.value: 0 for outcome in AssessmentOutcome}
    consecutive_correct = 0
    consecutive_incorrect = 0
    response_times: list[int] = []
    correct_times: list[datetime] = []

    for item in ordered_items:
        counts[item.outcome] += 1
        if item.response_time_ms is not None:
            response_times.append(item.response_time_ms)
        if item.outcome == AssessmentOutcome.CORRECT:
            correct_times.append(item.assessed_at)
            consecutive_correct += 1
            consecutive_incorrect = 0
        elif item.outcome == AssessmentOutcome.INCORRECT:
            consecutive_incorrect += 1
            consecutive_correct = 0
        else:
            consecutive_correct = 0
            consecutive_incorrect = 0

    weighted_evidence = (
        counts[AssessmentOutcome.CORRECT]
        + 0.5 * counts[AssessmentOutcome.HINTED_CORRECT]
        - 0.25 * counts[AssessmentOutcome.UNCERTAIN]
        - 0.75 * counts[AssessmentOutcome.INCORRECT]
    )
    score = round(min(1.0, max(0.0, weighted_evidence / 4)), 4)
    has_evidence = bool(learning_records or ordered_items)
    level = MasteryLevel.INTRODUCED if has_evidence else MasteryLevel.UNLEARNED

    if (
        counts[AssessmentOutcome.CORRECT] >= 1 or counts[AssessmentOutcome.HINTED_CORRECT] >= 2
    ) and score >= 0.15:
        level = MasteryLevel.RECOGNIZING
    if counts[AssessmentOutcome.CORRECT] >= 3 and consecutive_correct >= 2 and score >= 0.5:
        level = MasteryLevel.PROFICIENT
    if correct_times:
        correct_dates = {item.date() for item in correct_times}
        correct_span_days = (max(correct_times) - min(correct_times)).total_seconds() / 86400
        if (
            counts[AssessmentOutcome.CORRECT] >= 4
            and len(correct_dates) >= 3
            and correct_span_days >= 7
            and consecutive_correct >= 3
            and score >= 0.8
        ):
            level = MasteryLevel.STABLE

    ordered_learning = sorted(
        learning_records, key=lambda record: (record.learned_at, str(record.id))
    )
    return MasteryProjection(
        mastery_level=level,
        mastery_score=score,
        first_introduced_at=ordered_learning[0].learned_at if ordered_learning else None,
        last_learning_at=ordered_learning[-1].learned_at if ordered_learning else None,
        last_assessed_at=ordered_items[-1].assessed_at if ordered_items else None,
        correct_count=counts[AssessmentOutcome.CORRECT],
        hinted_correct_count=counts[AssessmentOutcome.HINTED_CORRECT],
        uncertain_count=counts[AssessmentOutcome.UNCERTAIN],
        incorrect_count=counts[AssessmentOutcome.INCORRECT],
        consecutive_correct=consecutive_correct,
        consecutive_incorrect=consecutive_incorrect,
        average_response_time_ms=(
            round(sum(response_times) / len(response_times), 2) if response_times else None
        ),
    )


class ChineseCharacterMasteryPolicy:
    """Compatibility wrapper around the unchanged Chinese-character V1 algorithm."""

    key = CHINESE_CHARACTER_POLICY_KEY
    supported_knowledge_types = frozenset({KnowledgeType.CHINESE_CHARACTER})
    supported_assessment_kinds = frozenset({AssessmentKind.RECOGNITION})

    def recompute(
        self,
        learning_records: list[LearningRecord],
        assessment_items: list[AssessmentItem],
        *,
        knowledge_type: str | None = None,
    ) -> MasteryProjection:
        del knowledge_type
        return project_mastery(learning_records, assessment_items)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def pinyin_dimension_state(items: list[AssessmentItem]) -> str:
    if not items:
        return "unlearned"
    ordered = sorted(items, key=lambda item: (_utc(item.assessed_at), str(item.id)))
    independent_correct = [item for item in ordered if item.outcome == AssessmentOutcome.CORRECT]
    correct_dates = {_utc(item.assessed_at).date() for item in independent_correct}
    span_days = 0.0
    if independent_correct:
        first = min(_utc(item.assessed_at) for item in independent_correct)
        last = max(_utc(item.assessed_at) for item in independent_correct)
        span_days = (last - first).total_seconds() / 86400
    if (
        len(independent_correct) >= 3
        and len(correct_dates) >= 3
        and span_days >= 7
        and ordered[-1].outcome in {AssessmentOutcome.CORRECT, AssessmentOutcome.HINTED_CORRECT}
    ):
        return "stable"
    if len(independent_correct) >= 2 and len(correct_dates) >= 2:
        return "proficient"
    return "practicing"


class PinyinMasteryPolicy:
    """Deterministic multi-dimensional Pinyin policy with cross-day stability."""

    key = PINYIN_POLICY_KEY
    supported_knowledge_types = frozenset(
        {
            KnowledgeType.PINYIN_INITIAL,
            KnowledgeType.PINYIN_FINAL,
            KnowledgeType.PINYIN_TONE,
            KnowledgeType.PINYIN_SYLLABLE,
        }
    )
    supported_assessment_kinds = frozenset(
        {
            AssessmentKind.RECOGNITION,
            AssessmentKind.PRACTICE_CHECK,
            AssessmentKind.LISTENING_CHECK,
            AssessmentKind.ORAL_CHECK,
        }
    )

    def recompute(
        self,
        learning_records: list[LearningRecord],
        assessment_items: list[AssessmentItem],
        *,
        knowledge_type: str | None = None,
    ) -> MasteryProjection:
        required = (
            ("tone", "listening")
            if knowledge_type == KnowledgeType.PINYIN_TONE
            else ("recognition", "listening")
        )
        by_dimension = {
            dimension: [item for item in assessment_items if item.skill_dimension == dimension]
            for dimension in PINYIN_DIMENSIONS
        }
        dimensions = {
            dimension: pinyin_dimension_state(items)
            for dimension, items in by_dimension.items()
            if items
        }
        required_states = [dimensions.get(dimension, "unlearned") for dimension in required]
        has_evidence = bool(learning_records or assessment_items)
        state_code = "introduced" if learning_records else "unlearned"
        if assessment_items:
            state_code = "practicing"
        if all(state in {"proficient", "stable"} for state in required_states):
            state_code = "proficient"
        if all(state == "stable" for state in required_states):
            state_code = "stable"
        legacy_level = {
            "unlearned": MasteryLevel.UNLEARNED,
            "introduced": MasteryLevel.INTRODUCED,
            "practicing": MasteryLevel.RECOGNIZING,
            "proficient": MasteryLevel.PROFICIENT,
            "stable": MasteryLevel.STABLE,
        }[state_code]
        ordered_learning = sorted(
            learning_records, key=lambda record: (_utc(record.learned_at), str(record.id))
        )
        ordered_items = sorted(
            assessment_items, key=lambda item: (_utc(item.assessed_at), str(item.id))
        )
        counts = {outcome.value: 0 for outcome in AssessmentOutcome}
        response_times: list[int] = []
        consecutive_correct = 0
        consecutive_incorrect = 0
        for item in ordered_items:
            counts[item.outcome] += 1
            if item.response_time_ms is not None:
                response_times.append(item.response_time_ms)
            if item.outcome == AssessmentOutcome.CORRECT:
                consecutive_correct += 1
                consecutive_incorrect = 0
            elif item.outcome == AssessmentOutcome.INCORRECT:
                consecutive_incorrect += 1
                consecutive_correct = 0
            else:
                consecutive_correct = 0
                consecutive_incorrect = 0
        rank = {"unlearned": 0.0, "practicing": 0.35, "proficient": 0.7, "stable": 1.0}
        score = round(sum(rank[state] for state in required_states) / len(required_states), 4)
        return MasteryProjection(
            mastery_level=legacy_level,
            mastery_score=score,
            first_introduced_at=(ordered_learning[0].learned_at if ordered_learning else None),
            last_learning_at=(ordered_learning[-1].learned_at if ordered_learning else None),
            last_assessed_at=(ordered_items[-1].assessed_at if ordered_items else None),
            correct_count=counts[AssessmentOutcome.CORRECT],
            hinted_correct_count=counts[AssessmentOutcome.HINTED_CORRECT],
            uncertain_count=counts[AssessmentOutcome.UNCERTAIN],
            incorrect_count=counts[AssessmentOutcome.INCORRECT],
            consecutive_correct=consecutive_correct,
            consecutive_incorrect=consecutive_incorrect,
            average_response_time_ms=(
                round(sum(response_times) / len(response_times), 2) if response_times else None
            ),
            state_code=state_code if has_evidence else "unlearned",
            dimensions_json=dimensions,
        )


class MathMasteryPolicy:
    """Math-specific projection requiring independent, varied, cross-day evidence."""

    key = MATH_POLICY_KEY
    supported_knowledge_types = frozenset({KnowledgeType.MATH_SKILL})
    supported_assessment_kinds = frozenset({AssessmentKind.MATH_CHECK})

    def recompute(
        self,
        learning_records: list[LearningRecord],
        assessment_items: list[AssessmentItem],
        *,
        knowledge_type: str | None = None,
    ) -> MasteryProjection:
        del knowledge_type
        ordered_learning = sorted(
            learning_records, key=lambda record: (_utc(record.learned_at), str(record.id))
        )
        ordered_items = sorted(
            assessment_items, key=lambda item: (_utc(item.assessed_at), str(item.id))
        )
        counts = {outcome.value: 0 for outcome in AssessmentOutcome}
        response_times: list[int] = []
        independent_items: list[AssessmentItem] = []
        representations: set[str] = set()
        independent_representations: set[str] = set()
        independent_problem_count = 0
        for item in ordered_items:
            counts[item.outcome] += 1
            if item.response_time_ms is not None:
                response_times.append(item.response_time_ms)
            metadata = item.evidence_metadata or {}
            representations.update(str(value) for value in metadata.get("representations", []))
            if item.outcome == AssessmentOutcome.CORRECT and not item.hint_used:
                independent_items.append(item)
                independent_representations.update(
                    str(value) for value in metadata.get("representations", [])
                )
                independent_problem_count += int(
                    metadata.get("first_answer_correct_count", metadata.get("correct_attempts", 1))
                )

        independent_dates = {_utc(item.assessed_at).date() for item in independent_items}
        span_days = 0.0
        if independent_items:
            first = min(_utc(item.assessed_at) for item in independent_items)
            last = max(_utc(item.assessed_at) for item in independent_items)
            span_days = (last - first).total_seconds() / 86400
        latest_success = bool(
            ordered_items
            and ordered_items[-1].outcome == AssessmentOutcome.CORRECT
            and not ordered_items[-1].hint_used
        )

        has_evidence = bool(ordered_learning or ordered_items)
        state_code = "introduced" if ordered_learning else "unlearned"
        if ordered_items:
            state_code = "practicing"
        if independent_problem_count >= 2 and independent_items:
            state_code = "proficient"
        stable = (
            independent_problem_count >= 6
            and len(independent_items) >= 3
            and len(independent_dates) >= 3
            and span_days >= 7
            and len(independent_representations) >= 3
            and latest_success
        )
        if stable:
            state_code = "stable"

        understanding_state = "unlearned"
        if ordered_learning:
            understanding_state = "introduced"
        if ordered_items:
            understanding_state = "practicing"
        if independent_problem_count >= 2:
            understanding_state = "proficient"
        if stable:
            understanding_state = "stable"
        independent_state = "unlearned"
        if independent_items:
            independent_state = "practicing"
        if independent_problem_count >= 2:
            independent_state = "proficient"
        if stable:
            independent_state = "stable"
        transfer_state = "unlearned"
        if independent_representations:
            transfer_state = "practicing"
        if len(independent_representations) >= 2 and independent_problem_count >= 2:
            transfer_state = "proficient"
        if stable:
            transfer_state = "stable"

        legacy_level = {
            "unlearned": MasteryLevel.UNLEARNED,
            "introduced": MasteryLevel.INTRODUCED,
            "practicing": MasteryLevel.RECOGNIZING,
            "proficient": MasteryLevel.PROFICIENT,
            "stable": MasteryLevel.STABLE,
        }[state_code]
        consecutive_correct = 0
        consecutive_incorrect = 0
        for item in ordered_items:
            if item.outcome == AssessmentOutcome.CORRECT and not item.hint_used:
                consecutive_correct += 1
                consecutive_incorrect = 0
            elif item.outcome == AssessmentOutcome.INCORRECT:
                consecutive_incorrect += 1
                consecutive_correct = 0
            else:
                consecutive_correct = 0
                consecutive_incorrect = 0
        score = {
            "unlearned": 0.0,
            "introduced": 0.15,
            "practicing": 0.4,
            "proficient": 0.75,
            "stable": 1.0,
        }[state_code]
        return MasteryProjection(
            mastery_level=legacy_level,
            mastery_score=score,
            first_introduced_at=ordered_learning[0].learned_at if ordered_learning else None,
            last_learning_at=ordered_learning[-1].learned_at if ordered_learning else None,
            last_assessed_at=ordered_items[-1].assessed_at if ordered_items else None,
            correct_count=counts[AssessmentOutcome.CORRECT],
            hinted_correct_count=counts[AssessmentOutcome.HINTED_CORRECT],
            uncertain_count=counts[AssessmentOutcome.UNCERTAIN],
            incorrect_count=counts[AssessmentOutcome.INCORRECT],
            consecutive_correct=consecutive_correct,
            consecutive_incorrect=consecutive_incorrect,
            average_response_time_ms=(
                round(sum(response_times) / len(response_times), 2) if response_times else None
            ),
            state_code=state_code if has_evidence else "unlearned",
            dimensions_json={
                "understanding": understanding_state,
                "independent": independent_state,
                "transfer": transfer_state,
                "representation": {
                    "state": transfer_state,
                    "types": sorted(representations),
                    "independent_types": sorted(independent_representations),
                },
                "independent_problem_count": independent_problem_count,
                "independent_dates": len(independent_dates),
                "evidence_span_days": round(span_days, 2),
            },
        )


mastery_policies = MasteryPolicyRegistry()
mastery_policies.register(ChineseCharacterMasteryPolicy())
mastery_policies.register(PinyinMasteryPolicy())
mastery_policies.register(MathMasteryPolicy())


def mastery_policy_for_type(knowledge_type: str) -> MasteryPolicy | None:
    return mastery_policies.for_knowledge_type(knowledge_type)


async def recompute_child_knowledge_state(
    session: AsyncSession,
    child_id: uuid.UUID,
    knowledge_point_id: uuid.UUID,
    *,
    ensure_state: bool = False,
) -> ChildKnowledgeState | None:
    """Rebuild one projection while preserving its family-managed priority flag."""

    point = await session.get(KnowledgePoint, knowledge_point_id)
    if point is None:
        return None
    policy = mastery_policy_for_type(point.type)
    if policy is None:
        # Generic evidence remains canonical even when no domain projection exists.
        return None

    learning_records = list(
        (
            await session.scalars(
                select(LearningRecord).where(
                    LearningRecord.child_id == child_id,
                    LearningRecord.knowledge_point_id == knowledge_point_id,
                )
            )
        ).all()
    )
    assessment_items = list(
        (
            await session.scalars(
                select(AssessmentItem)
                .join(AssessmentSession, AssessmentSession.id == AssessmentItem.session_id)
                .where(
                    AssessmentItem.child_id == child_id,
                    AssessmentItem.knowledge_point_id == knowledge_point_id,
                    AssessmentSession.assessment_kind.in_(policy.supported_assessment_kinds),
                )
            )
        ).all()
    )
    state = await session.scalar(
        select(ChildKnowledgeState).where(
            ChildKnowledgeState.child_id == child_id,
            ChildKnowledgeState.knowledge_point_id == knowledge_point_id,
        )
    )
    if state is None and not (ensure_state or learning_records or assessment_items):
        return None
    if state is None:
        state = ChildKnowledgeState(
            child_id=child_id,
            knowledge_point_id=knowledge_point_id,
        )
        session.add(state)

    projection = policy.recompute(learning_records, assessment_items, knowledge_type=point.type)
    for field_name, value in projection.__dict__.items():
        if field_name in {"state_code", "dimensions_json"}:
            continue
        setattr(state, field_name, value)
    state.algorithm_version = (
        ALGORITHM_VERSION if policy.key == CHINESE_CHARACTER_POLICY_KEY else policy.key
    )
    state.policy_key = policy.key
    state.state_code = projection.state_code or projection.mastery_level
    state.dimensions_json = projection.dimensions_json
    await session.flush()
    return state


async def recompute_child_states(session: AsyncSession, child_id: uuid.UUID | None = None) -> int:
    """Rebuild every materialized state represented by evidence or priority rows."""

    point_pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()
    for model in (LearningRecord, AssessmentItem, ChildKnowledgeState):
        query = select(model.child_id, model.knowledge_point_id)
        if child_id is not None:
            query = query.where(model.child_id == child_id)
        point_pairs.update((await session.execute(query)).all())

    projected = 0
    for state_child_id, point_id in point_pairs:
        projected += int(
            await recompute_child_knowledge_state(
                session, state_child_id, point_id, ensure_state=True
            )
            is not None
        )
    return projected
