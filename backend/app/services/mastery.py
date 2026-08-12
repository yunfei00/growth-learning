"""Deterministic mastery projection built only from preserved raw evidence."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssessmentItem,
    AssessmentOutcome,
    ChildKnowledgeState,
    LearningRecord,
    MasteryLevel,
)

ALGORITHM_VERSION = "v1"


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


async def recompute_child_knowledge_state(
    session: AsyncSession,
    child_id: uuid.UUID,
    knowledge_point_id: uuid.UUID,
    *,
    ensure_state: bool = False,
) -> ChildKnowledgeState | None:
    """Rebuild one projection while preserving its family-managed priority flag."""

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
                select(AssessmentItem).where(
                    AssessmentItem.child_id == child_id,
                    AssessmentItem.knowledge_point_id == knowledge_point_id,
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

    projection = project_mastery(learning_records, assessment_items)
    for field, value in projection.__dict__.items():
        setattr(state, field, value)
    state.algorithm_version = ALGORITHM_VERSION
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

    for state_child_id, point_id in point_pairs:
        await recompute_child_knowledge_state(session, state_child_id, point_id, ensure_state=True)
    return len(point_pairs)
