"""Pinyin catalog projections, daily selection, practice, and attributed history."""

import uuid
from collections import defaultdict
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import (
    AssessmentItem,
    AssessmentSession,
    ChildKnowledgeState,
    ChildLearningSettings,
    ChildReviewSchedule,
    DailyPlanStatus,
    KnowledgePoint,
    KnowledgeRelation,
    KnowledgeStatus,
    LearningRecord,
    LearningSession,
    PinyinDailyPlan,
    PinyinDailyPlanItem,
    PinyinItem,
    PinyinPlanItemKind,
    PinyinPracticeItem,
    PlanItemStatus,
    RelationType,
    User,
)
from app.schemas.pinyin import (
    PinyinAudioResponse,
    PinyinHistoryEvidence,
    PinyinHistoryResponse,
    PinyinHistorySession,
    PinyinItemDetail,
    PinyinItemPage,
    PinyinItemSummary,
    PinyinNavigationItem,
    PinyinOverviewGroup,
    PinyinOverviewResponse,
    PinyinPracticePage,
    PinyinPracticeResponse,
    PinyinTodayResponse,
)
from app.services.mastery import PINYIN_POLICY_KEY, pinyin_dimension_state
from app.services.pinyin_audio import pinyin_audio_provider
from app.services.pinyin_catalog import PINYIN_CATALOG_VERSION, list_pinyin_items

PINYIN_KINDS = ("initial", "final", "tone", "whole")
PINYIN_KIND_LABELS = {
    "initial": "声母",
    "final": "韵母",
    "tone": "声调",
    "whole": "整体认读",
}
PINYIN_NEW_LIMIT = 3
PINYIN_REVIEW_LIMIT = 5


def _state_code(state: ChildKnowledgeState | None) -> str:
    return state.state_code if state is not None else "unlearned"


def pinyin_item_summary(
    point: KnowledgePoint,
    item: PinyinItem,
    state: ChildKnowledgeState | None = None,
) -> PinyinItemSummary:
    audio = pinyin_audio_provider.resolve(item)
    state_code = _state_code(state)
    return PinyinItemSummary(
        knowledge_point_id=point.id,
        symbol=item.symbol,
        kind=item.kind,
        subcategory=item.subcategory,
        display_text=item.display_text,
        example_text=item.example_text,
        order_index=item.order_index,
        status=point.status,
        audio_status=audio.mode,
        state_code=state_code,
        learned=state_code != "unlearned",
    )


async def child_pinyin_items(
    session: AsyncSession,
    child_id: uuid.UUID,
    *,
    kind: str | None = None,
    subcategory: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> PinyinItemPage:
    rows, total, pages = await list_pinyin_items(
        session,
        kind=kind,
        subcategory=subcategory,
        page=page,
        page_size=page_size,
        public_only=True,
    )
    point_ids = [point.id for point, _ in rows]
    states = {
        state.knowledge_point_id: state
        for state in (
            await session.scalars(
                select(ChildKnowledgeState).where(
                    ChildKnowledgeState.child_id == child_id,
                    ChildKnowledgeState.knowledge_point_id.in_(point_ids),
                )
            )
        ).all()
    }
    return PinyinItemPage(
        items=[pinyin_item_summary(point, item, states.get(point.id)) for point, item in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=pages,
    )


async def pinyin_item_detail(
    session: AsyncSession,
    child_id: uuid.UUID,
    knowledge_point_id: uuid.UUID,
    *,
    include_archived: bool = False,
) -> PinyinItemDetail | None:
    status_filters = () if include_archived else (KnowledgePoint.status == KnowledgeStatus.ACTIVE,)
    row = (
        await session.execute(
            select(KnowledgePoint, PinyinItem, ChildKnowledgeState)
            .join(PinyinItem)
            .outerjoin(
                ChildKnowledgeState,
                and_(
                    ChildKnowledgeState.knowledge_point_id == KnowledgePoint.id,
                    ChildKnowledgeState.child_id == child_id,
                ),
            )
            .where(
                KnowledgePoint.id == knowledge_point_id,
                *status_filters,
            )
        )
    ).one_or_none()
    if row is None:
        return None
    point, item, state = row
    enabled_rows = (
        await session.execute(
            select(KnowledgePoint.id, PinyinItem.display_text, PinyinItem.order_index)
            .join(PinyinItem)
            .where(*status_filters)
            .order_by(PinyinItem.order_index)
        )
    ).all()
    current_index = next(
        index for index, enabled in enumerate(enabled_rows) if enabled.id == knowledge_point_id
    )

    def navigation(index: int) -> PinyinNavigationItem | None:
        if index < 0 or index >= len(enabled_rows):
            return None
        target = enabled_rows[index]
        return PinyinNavigationItem(knowledge_point_id=target.id, display_text=target.display_text)

    confusing_rows = (
        await session.execute(
            select(KnowledgePoint.id, PinyinItem.display_text)
            .join(
                KnowledgeRelation,
                KnowledgeRelation.target_id == KnowledgePoint.id,
            )
            .join(PinyinItem, PinyinItem.knowledge_point_id == KnowledgePoint.id)
            .where(
                KnowledgeRelation.source_id == knowledge_point_id,
                KnowledgeRelation.relation_type == RelationType.CONFUSING,
                *status_filters,
            )
            .order_by(PinyinItem.order_index)
        )
    ).all()
    same_kind = (
        await session.execute(
            select(KnowledgePoint.id, PinyinItem.display_text, PinyinItem.order_index)
            .join(PinyinItem)
            .where(
                *status_filters,
                PinyinItem.kind == item.kind,
            )
            .order_by(PinyinItem.order_index)
        )
    ).all()
    distractors = sorted(
        (candidate for candidate in same_kind if candidate.id != knowledge_point_id),
        key=lambda candidate: (
            abs(candidate.order_index - item.order_index),
            candidate.order_index,
        ),
    )[:2]
    option_rows = sorted(
        [
            next(candidate for candidate in same_kind if candidate.id == knowledge_point_id),
            *distractors,
        ],
        key=lambda candidate: candidate.order_index,
    )
    audio = pinyin_audio_provider.resolve(item)
    base = pinyin_item_summary(point, item, state)
    return PinyinItemDetail(
        **base.model_dump(),
        canonical_key=point.canonical_key,
        pronunciation_cue=item.pronunciation_cue,
        example_pinyin=item.example_pinyin,
        description=item.description,
        parent_tip=item.parent_tip,
        audio_key=item.audio_key,
        catalog_version=item.catalog_version,
        metadata=item.metadata_json,
        audio=PinyinAudioResponse(**audio.__dict__),
        position=current_index + 1,
        total=len(enabled_rows),
        previous=navigation(current_index - 1),
        next=navigation(current_index + 1),
        confusing=[
            PinyinNavigationItem(knowledge_point_id=target.id, display_text=target.display_text)
            for target in confusing_rows
        ],
        listening_options=[
            PinyinNavigationItem(knowledge_point_id=option.id, display_text=option.display_text)
            for option in option_rows
        ],
        policy_key=state.policy_key if state else PINYIN_POLICY_KEY,
        dimensions=state.dimensions_json if state else {},
    )


async def pinyin_overview(session: AsyncSession, child_id: uuid.UUID) -> PinyinOverviewResponse:
    rows = (
        await session.execute(
            select(PinyinItem, ChildKnowledgeState)
            .join(KnowledgePoint, KnowledgePoint.id == PinyinItem.knowledge_point_id)
            .outerjoin(
                ChildKnowledgeState,
                and_(
                    ChildKnowledgeState.knowledge_point_id == PinyinItem.knowledge_point_id,
                    ChildKnowledgeState.child_id == child_id,
                ),
            )
            .where(KnowledgePoint.status == KnowledgeStatus.ACTIVE)
            .order_by(PinyinItem.order_index)
        )
    ).all()
    groups = []
    for kind in PINYIN_KINDS:
        group_states = [_state_code(state) for item, state in rows if item.kind == kind]
        groups.append(
            PinyinOverviewGroup(
                kind=kind,
                label=PINYIN_KIND_LABELS[kind],
                total=len(group_states),
                learned=sum(state != "unlearned" for state in group_states),
                stable=sum(state == "stable" for state in group_states),
            )
        )
    blending_items = list(
        (
            await session.scalars(
                select(AssessmentItem).where(
                    AssessmentItem.child_id == child_id,
                    AssessmentItem.skill_dimension == "blending",
                )
            )
        ).all()
    )
    all_states = [_state_code(state) for _, state in rows]
    return PinyinOverviewResponse(
        child_id=child_id,
        catalog_version=PINYIN_CATALOG_VERSION,
        total=len(rows),
        learned=sum(state != "unlearned" for state in all_states),
        stable=sum(state == "stable" for state in all_states),
        groups=groups,
        blending_state=pinyin_dimension_state(blending_items),
        blending_attempts=len(blending_items),
    )


async def get_or_create_pinyin_today(
    session: AsyncSession,
    child_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> PinyinTodayResponse | None:
    current = now or datetime.now(UTC)
    settings = await session.scalar(
        select(ChildLearningSettings).where(ChildLearningSettings.child_id == child_id)
    )
    timezone_name = settings.timezone if settings is not None else "Asia/Shanghai"
    plan_date = current.astimezone(ZoneInfo(timezone_name)).date()
    plan = await session.scalar(
        select(PinyinDailyPlan).where(
            PinyinDailyPlan.child_id == child_id,
            PinyinDailyPlan.plan_date == plan_date,
        )
    )
    if plan is None:
        catalog_exists = await session.scalar(select(PinyinItem.knowledge_point_id).limit(1))
        if catalog_exists is None:
            return None
        new_rows = (
            await session.execute(
                select(KnowledgePoint, PinyinItem)
                .join(PinyinItem)
                .outerjoin(
                    ChildKnowledgeState,
                    and_(
                        ChildKnowledgeState.knowledge_point_id == KnowledgePoint.id,
                        ChildKnowledgeState.child_id == child_id,
                    ),
                )
                .where(
                    KnowledgePoint.status == KnowledgeStatus.ACTIVE,
                    ChildKnowledgeState.id.is_(None),
                )
                .order_by(PinyinItem.order_index)
                .limit(PINYIN_NEW_LIMIT)
            )
        ).all()
        new_ids = {point.id for point, _ in new_rows}
        review_rows = (
            await session.execute(
                select(KnowledgePoint, PinyinItem)
                .join(PinyinItem)
                .join(
                    ChildReviewSchedule,
                    ChildReviewSchedule.knowledge_point_id == KnowledgePoint.id,
                )
                .where(
                    ChildReviewSchedule.child_id == child_id,
                    ChildReviewSchedule.next_review_at <= current,
                    ChildReviewSchedule.algorithm_version == "pinyin-review-v1",
                    KnowledgePoint.status == KnowledgeStatus.ACTIVE,
                    KnowledgePoint.id.not_in(new_ids),
                )
                .order_by(ChildReviewSchedule.next_review_at, PinyinItem.order_index)
                .limit(PINYIN_REVIEW_LIMIT)
            )
        ).all()
        plan = PinyinDailyPlan(
            child_id=child_id,
            plan_date=plan_date,
            timezone=timezone_name,
            new_count=len(new_rows),
            review_count=len(review_rows),
            completed_count=0,
            status=DailyPlanStatus.PENDING,
        )
        session.add(plan)
        await session.flush()
        for position, (point, _) in enumerate([*new_rows, *review_rows]):
            session.add(
                PinyinDailyPlanItem(
                    pinyin_daily_plan_id=plan.id,
                    knowledge_point_id=point.id,
                    item_kind=(
                        PinyinPlanItemKind.NEW
                        if position < len(new_rows)
                        else PinyinPlanItemKind.REVIEW
                    ),
                    status=PlanItemStatus.PENDING,
                    position=position,
                )
            )
        await session.flush()
    return await _today_response(session, plan)


async def _today_response(session: AsyncSession, plan: PinyinDailyPlan) -> PinyinTodayResponse:
    rows = (
        await session.execute(
            select(PinyinDailyPlanItem, KnowledgePoint, PinyinItem, ChildKnowledgeState)
            .join(KnowledgePoint, KnowledgePoint.id == PinyinDailyPlanItem.knowledge_point_id)
            .join(PinyinItem, PinyinItem.knowledge_point_id == KnowledgePoint.id)
            .outerjoin(
                ChildKnowledgeState,
                and_(
                    ChildKnowledgeState.knowledge_point_id == KnowledgePoint.id,
                    ChildKnowledgeState.child_id == plan.child_id,
                ),
            )
            .where(PinyinDailyPlanItem.pinyin_daily_plan_id == plan.id)
            .order_by(PinyinDailyPlanItem.position)
        )
    ).all()
    new_items = [
        pinyin_item_summary(point, item, state)
        for plan_item, point, item, state in rows
        if plan_item.item_kind == PinyinPlanItemKind.NEW
    ]
    review_items = [
        pinyin_item_summary(point, item, state)
        for plan_item, point, item, state in rows
        if plan_item.item_kind == PinyinPlanItemKind.REVIEW
    ]
    return PinyinTodayResponse(
        plan_id=plan.id,
        child_id=plan.child_id,
        plan_date=plan.plan_date,
        new_items=new_items,
        review_items=review_items,
        completed_count=plan.completed_count,
        target_count=plan.new_count + plan.review_count,
        status=plan.status,
    )


async def update_pinyin_daily_progress(
    session: AsyncSession,
    child_id: uuid.UUID,
    knowledge_point_ids: set[uuid.UUID],
    *,
    now: datetime,
) -> None:
    settings = await session.scalar(
        select(ChildLearningSettings).where(ChildLearningSettings.child_id == child_id)
    )
    timezone_name = settings.timezone if settings is not None else "Asia/Shanghai"
    plan_date = now.astimezone(ZoneInfo(timezone_name)).date()
    plan = await session.scalar(
        select(PinyinDailyPlan).where(
            PinyinDailyPlan.child_id == child_id,
            PinyinDailyPlan.plan_date == plan_date,
        )
    )
    if plan is None:
        return
    items = list(
        (
            await session.scalars(
                select(PinyinDailyPlanItem).where(
                    PinyinDailyPlanItem.pinyin_daily_plan_id == plan.id
                )
            )
        ).all()
    )
    for item in items:
        if (
            item.knowledge_point_id in knowledge_point_ids
            and item.status != PlanItemStatus.COMPLETED
        ):
            item.status = PlanItemStatus.COMPLETED
            item.completed_at = now
    plan.completed_count = sum(item.status == PlanItemStatus.COMPLETED for item in items)
    target = plan.new_count + plan.review_count
    if target and plan.completed_count >= target:
        plan.status = DailyPlanStatus.COMPLETED
    elif plan.completed_count:
        plan.status = DailyPlanStatus.IN_PROGRESS
    else:
        plan.status = DailyPlanStatus.PENDING
    await session.flush()


async def pinyin_practice_page(session: AsyncSession) -> PinyinPracticePage:
    initial_item = aliased(PinyinItem)
    final_item = aliased(PinyinItem)
    rows = (
        await session.execute(
            select(PinyinPracticeItem, initial_item, final_item)
            .join(
                initial_item,
                initial_item.knowledge_point_id == PinyinPracticeItem.initial_knowledge_point_id,
            )
            .join(
                final_item,
                final_item.knowledge_point_id == PinyinPracticeItem.final_knowledge_point_id,
            )
            .order_by(PinyinPracticeItem.order_index)
        )
    ).all()
    return PinyinPracticePage(
        items=[
            PinyinPracticeResponse(
                id=practice.id,
                practice_key=practice.practice_key,
                initial_knowledge_point_id=practice.initial_knowledge_point_id,
                final_knowledge_point_id=practice.final_knowledge_point_id,
                initial=initial.symbol,
                underlying_final=practice.underlying_final,
                display_final=practice.display_final,
                display_syllable=practice.display_syllable,
                pronunciation_cue=practice.pronunciation_cue,
                order_index=practice.order_index,
                metadata=practice.metadata_json,
            )
            for practice, initial, _ in rows
        ],
        total=len(rows),
    )


async def pinyin_history(
    session: AsyncSession, child_id: uuid.UUID, *, limit: int = 30
) -> PinyinHistoryResponse:
    grouped: dict[tuple[datetime, str, uuid.UUID, str, str], list[PinyinHistoryEvidence]] = (
        defaultdict(list)
    )
    learning_rows = (
        await session.execute(
            select(LearningSession, LearningRecord, PinyinItem, User)
            .join(LearningRecord, LearningRecord.session_id == LearningSession.id)
            .join(PinyinItem, PinyinItem.knowledge_point_id == LearningRecord.knowledge_point_id)
            .join(User, User.id == LearningSession.actor_user_id)
            .where(LearningSession.child_id == child_id)
            .order_by(LearningRecord.learned_at.desc())
            .limit(limit * 5)
        )
    ).all()
    for learning_session, record, item, user in learning_rows:
        occurred_at = learning_session.completed_at or learning_session.started_at
        key = (
            occurred_at,
            "learning",
            learning_session.id,
            learning_session.source,
            user.display_name,
        )
        grouped[key].append(
            PinyinHistoryEvidence(
                evidence_id=record.id,
                evidence_type="learning",
                knowledge_point_id=record.knowledge_point_id,
                display_text=item.display_text,
                dimension=None,
                outcome=record.activity_type,
                occurred_at=record.learned_at,
            )
        )
    assessment_rows = (
        await session.execute(
            select(AssessmentSession, AssessmentItem, PinyinItem, User)
            .join(AssessmentItem, AssessmentItem.session_id == AssessmentSession.id)
            .join(PinyinItem, PinyinItem.knowledge_point_id == AssessmentItem.knowledge_point_id)
            .join(User, User.id == AssessmentSession.evaluator_user_id)
            .where(AssessmentSession.child_id == child_id)
            .order_by(AssessmentItem.assessed_at.desc())
            .limit(limit * 5)
        )
    ).all()
    for assessment_session, item_evidence, item, user in assessment_rows:
        occurred_at = assessment_session.completed_at or assessment_session.started_at
        key = (
            occurred_at,
            "assessment",
            assessment_session.id,
            assessment_session.source,
            user.display_name,
        )
        grouped[key].append(
            PinyinHistoryEvidence(
                evidence_id=item_evidence.id,
                evidence_type="assessment",
                knowledge_point_id=item_evidence.knowledge_point_id,
                display_text=item.display_text,
                dimension=item_evidence.skill_dimension,
                outcome=item_evidence.outcome,
                occurred_at=item_evidence.assessed_at,
            )
        )
    sessions = [
        PinyinHistorySession(
            session_id=session_id,
            source=source,
            actor_display_name=actor,
            occurred_at=occurred_at,
            evidence=sorted(evidence, key=lambda row: row.occurred_at),
        )
        for (occurred_at, _kind, session_id, source, actor), evidence in grouped.items()
    ]
    sessions.sort(key=lambda row: row.occurred_at, reverse=True)
    return PinyinHistoryResponse(child_id=child_id, items=sessions[:limit])
