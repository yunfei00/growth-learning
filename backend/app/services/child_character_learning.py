"""Authorized child character evidence capture and mastery read models."""

import math
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ActivityKnowledgePoint,
    AssessmentItem,
    AssessmentSession,
    AssessmentSessionTarget,
    CatalogRelease,
    CharacterCatalogEntry,
    ChildKnowledgeState,
    ChineseCharacter,
    DailyLearningPlan,
    DailyPlanItem,
    KnowledgePoint,
    KnowledgeStatus,
    KnowledgeType,
    LearningRecord,
    LearningSession,
    MasteryLevel,
    SessionStatus,
)
from app.schemas.learning import (
    AssessmentSessionCreate,
    CharacterLearningHistoryPage,
    CharacterLearningHistoryRecord,
    CharacterLearningHistorySession,
    CharacterMasteryDetail,
    CharacterMasteryPage,
    CharacterMasteryState,
    CharacterMasterySummary,
    CharacterNavigationItem,
    CharacterNavigationResponse,
    CharacterRecommendation,
    EvidenceSessionResponse,
    LearningSessionCreate,
    TimelineItem,
)
from app.services.mastery import mastery_policy_for_type, recompute_child_knowledge_state
from app.services.pinyin_learning import update_pinyin_daily_progress
from app.services.review_planning import (
    recompute_review_schedule,
    update_daily_learning_progress,
)


def _character_point_ids():
    return (
        select(KnowledgePoint.id)
        .join(ChineseCharacter)
        .where(KnowledgePoint.type == KnowledgeType.CHINESE_CHARACTER)
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
            .where(
                LearningRecord.child_id == child_id,
                LearningRecord.knowledge_point_id.in_(_character_point_ids()),
            )
        )
        or 0
    )
    assessment_count = int(
        await session.scalar(
            select(func.count())
            .select_from(AssessmentItem)
            .where(
                AssessmentItem.child_id == child_id,
                AssessmentItem.knowledge_point_id.in_(_character_point_ids()),
            )
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


async def list_character_learning_history(
    session: AsyncSession,
    child_id: uuid.UUID,
    *,
    search: str | None,
    learned_from: datetime | None,
    learned_to: datetime | None,
    page: int,
    page_size: int,
) -> CharacterLearningHistoryPage:
    """Return only real learning evidence, grouped without collapsing repeated sessions."""

    record_query = (
        select(LearningRecord.id)
        .join(KnowledgePoint, KnowledgePoint.id == LearningRecord.knowledge_point_id)
        .join(ChineseCharacter, ChineseCharacter.knowledge_point_id == KnowledgePoint.id)
        .where(LearningRecord.child_id == child_id)
    )
    if search:
        pattern = f"%{search.strip()}%"
        record_query = record_query.where(
            or_(
                ChineseCharacter.character.ilike(pattern),
                ChineseCharacter.pinyin.ilike(pattern),
            )
        )
    if learned_from is not None:
        record_query = record_query.where(LearningRecord.learned_at >= learned_from)
    if learned_to is not None:
        record_query = record_query.where(LearningRecord.learned_at < learned_to)

    filtered_records = record_query.subquery()
    total_records = int(
        await session.scalar(select(func.count()).select_from(filtered_records)) or 0
    )
    session_ids_query = (
        select(LearningRecord.session_id)
        .where(LearningRecord.id.in_(select(filtered_records.c.id)))
        .distinct()
    )
    total_sessions = int(
        await session.scalar(select(func.count()).select_from(session_ids_query.subquery())) or 0
    )
    session_rows = list(
        (
            await session.scalars(
                select(LearningSession)
                .where(LearningSession.id.in_(session_ids_query))
                .order_by(
                    func.coalesce(
                        LearningSession.completed_at,
                        LearningSession.started_at,
                    ).desc(),
                    LearningSession.id.desc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    selected_session_ids = [item.id for item in session_rows]
    records_by_session: dict[uuid.UUID, list[CharacterLearningHistoryRecord]] = {
        item.id: [] for item in session_rows
    }
    if selected_session_ids:
        record_rows = (
            await session.execute(
                select(
                    LearningRecord,
                    KnowledgePoint,
                    ChineseCharacter,
                    ChildKnowledgeState,
                )
                .join(KnowledgePoint, KnowledgePoint.id == LearningRecord.knowledge_point_id)
                .join(ChineseCharacter, ChineseCharacter.knowledge_point_id == KnowledgePoint.id)
                .outerjoin(
                    ChildKnowledgeState,
                    and_(
                        ChildKnowledgeState.child_id == child_id,
                        ChildKnowledgeState.knowledge_point_id == KnowledgePoint.id,
                    ),
                )
                .where(
                    LearningRecord.id.in_(select(filtered_records.c.id)),
                    LearningRecord.session_id.in_(selected_session_ids),
                )
                .order_by(
                    LearningRecord.learned_at,
                    LearningRecord.created_at,
                    LearningRecord.id,
                )
            )
        ).all()
        for record, point, character, state in record_rows:
            records_by_session[record.session_id].append(
                CharacterLearningHistoryRecord(
                    record_id=record.id,
                    knowledge_point_id=point.id,
                    character=character.character,
                    pinyin=character.pinyin,
                    activity_type=record.activity_type,
                    source=record.source,
                    learned_at=record.learned_at,
                    mastery_level=state.mastery_level if state else MasteryLevel.UNLEARNED,
                    is_priority=state.is_priority if state else False,
                )
            )

    distinct_characters = int(
        await session.scalar(
            select(func.count(func.distinct(LearningRecord.knowledge_point_id))).where(
                LearningRecord.child_id == child_id,
                LearningRecord.knowledge_point_id.in_(_character_point_ids()),
            )
        )
        or 0
    )
    now = datetime.now(UTC)
    week_start = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    first_learning = (
        select(
            LearningRecord.knowledge_point_id,
            func.min(LearningRecord.learned_at).label("first_learned_at"),
        )
        .where(
            LearningRecord.child_id == child_id,
            LearningRecord.knowledge_point_id.in_(_character_point_ids()),
        )
        .group_by(LearningRecord.knowledge_point_id)
        .subquery()
    )
    this_week_first_learned = int(
        await session.scalar(
            select(func.count())
            .select_from(first_learning)
            .where(first_learning.c.first_learned_at >= week_start)
        )
        or 0
    )
    return CharacterLearningHistoryPage(
        items=[
            CharacterLearningHistorySession(
                session_id=item.id,
                source=item.source,
                status=item.status,
                started_at=item.started_at,
                completed_at=item.completed_at,
                records=records_by_session[item.id],
            )
            for item in session_rows
        ],
        page=page,
        page_size=page_size,
        total_sessions=total_sessions,
        total_records=total_records,
        pages=max(1, math.ceil(total_sessions / page_size)),
        distinct_characters=distinct_characters,
        this_week_first_learned=this_week_first_learned,
    )


async def get_character_navigation(
    session: AsyncSession,
    child_id: uuid.UUID,
    knowledge_point_id: uuid.UUID,
    *,
    sequence: str,
    context_id: uuid.UUID | None,
    item_kind: str | None,
    mastery_level: str | None,
    priority: bool | None,
    sort_by: str,
    sort_order: str,
) -> CharacterNavigationResponse | None:
    """Resolve stable previous/next links from a small, refresh-safe sequence context."""

    base = (
        select(KnowledgePoint.id, ChineseCharacter.character)
        .join(ChineseCharacter, ChineseCharacter.knowledge_point_id == KnowledgePoint.id)
        .where(
            KnowledgePoint.status == KnowledgeStatus.ACTIVE,
            ChineseCharacter.is_enabled.is_(True),
        )
    )
    if sequence == "system_path":
        release_id = await session.scalar(
            select(CatalogRelease.id)
            .where(CatalogRelease.is_current.is_(True))
            .order_by(CatalogRelease.imported_at.desc(), CatalogRelease.id.desc())
            .limit(1)
        )
        if release_id is None:
            rows = (
                await session.execute(base.order_by(ChineseCharacter.created_at, KnowledgePoint.id))
            ).all()
        else:
            rows = (
                await session.execute(
                    base.join(
                        CharacterCatalogEntry,
                        CharacterCatalogEntry.knowledge_point_id == KnowledgePoint.id,
                    )
                    .where(CharacterCatalogEntry.catalog_release_id == release_id)
                    .order_by(CharacterCatalogEntry.order_index)
                )
            ).all()
    elif sequence == "today":
        if context_id is None:
            raise ValueError("A daily plan is required for today navigation")
        query = (
            base.join(DailyPlanItem, DailyPlanItem.knowledge_point_id == KnowledgePoint.id)
            .join(DailyLearningPlan, DailyLearningPlan.id == DailyPlanItem.daily_plan_id)
            .where(
                DailyLearningPlan.id == context_id,
                DailyLearningPlan.child_id == child_id,
            )
        )
        if item_kind:
            query = query.where(DailyPlanItem.item_kind == item_kind)
        rows = (await session.execute(query.order_by(DailyPlanItem.position))).all()
    elif sequence == "mastery":
        query = _enabled_character_query(child_id)
        if mastery_level == MasteryLevel.UNLEARNED:
            query = query.where(
                or_(
                    ChildKnowledgeState.id.is_(None),
                    ChildKnowledgeState.mastery_level == MasteryLevel.UNLEARNED,
                )
            )
        elif mastery_level:
            query = query.where(ChildKnowledgeState.mastery_level == mastery_level)
        if priority is True:
            query = query.where(ChildKnowledgeState.is_priority.is_(True))
        sort_columns = {
            "learning_time": ChildKnowledgeState.last_learning_at,
            "recent_review": ChildKnowledgeState.last_assessed_at,
            "character": ChineseCharacter.character,
        }
        sort_column = sort_columns[sort_by]
        ordered = sort_column.asc() if sort_order == "asc" else sort_column.desc()
        mastery_rows = (
            await session.execute(
                query.order_by(
                    ChildKnowledgeState.is_priority.desc(),
                    ordered.nulls_last(),
                    ChineseCharacter.character,
                )
            )
        ).all()
        rows = [(point.id, character.character) for point, character, _ in mastery_rows]
    elif sequence == "learning_session":
        if context_id is None:
            raise ValueError("A learning session is required for history navigation")
        rows = (
            await session.execute(
                base.join(LearningRecord, LearningRecord.knowledge_point_id == KnowledgePoint.id)
                .join(LearningSession, LearningSession.id == LearningRecord.session_id)
                .where(
                    LearningSession.id == context_id,
                    LearningSession.child_id == child_id,
                )
                .order_by(
                    LearningRecord.learned_at,
                    LearningRecord.created_at,
                    LearningRecord.id,
                )
            )
        ).all()
    elif sequence == "assessment_session":
        if context_id is None:
            raise ValueError("An assessment session is required for assessment navigation")
        rows = (
            await session.execute(
                base.join(
                    AssessmentSessionTarget,
                    AssessmentSessionTarget.knowledge_point_id == KnowledgePoint.id,
                )
                .join(
                    AssessmentSession,
                    AssessmentSession.id == AssessmentSessionTarget.assessment_session_id,
                )
                .where(
                    AssessmentSession.id == context_id,
                    AssessmentSession.child_id == child_id,
                )
                .order_by(AssessmentSessionTarget.position)
            )
        ).all()
    elif sequence == "course_activity":
        if context_id is None:
            raise ValueError("A course activity is required for course navigation")
        rows = (
            await session.execute(
                base.join(
                    ActivityKnowledgePoint,
                    ActivityKnowledgePoint.knowledge_point_id == KnowledgePoint.id,
                )
                .where(ActivityKnowledgePoint.activity_id == context_id)
                .order_by(ActivityKnowledgePoint.order_index)
            )
        ).all()
    else:
        raise ValueError("Unknown character navigation sequence")

    normalized_rows = [(row[0], row[1]) for row in rows]
    current_index = next(
        (
            index
            for index, (point_id, _) in enumerate(normalized_rows)
            if point_id == knowledge_point_id
        ),
        None,
    )
    if current_index is None:
        return None

    def navigation_item(index: int) -> CharacterNavigationItem:
        point_id, character = normalized_rows[index]
        return CharacterNavigationItem(knowledge_point_id=point_id, character=character)

    return CharacterNavigationResponse(
        sequence=sequence,
        position=current_index + 1,
        total=len(normalized_rows),
        group=current_index // 10 + 1 if sequence == "system_path" else None,
        group_size=10 if sequence == "system_path" else None,
        previous=navigation_item(current_index - 1) if current_index > 0 else None,
        next=(
            navigation_item(current_index + 1) if current_index + 1 < len(normalized_rows) else None
        ),
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


async def _validate_enabled_points(
    session: AsyncSession, point_ids: set[uuid.UUID]
) -> dict[uuid.UUID, KnowledgePoint]:
    rows = list(
        (
            await session.execute(
                select(KnowledgePoint, ChineseCharacter)
                .outerjoin(
                    ChineseCharacter,
                    ChineseCharacter.knowledge_point_id == KnowledgePoint.id,
                )
                .where(
                    KnowledgePoint.id.in_(point_ids),
                    KnowledgePoint.status == KnowledgeStatus.ACTIVE,
                    or_(
                        KnowledgePoint.type != KnowledgeType.CHINESE_CHARACTER,
                        ChineseCharacter.is_enabled.is_(True),
                    ),
                )
            )
        ).all()
    )
    available = {point.id: point for point, _ in rows}
    if set(available) != point_ids:
        raise ValueError("One or more enabled knowledge points were not found")
    return available


def _projection_availability(
    points: dict[uuid.UUID, KnowledgePoint],
) -> tuple[str, list[uuid.UUID]]:
    unavailable = sorted(
        (
            point_id
            for point_id, point in points.items()
            if mastery_policy_for_type(point.type) is None
        ),
        key=str,
    )
    if not unavailable:
        return "configured", []
    if len(unavailable) == len(points):
        return "unavailable", unavailable
    return "partially_unavailable", unavailable


class UnsupportedAssessmentFlowError(ValueError):
    """The subject has a stricter evidence workflow than the generic endpoint."""


async def create_learning_session(
    session: AsyncSession,
    child_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    payload: LearningSessionCreate,
) -> EvidenceSessionResponse:
    point_ids = {item.knowledge_point_id for item in payload.items}
    points = await _validate_enabled_points(session, point_ids)
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
    await update_pinyin_daily_progress(session, child_id, point_ids, now=now)
    await session.commit()
    projection_status, unavailable = _projection_availability(points)
    return EvidenceSessionResponse(
        id=learning_session.id,
        child_id=child_id,
        status=learning_session.status,
        source=learning_session.source,
        item_count=len(payload.items),
        started_at=learning_session.started_at,
        completed_at=learning_session.completed_at,
        created_at=learning_session.created_at,
        mastery_projection=projection_status,
        projection_unavailable_knowledge_point_ids=unavailable,
    )


async def create_assessment_session(
    session: AsyncSession,
    child_id: uuid.UUID,
    evaluator_user_id: uuid.UUID,
    payload: AssessmentSessionCreate,
) -> EvidenceSessionResponse:
    point_ids = {item.knowledge_point_id for item in payload.items}
    points = await _validate_enabled_points(session, point_ids)
    if any(point.type == KnowledgeType.MATH_SKILL for point in points.values()):
        raise UnsupportedAssessmentFlowError(
            "Math skill assessment must use the deterministic Math session endpoint"
        )
    if any(
        point.type
        in {
            KnowledgeType.ENGLISH_LETTER,
            KnowledgeType.ENGLISH_WORD,
            KnowledgeType.ENGLISH_PHONICS,
            KnowledgeType.ENGLISH_PHRASE,
        }
        for point in points.values()
    ):
        raise UnsupportedAssessmentFlowError(
            "English assessment must use the English exercise session endpoint"
        )
    now = datetime.now(UTC)
    assessment_session = AssessmentSession(
        child_id=child_id,
        evaluator_user_id=evaluator_user_id,
        status=payload.status,
        source=payload.source,
        assessment_kind=payload.assessment_kind,
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
                skill_dimension=item.skill_dimension,
                evidence_metadata=item.evidence_metadata,
                assessed_at=now,
            )
        )
    await session.flush()
    for point_id in point_ids:
        await recompute_child_knowledge_state(session, child_id, point_id)
        await recompute_review_schedule(session, child_id, point_id)
    await update_pinyin_daily_progress(session, child_id, point_ids, now=now)
    await session.commit()
    projection_status, unavailable = _projection_availability(points)
    return EvidenceSessionResponse(
        id=assessment_session.id,
        child_id=child_id,
        status=assessment_session.status,
        source=assessment_session.source,
        item_count=len(payload.items),
        started_at=assessment_session.started_at,
        completed_at=assessment_session.completed_at,
        created_at=assessment_session.created_at,
        mastery_projection=projection_status,
        projection_unavailable_knowledge_point_ids=unavailable,
    )
