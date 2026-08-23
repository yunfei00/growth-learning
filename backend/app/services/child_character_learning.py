"""Authorized child character evidence capture and mastery read models."""

import math
import uuid
from datetime import UTC, datetime

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssessmentItem,
    AssessmentSession,
    ChildKnowledgeState,
    ChineseCharacter,
    KnowledgePoint,
    KnowledgeStatus,
    LearningRecord,
    LearningSession,
    MasteryLevel,
    SessionStatus,
)
from app.schemas.learning import (
    AssessmentSessionCreate,
    CharacterMasteryDetail,
    CharacterMasteryPage,
    CharacterMasteryState,
    CharacterMasterySummary,
    CharacterRecommendation,
    EvidenceSessionResponse,
    LearningSessionCreate,
    TimelineItem,
)
from app.services.mastery import recompute_child_knowledge_state
from app.services.review_planning import (
    recompute_review_schedule,
    update_daily_learning_progress,
)


def _state_response(
    point: KnowledgePoint,
    character: ChineseCharacter,
    state: ChildKnowledgeState | None,
) -> CharacterMasteryState:
    return CharacterMasteryState(
        knowledge_point_id=point.id,
        character=character.character,
        pinyin=character.pinyin,
        common_words=character.common_words,
        simple_meaning=character.simple_meaning,
        example_sentence=character.example_sentence,
        parent_tip=character.parent_tip,
        mastery_level=state.mastery_level if state else MasteryLevel.UNLEARNED,
        mastery_score=state.mastery_score if state else 0,
        first_introduced_at=state.first_introduced_at if state else None,
        last_learning_at=state.last_learning_at if state else None,
        last_assessed_at=state.last_assessed_at if state else None,
        correct_count=state.correct_count if state else 0,
        hinted_correct_count=state.hinted_correct_count if state else 0,
        uncertain_count=state.uncertain_count if state else 0,
        incorrect_count=state.incorrect_count if state else 0,
        consecutive_correct=state.consecutive_correct if state else 0,
        consecutive_incorrect=state.consecutive_incorrect if state else 0,
        average_response_time_ms=state.average_response_time_ms if state else None,
        is_priority=state.is_priority if state else False,
        algorithm_version=state.algorithm_version if state else "v1",
    )


def _enabled_character_query(child_id: uuid.UUID) -> Select:
    return (
        select(KnowledgePoint, ChineseCharacter, ChildKnowledgeState)
        .join(ChineseCharacter, ChineseCharacter.knowledge_point_id == KnowledgePoint.id)
        .outerjoin(
            ChildKnowledgeState,
            and_(
                ChildKnowledgeState.knowledge_point_id == KnowledgePoint.id,
                ChildKnowledgeState.child_id == child_id,
            ),
        )
        .where(
            KnowledgePoint.status == KnowledgeStatus.ACTIVE,
            ChineseCharacter.is_enabled.is_(True),
        )
    )


async def summarize_character_mastery(
    session: AsyncSession, child_id: uuid.UUID
) -> CharacterMasterySummary:
    enabled_conditions = (
        KnowledgePoint.status == KnowledgeStatus.ACTIVE,
        ChineseCharacter.is_enabled.is_(True),
    )
    total = int(
        await session.scalar(
            select(func.count())
            .select_from(ChineseCharacter)
            .join(KnowledgePoint)
            .where(*enabled_conditions)
        )
        or 0
    )
    rows = (
        await session.execute(
            select(ChildKnowledgeState.mastery_level, func.count())
            .join(KnowledgePoint, KnowledgePoint.id == ChildKnowledgeState.knowledge_point_id)
            .join(ChineseCharacter, ChineseCharacter.knowledge_point_id == KnowledgePoint.id)
            .where(ChildKnowledgeState.child_id == child_id, *enabled_conditions)
            .group_by(ChildKnowledgeState.mastery_level)
        )
    ).all()
    counts = dict(rows)
    represented = sum(counts.values())
    priority = int(
        await session.scalar(
            select(func.count())
            .select_from(ChildKnowledgeState)
            .join(KnowledgePoint)
            .join(ChineseCharacter)
            .where(
                ChildKnowledgeState.child_id == child_id,
                ChildKnowledgeState.is_priority.is_(True),
                *enabled_conditions,
            )
        )
        or 0
    )
    learning_count = int(
        await session.scalar(
            select(func.count())
            .select_from(LearningRecord)
            .where(LearningRecord.child_id == child_id)
        )
        or 0
    )
    assessment_count = int(
        await session.scalar(
            select(func.count())
            .select_from(AssessmentItem)
            .where(AssessmentItem.child_id == child_id)
        )
        or 0
    )
    return CharacterMasterySummary(
        total_enabled=total,
        unlearned=total - represented + counts.get(MasteryLevel.UNLEARNED, 0),
        introduced=counts.get(MasteryLevel.INTRODUCED, 0),
        recognizing=counts.get(MasteryLevel.RECOGNIZING, 0),
        proficient=counts.get(MasteryLevel.PROFICIENT, 0),
        stable=counts.get(MasteryLevel.STABLE, 0),
        priority=priority,
        learning_records=learning_count,
        assessment_items=assessment_count,
    )


async def list_character_mastery(
    session: AsyncSession,
    child_id: uuid.UUID,
    *,
    search: str | None,
    mastery_level: str | None,
    priority: bool | None,
    sort_by: str,
    sort_order: str,
    page: int,
    page_size: int,
) -> CharacterMasteryPage:
    query = _enabled_character_query(child_id)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                ChineseCharacter.character.ilike(pattern),
                ChineseCharacter.pinyin.ilike(pattern),
            )
        )
    if mastery_level == MasteryLevel.UNLEARNED:
        query = query.where(
            or_(
                ChildKnowledgeState.id.is_(None),
                ChildKnowledgeState.mastery_level == MasteryLevel.UNLEARNED,
            )
        )
    elif mastery_level:
        query = query.where(ChildKnowledgeState.mastery_level == mastery_level)
    if priority is not None:
        if priority:
            query = query.where(ChildKnowledgeState.is_priority.is_(True))
        else:
            query = query.where(
                or_(ChildKnowledgeState.id.is_(None), ChildKnowledgeState.is_priority.is_(False))
            )

    total = int(await session.scalar(select(func.count()).select_from(query.subquery())) or 0)
    sort_columns = {
        "learning_time": ChildKnowledgeState.last_learning_at,
        "recent_review": ChildKnowledgeState.last_assessed_at,
        "character": ChineseCharacter.character,
    }
    sort_column = sort_columns[sort_by]
    ordered = sort_column.asc() if sort_order == "asc" else sort_column.desc()
    rows = (
        await session.execute(
            query.order_by(
                ChildKnowledgeState.is_priority.desc(),
                ordered.nulls_last(),
                ChineseCharacter.character,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return CharacterMasteryPage(
        items=[_state_response(*row) for row in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=max(1, math.ceil(total / page_size)),
    )


async def get_character_mastery_detail(
    session: AsyncSession, child_id: uuid.UUID, knowledge_point_id: uuid.UUID
) -> CharacterMasteryDetail | None:
    row = (
        await session.execute(
            select(KnowledgePoint, ChineseCharacter, ChildKnowledgeState)
            .join(ChineseCharacter)
            .outerjoin(
                ChildKnowledgeState,
                and_(
                    ChildKnowledgeState.knowledge_point_id == KnowledgePoint.id,
                    ChildKnowledgeState.child_id == child_id,
                ),
            )
            .where(KnowledgePoint.id == knowledge_point_id)
        )
    ).one_or_none()
    if row is None:
        return None
    point, character, state = row
    learning = (
        await session.scalars(
            select(LearningRecord).where(
                LearningRecord.child_id == child_id,
                LearningRecord.knowledge_point_id == knowledge_point_id,
            )
        )
    ).all()
    assessments = (
        await session.scalars(
            select(AssessmentItem).where(
                AssessmentItem.child_id == child_id,
                AssessmentItem.knowledge_point_id == knowledge_point_id,
            )
        )
    ).all()
    timeline = [
        TimelineItem(
            id=record.id,
            evidence_type="learning",
            value=record.activity_type,
            occurred_at=record.learned_at,
        )
        for record in learning
    ] + [
        TimelineItem(
            id=item.id,
            evidence_type="assessment",
            value=item.outcome,
            occurred_at=item.assessed_at,
            response_time_ms=item.response_time_ms,
        )
        for item in assessments
    ]
    timeline.sort(key=lambda item: (item.occurred_at, str(item.id)), reverse=True)
    return CharacterMasteryDetail(state=_state_response(point, character, state), timeline=timeline)


async def recommend_characters(
    session: AsyncSession, child_id: uuid.UUID, *, mode: str, limit: int
) -> list[CharacterRecommendation]:
    query = _enabled_character_query(child_id)
    if mode == "new":
        learned = select(LearningRecord.id).where(
            LearningRecord.child_id == child_id,
            LearningRecord.knowledge_point_id == KnowledgePoint.id,
        )
        query = query.where(~learned.exists())
    else:
        query = query.where(
            ChildKnowledgeState.mastery_level.in_(
                [
                    MasteryLevel.INTRODUCED,
                    MasteryLevel.RECOGNIZING,
                    MasteryLevel.PROFICIENT,
                    MasteryLevel.STABLE,
                ]
            )
        )
    rows = (
        await session.execute(
            query.order_by(
                ChildKnowledgeState.is_priority.desc(),
                ChildKnowledgeState.mastery_score,
                ChineseCharacter.created_at,
            ).limit(limit)
        )
    ).all()
    return [
        CharacterRecommendation(
            id=point.id,
            character=character.character,
            pinyin=character.pinyin,
            common_words=character.common_words,
            simple_meaning=character.simple_meaning,
            example_sentence=character.example_sentence,
            mastery_level=state.mastery_level if state else MasteryLevel.UNLEARNED,
            is_priority=state.is_priority if state else False,
        )
        for point, character, state in rows
    ]


async def _validate_enabled_points(session: AsyncSession, point_ids: set[uuid.UUID]) -> None:
    available = set(
        (
            await session.scalars(
                select(KnowledgePoint.id)
                .join(ChineseCharacter)
                .where(
                    KnowledgePoint.id.in_(point_ids),
                    KnowledgePoint.status == KnowledgeStatus.ACTIVE,
                    ChineseCharacter.is_enabled.is_(True),
                )
            )
        ).all()
    )
    if available != point_ids:
        raise ValueError("One or more enabled characters were not found")


async def create_learning_session(
    session: AsyncSession,
    child_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    payload: LearningSessionCreate,
) -> EvidenceSessionResponse:
    point_ids = {item.knowledge_point_id for item in payload.items}
    await _validate_enabled_points(session, point_ids)
    now = datetime.now(UTC)
    learning_session = LearningSession(
        child_id=child_id,
        actor_user_id=actor_user_id,
        status=payload.status,
        source=payload.source,
        completed_at=now if payload.status != SessionStatus.IN_PROGRESS else None,
    )
    session.add(learning_session)
    await session.flush()
    for item in payload.items:
        session.add(
            LearningRecord(
                session_id=learning_session.id,
                child_id=child_id,
                knowledge_point_id=item.knowledge_point_id,
                actor_user_id=actor_user_id,
                activity_type=item.activity_type,
                source=payload.source,
                learned_at=now,
            )
        )
    await session.flush()
    for point_id in point_ids:
        await recompute_child_knowledge_state(session, child_id, point_id)
        await recompute_review_schedule(session, child_id, point_id)
    await update_daily_learning_progress(session, child_id, point_ids, now=now)
    await session.commit()
    return EvidenceSessionResponse(
        id=learning_session.id,
        child_id=child_id,
        status=learning_session.status,
        source=learning_session.source,
        item_count=len(payload.items),
        started_at=learning_session.started_at,
        completed_at=learning_session.completed_at,
        created_at=learning_session.created_at,
    )


async def create_assessment_session(
    session: AsyncSession,
    child_id: uuid.UUID,
    evaluator_user_id: uuid.UUID,
    payload: AssessmentSessionCreate,
) -> EvidenceSessionResponse:
    point_ids = {item.knowledge_point_id for item in payload.items}
    await _validate_enabled_points(session, point_ids)
    now = datetime.now(UTC)
    assessment_session = AssessmentSession(
        child_id=child_id,
        evaluator_user_id=evaluator_user_id,
        status=payload.status,
        source=payload.source,
        completed_at=now if payload.status != SessionStatus.IN_PROGRESS else None,
    )
    session.add(assessment_session)
    await session.flush()
    for item in payload.items:
        session.add(
            AssessmentItem(
                session_id=assessment_session.id,
                child_id=child_id,
                knowledge_point_id=item.knowledge_point_id,
                evaluator_user_id=evaluator_user_id,
                outcome=item.outcome,
                response_time_ms=item.response_time_ms,
                hint_used=item.hint_used,
                assessed_at=now,
            )
        )
    await session.flush()
    for point_id in point_ids:
        await recompute_child_knowledge_state(session, child_id, point_id)
        await recompute_review_schedule(session, child_id, point_id)
    await session.commit()
    return EvidenceSessionResponse(
        id=assessment_session.id,
        child_id=child_id,
        status=assessment_session.status,
        source=assessment_session.source,
        item_count=len(payload.items),
        started_at=assessment_session.started_at,
        completed_at=assessment_session.completed_at,
        created_at=assessment_session.created_at,
    )
