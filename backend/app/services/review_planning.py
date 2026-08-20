"""Deterministic adaptive review, daily planning, and bounded literacy services."""

import math
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ActivityKnowledgePoint,
    AssessmentItem,
    AssessmentOutcome,
    AssessmentSession,
    AssessmentSessionPlan,
    AssessmentSessionTarget,
    AssessmentSource,
    CatalogRelease,
    ChildCourseEnrollment,
    ChildKnowledgeState,
    ChildLearningSettings,
    ChildReviewSchedule,
    ChineseCharacter,
    Course,
    CourseUnit,
    DailyLearningPlan,
    DailyPlanItem,
    DailyPlanItemKind,
    DailyPlanStatus,
    KnowledgePoint,
    KnowledgePointRole,
    KnowledgeStatus,
    LearningActivity,
    LearningRecord,
    LiteracyEstimate,
    MasteryLevel,
    PlanItemStatus,
    SessionStatus,
)
from app.schemas.learning import (
    AssessmentBatchSubmit,
    AssessmentHistoryEntry,
    AssessmentTargetResponse,
    DailyPlanItemResponse,
    DailyPlanResponse,
    LearningSettingsResponse,
    LearningSettingsUpdate,
    LiteracyEstimateResponse,
    PlannedAssessmentResponse,
    ReviewBacklogResponse,
    ReviewScheduleResponse,
)
from app.services.daily_reading import daily_reading_response, ensure_daily_reading_task
from app.services.mastery import recompute_child_knowledge_state

REVIEW_ALGORITHM_VERSION = "review-v1"
PLAN_ALGORITHM_VERSION = "plan-v1"
SAMPLING_VERSION = "sampling-v1"
LITERACY_ESTIMATION_VERSION = "literacy-v1"
INTERVALS = (1, 3, 7, 14, 30, 60, 90)
LITERACY_MINIMUM_SAMPLE = 20
LITERACY_LIMITATION = "该结果仅代表当前系统字库范围，不是孩子全部汉字识字量。"


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@dataclass(frozen=True)
class ReviewProjection:
    last_review_at: datetime
    next_review_at: datetime
    interval_days: int
    interval_stage: int
    last_outcome: str
    scheduling_reason: str


def project_review_schedule(
    learning_records: list[LearningRecord], assessment_items: list[AssessmentItem]
) -> ReviewProjection | None:
    """Replay evidence into the conservative Review V1 interval ladder."""

    events: list[tuple[datetime, str, str, str]] = []
    for record in learning_records:
        events.append((_utc(record.learned_at), "learning", record.activity_type, str(record.id)))
    for item in assessment_items:
        events.append((_utc(item.assessed_at), "assessment", item.outcome, str(item.id)))
    if not events:
        return None

    stage = 0
    last_at = events[0][0]
    last_outcome = "introduced"
    reason = "introduced_baseline"
    for occurred_at, event_type, outcome, _event_id in sorted(
        events, key=lambda event: (event[0], event[1], event[3])
    ):
        last_at = occurred_at
        if event_type == "learning":
            stage = 0
            last_outcome = outcome
            reason = "learning_or_relearning"
        elif outcome == AssessmentOutcome.CORRECT:
            stage = min(stage + 1, len(INTERVALS) - 1)
            last_outcome = outcome
            reason = "independent_correct_progression"
        elif outcome == AssessmentOutcome.HINTED_CORRECT:
            stage = max(0, stage - 1)
            last_outcome = outcome
            reason = "hinted_correct_shortened"
        elif outcome == AssessmentOutcome.UNCERTAIN:
            stage = max(0, stage - 2)
            last_outcome = outcome
            reason = "uncertain_strongly_shortened"
        else:
            stage = 0
            last_outcome = outcome
            reason = "incorrect_reset"

    interval_days = INTERVALS[stage]
    return ReviewProjection(
        last_review_at=last_at,
        next_review_at=last_at + timedelta(days=interval_days),
        interval_days=interval_days,
        interval_stage=stage,
        last_outcome=last_outcome,
        scheduling_reason=reason,
    )


async def recompute_review_schedule(
    session: AsyncSession, child_id: uuid.UUID, knowledge_point_id: uuid.UUID
) -> ChildReviewSchedule | None:
    learning = list(
        (
            await session.scalars(
                select(LearningRecord).where(
                    LearningRecord.child_id == child_id,
                    LearningRecord.knowledge_point_id == knowledge_point_id,
                )
            )
        ).all()
    )
    assessments = list(
        (
            await session.scalars(
                select(AssessmentItem).where(
                    AssessmentItem.child_id == child_id,
                    AssessmentItem.knowledge_point_id == knowledge_point_id,
                )
            )
        ).all()
    )
    projection = project_review_schedule(learning, assessments)
    schedule = await session.scalar(
        select(ChildReviewSchedule).where(
            ChildReviewSchedule.child_id == child_id,
            ChildReviewSchedule.knowledge_point_id == knowledge_point_id,
        )
    )
    if projection is None:
        return schedule
    if schedule is None:
        schedule = ChildReviewSchedule(child_id=child_id, knowledge_point_id=knowledge_point_id)
        session.add(schedule)
    for field, value in projection.__dict__.items():
        setattr(schedule, field, value)
    schedule.algorithm_version = REVIEW_ALGORITHM_VERSION
    await session.flush()
    return schedule


async def recompute_child_review_schedules(
    session: AsyncSession, child_id: uuid.UUID | None = None
) -> int:
    pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()
    for model in (LearningRecord, AssessmentItem):
        query = select(model.child_id, model.knowledge_point_id)
        if child_id is not None:
            query = query.where(model.child_id == child_id)
        pairs.update((row[0], row[1]) for row in (await session.execute(query)).all())
    for pair_child_id, point_id in sorted(pairs, key=lambda pair: (str(pair[0]), str(pair[1]))):
        await recompute_review_schedule(session, pair_child_id, point_id)
    return len(pairs)


async def ensure_learning_settings(
    session: AsyncSession, child_id: uuid.UUID
) -> ChildLearningSettings:
    settings = await session.scalar(
        select(ChildLearningSettings).where(ChildLearningSettings.child_id == child_id)
    )
    if settings is None:
        settings = ChildLearningSettings(child_id=child_id)
        session.add(settings)
        await session.flush()
    return settings


def settings_response(settings: ChildLearningSettings) -> LearningSettingsResponse:
    return LearningSettingsResponse(
        max_new_characters_per_day=settings.max_new_characters_per_day,
        daily_review_capacity=settings.daily_review_capacity,
        weekly_assessment_enabled=settings.weekly_assessment_enabled,
        monthly_assessment_enabled=settings.monthly_assessment_enabled,
        timezone=settings.timezone,
    )


async def update_learning_settings(
    session: AsyncSession,
    child_id: uuid.UUID,
    payload: LearningSettingsUpdate,
) -> LearningSettingsResponse:
    settings = await ensure_learning_settings(session, child_id)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(settings, field, value)
    await session.commit()
    return settings_response(settings)


async def _enabled_catalog_size(session: AsyncSession) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(ChineseCharacter)
            .join(KnowledgePoint)
            .where(
                KnowledgePoint.status == KnowledgeStatus.ACTIVE,
                ChineseCharacter.is_enabled.is_(True),
            )
        )
        or 0
    )


async def _current_catalog_frame(session: AsyncSession) -> tuple[str, int]:
    release = await session.scalar(
        select(CatalogRelease).where(CatalogRelease.is_current.is_(True))
    )
    if release is not None:
        return release.catalog_version, release.item_count
    return "growth-starter-v1", await _enabled_catalog_size(session)


async def _review_rows(
    session: AsyncSession, child_id: uuid.UUID, now: datetime
) -> list[tuple[ChildReviewSchedule, ChildKnowledgeState | None, KnowledgePoint, ChineseCharacter]]:
    return list(
        (
            await session.execute(
                select(ChildReviewSchedule, ChildKnowledgeState, KnowledgePoint, ChineseCharacter)
                .join(
                    KnowledgePoint,
                    KnowledgePoint.id == ChildReviewSchedule.knowledge_point_id,
                )
                .join(
                    ChineseCharacter,
                    ChineseCharacter.knowledge_point_id == KnowledgePoint.id,
                )
                .outerjoin(
                    ChildKnowledgeState,
                    and_(
                        ChildKnowledgeState.child_id == ChildReviewSchedule.child_id,
                        ChildKnowledgeState.knowledge_point_id
                        == ChildReviewSchedule.knowledge_point_id,
                    ),
                )
                .where(
                    ChildReviewSchedule.child_id == child_id,
                    ChildReviewSchedule.next_review_at <= now,
                    KnowledgePoint.status == KnowledgeStatus.ACTIVE,
                    ChineseCharacter.is_enabled.is_(True),
                )
            )
        ).all()
    )


def _review_sort_key(
    row: tuple[ChildReviewSchedule, ChildKnowledgeState | None, KnowledgePoint, ChineseCharacter],
    now: datetime,
) -> tuple:
    schedule, state, _, character = row
    overdue_seconds = max(0.0, (_utc(now) - _utc(schedule.next_review_at)).total_seconds())
    risk = {
        AssessmentOutcome.INCORRECT: 3,
        AssessmentOutcome.UNCERTAIN: 2,
        AssessmentOutcome.HINTED_CORRECT: 1,
    }.get(schedule.last_outcome, 0)
    return (
        -overdue_seconds,
        -int(state.is_priority if state else False),
        -risk,
        _utc(schedule.next_review_at),
        character.character,
    )


def _review_response(
    row: tuple[ChildReviewSchedule, ChildKnowledgeState | None, KnowledgePoint, ChineseCharacter],
    now: datetime,
) -> ReviewScheduleResponse:
    schedule, state, point, character = row
    overdue_days = max(
        0, math.floor((_utc(now) - _utc(schedule.next_review_at)).total_seconds() / 86400)
    )
    return ReviewScheduleResponse(
        knowledge_point_id=point.id,
        character=character.character,
        pinyin=character.pinyin,
        last_review_at=schedule.last_review_at,
        next_review_at=schedule.next_review_at,
        interval_days=schedule.interval_days,
        interval_stage=schedule.interval_stage,
        last_outcome=schedule.last_outcome,
        scheduling_reason=schedule.scheduling_reason,
        is_priority=state.is_priority if state else False,
        overdue_days=overdue_days,
        algorithm_version=schedule.algorithm_version,
    )


async def get_review_backlog(
    session: AsyncSession, child_id: uuid.UUID, *, now: datetime | None = None
) -> ReviewBacklogResponse:
    now = now or datetime.now(UTC)
    await recompute_child_review_schedules(session, child_id)
    settings = await ensure_learning_settings(session, child_id)
    rows = sorted(
        await _review_rows(session, child_id, now), key=lambda row: _review_sort_key(row, now)
    )
    selected = rows[: settings.daily_review_capacity]
    await session.commit()
    return ReviewBacklogResponse(
        due_count=len(rows),
        selected_count=len(selected),
        capacity=settings.daily_review_capacity,
        estimated_days_to_clear=(
            math.ceil(len(rows) / settings.daily_review_capacity) if rows else 0
        ),
        items=[_review_response(row, now) for row in selected],
    )


async def _recent_retention(
    session: AsyncSession, child_id: uuid.UUID, now: datetime
) -> tuple[int, float | None, float | None]:
    rows = list(
        (
            await session.scalars(
                select(AssessmentItem).where(
                    AssessmentItem.child_id == child_id,
                    AssessmentItem.assessed_at >= now - timedelta(days=7),
                )
            )
        ).all()
    )
    if not rows:
        return 0, None, None
    correct_rate = sum(item.outcome == AssessmentOutcome.CORRECT for item in rows) / len(rows)
    risk_rate = sum(
        item.outcome in (AssessmentOutcome.UNCERTAIN, AssessmentOutcome.INCORRECT) for item in rows
    ) / len(rows)
    return len(rows), round(correct_rate, 4), round(risk_rate, 4)


def recommend_new_load(
    maximum: int,
    backlog: int,
    capacity: int,
    recent_count: int,
    correct_rate: float | None,
    risk_rate: float | None,
) -> tuple[int, str]:
    if maximum == 0:
        return 0, "家长已将每日新字上限设置为 0，今天只安排复习。"
    if backlog >= capacity * 2:
        return 0, f"当前有 {backlog} 个知识点等待复习，积压较多，今天以复习为主。"
    if backlog >= capacity:
        count = min(maximum, 2)
        return count, f"当前有 {backlog} 个知识点等待复习，已降低新字数量并优先清理积压。"
    if recent_count >= 5 and (correct_rate or 0) < 0.5:
        count = min(maximum, 1)
        return count, "最近 7 天独立认识率偏低，今天减少新字并加强复习。"
    if recent_count >= 5 and ((correct_rate or 0) < 0.75 or (risk_rate or 0) >= 0.3):
        count = min(maximum, 3)
        return count, "最近复习中仍有一些不确定或错误，今天适当减少新字。"
    if recent_count < 5:
        return maximum, "近期数据还不多，按家长设置的上限安排少量新字并持续观察。"
    return maximum, "最近复习状态稳定且积压较少，今天按正常上限安排新字。"


async def _new_character_rows(
    session: AsyncSession, child_id: uuid.UUID, limit: int
) -> list[tuple[KnowledgePoint, ChineseCharacter, str]]:
    if limit <= 0:
        return []
    learned = select(LearningRecord.id).where(
        LearningRecord.child_id == child_id,
        LearningRecord.knowledge_point_id == KnowledgePoint.id,
    )
    selected: list[tuple[KnowledgePoint, ChineseCharacter, str]] = []
    selected_ids: set[uuid.UUID] = set()

    priority_rows = list(
        (
            await session.execute(
                select(KnowledgePoint, ChineseCharacter)
                .join(ChineseCharacter)
                .join(
                    ChildKnowledgeState,
                    and_(
                        ChildKnowledgeState.knowledge_point_id == KnowledgePoint.id,
                        ChildKnowledgeState.child_id == child_id,
                    ),
                )
                .where(
                    KnowledgePoint.status == KnowledgeStatus.ACTIVE,
                    ChineseCharacter.is_enabled.is_(True),
                    ChildKnowledgeState.is_priority.is_(True),
                    ~learned.exists(),
                )
                .order_by(ChineseCharacter.created_at, ChineseCharacter.character)
                .limit(limit)
            )
        ).all()
    )
    for point, character in priority_rows:
        selected.append((point, character, "priority_not_introduced"))
        selected_ids.add(point.id)

    course_rows = list(
        (
            await session.execute(
                select(KnowledgePoint, ChineseCharacter)
                .join(ChineseCharacter)
                .join(
                    ActivityKnowledgePoint,
                    ActivityKnowledgePoint.knowledge_point_id == KnowledgePoint.id,
                )
                .join(
                    LearningActivity,
                    LearningActivity.id == ActivityKnowledgePoint.activity_id,
                )
                .join(CourseUnit, CourseUnit.id == LearningActivity.course_unit_id)
                .join(Course, Course.id == CourseUnit.course_id)
                .join(
                    ChildCourseEnrollment,
                    ChildCourseEnrollment.course_id == Course.id,
                )
                .where(
                    ChildCourseEnrollment.child_id == child_id,
                    ChildCourseEnrollment.status == "active",
                    Course.status == "enabled",
                    CourseUnit.status == "enabled",
                    LearningActivity.status == "enabled",
                    LearningActivity.activity_type == "character_learning",
                    ActivityKnowledgePoint.role == KnowledgePointRole.PRIMARY,
                    KnowledgePoint.status == KnowledgeStatus.ACTIVE,
                    ChineseCharacter.is_enabled.is_(True),
                    ~learned.exists(),
                )
                .order_by(
                    ChildCourseEnrollment.path_order,
                    CourseUnit.order_index,
                    LearningActivity.order_index,
                    ActivityKnowledgePoint.order_index,
                )
            )
        ).all()
    )
    for point, character in course_rows:
        if point.id not in selected_ids:
            selected.append((point, character, "active_course_order"))
            selected_ids.add(point.id)
        if len(selected) >= limit:
            return selected

    fallback_rows = list(
        (
            await session.execute(
                select(KnowledgePoint, ChineseCharacter)
                .join(ChineseCharacter)
                .where(
                    KnowledgePoint.status == KnowledgeStatus.ACTIVE,
                    ChineseCharacter.is_enabled.is_(True),
                    ~learned.exists(),
                    KnowledgePoint.id.not_in(selected_ids),
                )
                .order_by(ChineseCharacter.created_at, ChineseCharacter.character)
                .limit(limit - len(selected))
            )
        ).all()
    )
    selected.extend(
        (point, character, "fallback_canonical_order") for point, character in fallback_rows
    )
    return selected


async def _period_status(
    session: AsyncSession,
    child_id: uuid.UUID,
    source: str,
    local_date: date,
    timezone: str,
) -> str:
    settings_field = (
        "weekly_assessment_enabled"
        if source == AssessmentSource.WEEKLY_CHECK
        else "monthly_assessment_enabled"
    )
    settings = await ensure_learning_settings(session, child_id)
    if not getattr(settings, settings_field):
        return "disabled"
    sessions = list(
        (
            await session.scalars(
                select(AssessmentSession)
                .where(AssessmentSession.child_id == child_id, AssessmentSession.source == source)
                .order_by(AssessmentSession.started_at.desc())
            )
        ).all()
    )
    for assessment in sessions:
        started_date = _utc(assessment.started_at).astimezone(ZoneInfo(timezone)).date()
        same_period = (
            started_date.isocalendar()[:2] == local_date.isocalendar()[:2]
            if source == AssessmentSource.WEEKLY_CHECK
            else (started_date.year, started_date.month) == (local_date.year, local_date.month)
        )
        if same_period:
            return assessment.status
    return "pending"


async def get_or_create_daily_plan(
    session: AsyncSession, child_id: uuid.UUID, *, now: datetime | None = None
) -> DailyPlanResponse:
    now = now or datetime.now(UTC)
    settings = await ensure_learning_settings(session, child_id)
    local_date = now.astimezone(ZoneInfo(settings.timezone)).date()
    plan = await session.scalar(
        select(DailyLearningPlan).where(
            DailyLearningPlan.child_id == child_id,
            DailyLearningPlan.plan_date == local_date,
        )
    )
    recent_count, correct_rate, risk_rate = await _recent_retention(session, child_id, now)
    if plan is None:
        await recompute_child_review_schedules(session, child_id)
        review_rows = sorted(
            await _review_rows(session, child_id, now), key=lambda row: _review_sort_key(row, now)
        )
        selected_reviews = review_rows[: settings.daily_review_capacity]
        new_count, reason = recommend_new_load(
            settings.max_new_characters_per_day,
            len(review_rows),
            settings.daily_review_capacity,
            recent_count,
            correct_rate,
            risk_rate,
        )
        new_rows = await _new_character_rows(session, child_id, new_count)
        plan = DailyLearningPlan(
            child_id=child_id,
            plan_date=local_date,
            timezone=settings.timezone,
            recommended_new_count=len(new_rows),
            review_count=len(selected_reviews),
            due_count=len(review_rows),
            estimated_backlog_days=(
                math.ceil(len(review_rows) / settings.daily_review_capacity) if review_rows else 0
            ),
            recommendation_reason=reason,
            algorithm_version=PLAN_ALGORITHM_VERSION,
        )
        session.add(plan)
        await session.flush()
        for position, row in enumerate(new_rows):
            point, _, selection_reason = row
            session.add(
                DailyPlanItem(
                    daily_plan_id=plan.id,
                    knowledge_point_id=point.id,
                    item_kind=DailyPlanItemKind.NEW,
                    position=position,
                    selection_reason=selection_reason,
                )
            )
        for position, row in enumerate(selected_reviews):
            schedule, state, point, _ = row
            reason_label = "priority" if state and state.is_priority else schedule.scheduling_reason
            session.add(
                DailyPlanItem(
                    daily_plan_id=plan.id,
                    knowledge_point_id=point.id,
                    item_kind=DailyPlanItemKind.REVIEW,
                    position=position,
                    selection_reason=reason_label,
                )
            )
        await session.flush()

    items = list(
        (
            await session.execute(
                select(DailyPlanItem, ChineseCharacter)
                .join(KnowledgePoint, KnowledgePoint.id == DailyPlanItem.knowledge_point_id)
                .join(ChineseCharacter, ChineseCharacter.knowledge_point_id == KnowledgePoint.id)
                .where(DailyPlanItem.daily_plan_id == plan.id)
                .order_by(DailyPlanItem.item_kind, DailyPlanItem.position)
            )
        ).all()
    )
    weekly_status = await _period_status(
        session, child_id, AssessmentSource.WEEKLY_CHECK, local_date, settings.timezone
    )
    monthly_status = await _period_status(
        session, child_id, AssessmentSource.MONTHLY_ASSESSMENT, local_date, settings.timezone
    )
    latest_estimate = await session.scalar(
        select(LiteracyEstimate)
        .where(LiteracyEstimate.child_id == child_id)
        .order_by(LiteracyEstimate.created_at.desc())
    )
    catalog_size = await _enabled_catalog_size(session)
    reading_task = await ensure_daily_reading_task(session, plan)
    reading_response = await daily_reading_response(session, reading_task)
    await session.commit()
    return DailyPlanResponse(
        id=plan.id,
        child_id=plan.child_id,
        plan_date=plan.plan_date,
        timezone=plan.timezone,
        recommended_new_count=plan.recommended_new_count,
        review_count=plan.review_count,
        due_count=plan.due_count,
        estimated_backlog_days=plan.estimated_backlog_days,
        recommendation_reason=plan.recommendation_reason,
        new_completed_count=plan.new_completed_count,
        review_completed_count=plan.review_completed_count,
        status=plan.status,
        recent_independent_correct_rate=correct_rate,
        weekly_status=weekly_status,
        monthly_status=monthly_status,
        literacy_status=(
            "available" if latest_estimate and latest_estimate.is_sufficient else "insufficient"
        ),
        literacy_estimate=latest_estimate.estimate if latest_estimate else None,
        literacy_catalog_size=catalog_size,
        items=[
            DailyPlanItemResponse(
                knowledge_point_id=item.knowledge_point_id,
                character=character.character,
                pinyin=character.pinyin,
                common_words=character.common_words,
                simple_meaning=character.simple_meaning,
                example_sentence=character.example_sentence,
                item_kind=item.item_kind,
                status=item.status,
                position=item.position,
                selection_reason=item.selection_reason,
            )
            for item, character in items
        ],
        reading=reading_response,
    )


def _refresh_plan_status(plan: DailyLearningPlan) -> None:
    if (
        plan.new_completed_count >= plan.recommended_new_count
        and plan.review_completed_count >= plan.review_count
    ):
        plan.status = DailyPlanStatus.COMPLETED
    elif plan.new_completed_count or plan.review_completed_count:
        plan.status = DailyPlanStatus.IN_PROGRESS


async def update_daily_learning_progress(
    session: AsyncSession,
    child_id: uuid.UUID,
    knowledge_point_ids: set[uuid.UUID],
    *,
    now: datetime,
) -> None:
    settings = await session.scalar(
        select(ChildLearningSettings).where(ChildLearningSettings.child_id == child_id)
    )
    timezone = settings.timezone if settings else "Asia/Shanghai"
    local_date = now.astimezone(ZoneInfo(timezone)).date()
    plan = await session.scalar(
        select(DailyLearningPlan).where(
            DailyLearningPlan.child_id == child_id,
            DailyLearningPlan.plan_date == local_date,
        )
    )
    if plan is None:
        return
    items = list(
        (
            await session.scalars(
                select(DailyPlanItem).where(
                    DailyPlanItem.daily_plan_id == plan.id,
                    DailyPlanItem.item_kind == DailyPlanItemKind.NEW,
                    DailyPlanItem.knowledge_point_id.in_(knowledge_point_ids),
                    DailyPlanItem.status == PlanItemStatus.PENDING,
                )
            )
        ).all()
    )
    for item in items:
        item.status = PlanItemStatus.COMPLETED
        item.completed_at = now
    plan.new_completed_count += len(items)
    _refresh_plan_status(plan)


async def _sample_periodic_targets(
    session: AsyncSession, child_id: uuid.UUID, source: str, now: datetime
) -> list[tuple[uuid.UUID, str]]:
    rows = list(
        (
            await session.execute(
                select(KnowledgePoint, ChineseCharacter, ChildKnowledgeState, ChildReviewSchedule)
                .join(ChineseCharacter)
                .outerjoin(
                    ChildKnowledgeState,
                    and_(
                        ChildKnowledgeState.child_id == child_id,
                        ChildKnowledgeState.knowledge_point_id == KnowledgePoint.id,
                    ),
                )
                .outerjoin(
                    ChildReviewSchedule,
                    and_(
                        ChildReviewSchedule.child_id == child_id,
                        ChildReviewSchedule.knowledge_point_id == KnowledgePoint.id,
                    ),
                )
                .where(
                    KnowledgePoint.status == KnowledgeStatus.ACTIVE,
                    ChineseCharacter.is_enabled.is_(True),
                )
                .order_by(ChineseCharacter.created_at, ChineseCharacter.character)
            )
        ).all()
    )
    learned_ids = set(
        (
            await session.scalars(
                select(LearningRecord.knowledge_point_id).where(LearningRecord.child_id == child_id)
            )
        ).all()
    )

    def add_unique(
        output: list[tuple[uuid.UUID, str]],
        candidates: list,
        label: str,
        label_limit: int,
        total_limit: int,
    ) -> None:
        existing = {point_id for point_id, _ in output}
        for point, _, _, _ in candidates:
            if len(output) >= total_limit:
                break
            if (
                point.id not in existing
                and len([value for value in output if value[1] == label]) < label_limit
            ):
                output.append((point.id, label))
                existing.add(point.id)

    weak = [
        row
        for row in rows
        if row[2]
        and (
            row[2].is_priority
            or row[2].mastery_level in (MasteryLevel.INTRODUCED, MasteryLevel.RECOGNIZING)
            or (
                row[3]
                and row[3].last_outcome
                in (AssessmentOutcome.UNCERTAIN, AssessmentOutcome.INCORRECT)
            )
        )
    ]
    recent = [
        row
        for row in rows
        if row[2]
        and row[2].first_introduced_at
        and _utc(row[2].first_introduced_at) >= now - timedelta(days=30)
    ]
    stable = [row for row in rows if row[2] and row[2].mastery_level == MasteryLevel.STABLE]
    learned = [row for row in rows if row[0].id in learned_ids]
    unseen = [row for row in rows if row[0].id not in learned_ids]
    selected: list[tuple[uuid.UUID, str]] = []
    if source == AssessmentSource.WEEKLY_CHECK:
        target = min(15, len(learned))
        add_unique(selected, weak, "weak_or_priority", max(1, target // 2), target)
        add_unique(selected, recent, "recently_learned", max(1, target // 2), target)
        add_unique(selected, stable, "stable_maintenance", max(1, target // 4), target)
        add_unique(selected, learned, "learned_fill", target, target)
    else:
        target = min(50, len(rows))
        unseen_target = min(len(unseen), max(1, target // 5)) if target else 0
        add_unique(selected, weak, "weak_or_priority", max(1, target // 4), target)
        add_unique(selected, stable, "stable_long_unseen", max(1, target // 4), target)
        add_unique(selected, unseen, "unseen_not_system_taught", unseen_target, target)
        add_unique(
            selected,
            learned,
            "learned_active",
            max(0, target - unseen_target),
            target,
        )
        add_unique(selected, rows, "catalog_fill", target, target)
    return selected


async def _session_response(
    session: AsyncSession, assessment: AssessmentSession
) -> PlannedAssessmentResponse:
    plan = await session.scalar(
        select(AssessmentSessionPlan).where(
            AssessmentSessionPlan.assessment_session_id == assessment.id
        )
    )
    if plan is None:
        raise ValueError("Assessment session has no persisted sampling plan")
    rows = list(
        (
            await session.execute(
                select(AssessmentSessionTarget, ChineseCharacter, AssessmentItem)
                .join(
                    KnowledgePoint,
                    KnowledgePoint.id == AssessmentSessionTarget.knowledge_point_id,
                )
                .join(ChineseCharacter, ChineseCharacter.knowledge_point_id == KnowledgePoint.id)
                .outerjoin(
                    AssessmentItem,
                    and_(
                        AssessmentItem.session_id == assessment.id,
                        AssessmentItem.knowledge_point_id
                        == AssessmentSessionTarget.knowledge_point_id,
                    ),
                )
                .where(AssessmentSessionTarget.assessment_session_id == assessment.id)
                .order_by(AssessmentSessionTarget.position)
            )
        ).all()
    )
    return PlannedAssessmentResponse(
        id=assessment.id,
        child_id=assessment.child_id,
        source=assessment.source,
        status=assessment.status,
        sampling_method=plan.sampling_method,
        sampling_version=plan.sampling_version,
        eligible_catalog_size=plan.eligible_catalog_size,
        catalog_version=plan.catalog_version,
        started_at=assessment.started_at,
        completed_at=assessment.completed_at,
        total_items=len(rows),
        completed_items=sum(item is not None for _, _, item in rows),
        targets=[
            AssessmentTargetResponse(
                knowledge_point_id=target.knowledge_point_id,
                character=character.character,
                pinyin=character.pinyin,
                position=target.position,
                sampling_class=target.sampling_class,
                outcome=item.outcome if item else None,
                response_time_ms=item.response_time_ms if item else None,
            )
            for target, character, item in rows
        ],
    )


async def start_or_resume_assessment(
    session: AsyncSession,
    child_id: uuid.UUID,
    evaluator_user_id: uuid.UUID,
    source: str,
    *,
    now: datetime | None = None,
) -> PlannedAssessmentResponse:
    now = now or datetime.now(UTC)
    if source not in (
        AssessmentSource.DAILY_REVIEW,
        AssessmentSource.WEEKLY_CHECK,
        AssessmentSource.MONTHLY_ASSESSMENT,
    ):
        raise ValueError("Unsupported planned assessment source")
    settings = await ensure_learning_settings(session, child_id)
    if source == AssessmentSource.WEEKLY_CHECK and not settings.weekly_assessment_enabled:
        raise ValueError("Weekly assessment is disabled")
    if source == AssessmentSource.MONTHLY_ASSESSMENT and not settings.monthly_assessment_enabled:
        raise ValueError("Monthly assessment is disabled")

    active = await session.scalar(
        select(AssessmentSession)
        .where(
            AssessmentSession.child_id == child_id,
            AssessmentSession.source == source,
            AssessmentSession.status == SessionStatus.IN_PROGRESS,
        )
        .order_by(AssessmentSession.started_at.desc())
    )
    if active is not None:
        return await _session_response(session, active)

    daily_plan: DailyLearningPlan | None = None
    if source == AssessmentSource.DAILY_REVIEW:
        daily = await get_or_create_daily_plan(session, child_id, now=now)
        daily_plan = await session.get(DailyLearningPlan, daily.id)
        assert daily_plan is not None
        existing_daily = await session.scalar(
            select(AssessmentSession)
            .join(
                AssessmentSessionPlan,
                AssessmentSessionPlan.assessment_session_id == AssessmentSession.id,
            )
            .where(
                AssessmentSession.child_id == child_id,
                AssessmentSessionPlan.daily_plan_id == daily_plan.id,
                AssessmentSession.status != SessionStatus.ABANDONED,
            )
            .order_by(AssessmentSession.started_at.desc())
        )
        if existing_daily is not None:
            return await _session_response(session, existing_daily)
        target_rows = list(
            (
                await session.scalars(
                    select(DailyPlanItem)
                    .where(
                        DailyPlanItem.daily_plan_id == daily_plan.id,
                        DailyPlanItem.item_kind == DailyPlanItemKind.REVIEW,
                    )
                    .order_by(DailyPlanItem.position)
                )
            ).all()
        )
        targets = [(item.knowledge_point_id, item.selection_reason) for item in target_rows]
        sampling_method = "daily_due_priority_capacity"
    else:
        local_date = now.astimezone(ZoneInfo(settings.timezone)).date()
        prior_sessions = list(
            (
                await session.scalars(
                    select(AssessmentSession)
                    .where(
                        AssessmentSession.child_id == child_id,
                        AssessmentSession.source == source,
                        AssessmentSession.status != SessionStatus.ABANDONED,
                    )
                    .order_by(AssessmentSession.started_at.desc())
                )
            ).all()
        )
        for prior in prior_sessions:
            prior_date = _utc(prior.started_at).astimezone(ZoneInfo(settings.timezone)).date()
            same_period = (
                prior_date.isocalendar()[:2] == local_date.isocalendar()[:2]
                if source == AssessmentSource.WEEKLY_CHECK
                else (prior_date.year, prior_date.month) == (local_date.year, local_date.month)
            )
            if same_period:
                return await _session_response(session, prior)
        targets = await _sample_periodic_targets(session, child_id, source, now)
        sampling_method = (
            "weekly_recent_weak_stable"
            if source == AssessmentSource.WEEKLY_CHECK
            else "monthly_stratified_with_unseen"
        )
    if not targets:
        raise ValueError("No eligible characters are available for this session")

    assessment = AssessmentSession(
        child_id=child_id,
        evaluator_user_id=evaluator_user_id,
        status=SessionStatus.IN_PROGRESS,
        source=source,
        started_at=now,
    )
    session.add(assessment)
    await session.flush()
    catalog_version, catalog_size = await _current_catalog_frame(session)
    session.add(
        AssessmentSessionPlan(
            assessment_session_id=assessment.id,
            daily_plan_id=daily_plan.id if daily_plan else None,
            sampling_method=sampling_method,
            sampling_version=SAMPLING_VERSION,
            eligible_catalog_size=catalog_size,
            catalog_version=catalog_version,
        )
    )
    for position, (point_id, sampling_class) in enumerate(targets):
        session.add(
            AssessmentSessionTarget(
                assessment_session_id=assessment.id,
                knowledge_point_id=point_id,
                position=position,
                sampling_class=sampling_class,
            )
        )
    if daily_plan:
        daily_plan.status = DailyPlanStatus.IN_PROGRESS
    await session.commit()
    return await _session_response(session, assessment)


async def _create_literacy_estimate(
    session: AsyncSession, assessment: AssessmentSession
) -> LiteracyEstimate:
    existing = await session.scalar(
        select(LiteracyEstimate).where(LiteracyEstimate.assessment_session_id == assessment.id)
    )
    if existing is not None:
        return existing
    plan = await session.scalar(
        select(AssessmentSessionPlan).where(
            AssessmentSessionPlan.assessment_session_id == assessment.id
        )
    )
    assert plan is not None
    items = list(
        (
            await session.scalars(
                select(AssessmentItem).where(AssessmentItem.session_id == assessment.id)
            )
        ).all()
    )
    sample_size = len(items)
    known = sum(item.outcome == AssessmentOutcome.CORRECT for item in items)
    sufficient = sample_size >= LITERACY_MINIMUM_SAMPLE
    estimate: float | None = None
    lower: float | None = None
    upper: float | None = None
    if sufficient and sample_size:
        proportion = known / sample_size
        z = 1.96
        denominator = 1 + z * z / sample_size
        center = (proportion + z * z / (2 * sample_size)) / denominator
        margin = (
            z
            * math.sqrt(
                proportion * (1 - proportion) / sample_size
                + z * z / (4 * sample_size * sample_size)
            )
            / denominator
        )
        estimate = float(
            min(plan.eligible_catalog_size, round(proportion * plan.eligible_catalog_size))
        )
        lower = float(max(0, round((center - margin) * plan.eligible_catalog_size)))
        upper = float(
            min(plan.eligible_catalog_size, round((center + margin) * plan.eligible_catalog_size))
        )
    estimate_row = LiteracyEstimate(
        child_id=assessment.child_id,
        assessment_session_id=assessment.id,
        catalog_size=plan.eligible_catalog_size,
        catalog_version=plan.catalog_version,
        sample_size=sample_size,
        known_count=known,
        unknown_count=sample_size - known,
        sampling_method=plan.sampling_method,
        sampling_version=plan.sampling_version,
        estimate=estimate,
        lower_bound=lower,
        upper_bound=upper,
        is_sufficient=sufficient,
        estimation_version=LITERACY_ESTIMATION_VERSION,
    )
    session.add(estimate_row)
    await session.flush()
    return estimate_row


async def submit_planned_assessment(
    session: AsyncSession,
    child_id: uuid.UUID,
    assessment_session_id: uuid.UUID,
    evaluator_user_id: uuid.UUID,
    payload: AssessmentBatchSubmit,
    *,
    now: datetime | None = None,
) -> PlannedAssessmentResponse:
    now = now or datetime.now(UTC)
    assessment = await session.scalar(
        select(AssessmentSession).where(
            AssessmentSession.id == assessment_session_id,
            AssessmentSession.child_id == child_id,
        )
    )
    if assessment is None:
        raise LookupError("Assessment session not found")
    if assessment.status != SessionStatus.IN_PROGRESS:
        raise RuntimeError("Assessment session is no longer in progress")
    targets = set(
        (
            await session.scalars(
                select(AssessmentSessionTarget.knowledge_point_id).where(
                    AssessmentSessionTarget.assessment_session_id == assessment.id
                )
            )
        ).all()
    )
    submitted_ids = {item.knowledge_point_id for item in payload.items}
    if not submitted_ids.issubset(targets):
        raise ValueError("Submission contains a character outside the persisted session sample")
    existing_ids = set(
        (
            await session.scalars(
                select(AssessmentItem.knowledge_point_id).where(
                    AssessmentItem.session_id == assessment.id,
                    AssessmentItem.knowledge_point_id.in_(submitted_ids),
                )
            )
        ).all()
    )
    if existing_ids:
        raise RuntimeError("One or more submitted characters already have preserved evidence")
    for item in payload.items:
        session.add(
            AssessmentItem(
                session_id=assessment.id,
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
    for point_id in submitted_ids:
        await recompute_child_knowledge_state(session, child_id, point_id)
        await recompute_review_schedule(session, child_id, point_id)

    completed_count = int(
        await session.scalar(
            select(func.count())
            .select_from(AssessmentItem)
            .where(AssessmentItem.session_id == assessment.id)
        )
        or 0
    )
    if payload.complete and completed_count != len(targets):
        raise ValueError("Every persisted target must have evidence before completion")
    should_complete = completed_count == len(targets)
    session_plan = await session.scalar(
        select(AssessmentSessionPlan).where(
            AssessmentSessionPlan.assessment_session_id == assessment.id
        )
    )
    if session_plan and session_plan.daily_plan_id:
        daily_plan = await session.get(DailyLearningPlan, session_plan.daily_plan_id)
        assert daily_plan is not None
        daily_items = list(
            (
                await session.scalars(
                    select(DailyPlanItem).where(
                        DailyPlanItem.daily_plan_id == daily_plan.id,
                        DailyPlanItem.item_kind == DailyPlanItemKind.REVIEW,
                        DailyPlanItem.knowledge_point_id.in_(submitted_ids),
                        DailyPlanItem.status == PlanItemStatus.PENDING,
                    )
                )
            ).all()
        )
        for item in daily_items:
            item.status = PlanItemStatus.COMPLETED
            item.completed_at = now
        daily_plan.review_completed_count += len(daily_items)
        _refresh_plan_status(daily_plan)
    if should_complete:
        assessment.status = SessionStatus.COMPLETED
        assessment.completed_at = now
        if assessment.source == AssessmentSource.MONTHLY_ASSESSMENT:
            await _create_literacy_estimate(session, assessment)
    await session.commit()
    return await _session_response(session, assessment)


async def assessment_history(
    session: AsyncSession, child_id: uuid.UUID
) -> list[AssessmentHistoryEntry]:
    sessions = list(
        (
            await session.scalars(
                select(AssessmentSession)
                .where(
                    AssessmentSession.child_id == child_id,
                    AssessmentSession.source.in_(
                        [
                            AssessmentSource.DAILY_REVIEW,
                            AssessmentSource.WEEKLY_CHECK,
                            AssessmentSource.MONTHLY_ASSESSMENT,
                        ]
                    ),
                )
                .order_by(AssessmentSession.started_at.desc())
                .limit(100)
            )
        ).all()
    )
    output: list[AssessmentHistoryEntry] = []
    for assessment in sessions:
        counts = dict(
            (
                await session.execute(
                    select(AssessmentItem.outcome, func.count())
                    .where(AssessmentItem.session_id == assessment.id)
                    .group_by(AssessmentItem.outcome)
                )
            ).all()
        )
        output.append(
            AssessmentHistoryEntry(
                id=assessment.id,
                source=assessment.source,
                status=assessment.status,
                started_at=assessment.started_at,
                completed_at=assessment.completed_at,
                item_count=sum(counts.values()),
                correct=counts.get(AssessmentOutcome.CORRECT, 0),
                hinted_correct=counts.get(AssessmentOutcome.HINTED_CORRECT, 0),
                uncertain=counts.get(AssessmentOutcome.UNCERTAIN, 0),
                incorrect=counts.get(AssessmentOutcome.INCORRECT, 0),
            )
        )
    return output


async def get_planned_assessment(
    session: AsyncSession, child_id: uuid.UUID, assessment_session_id: uuid.UUID
) -> PlannedAssessmentResponse | None:
    assessment = await session.scalar(
        select(AssessmentSession).where(
            AssessmentSession.id == assessment_session_id,
            AssessmentSession.child_id == child_id,
        )
    )
    if assessment is None:
        return None
    plan = await session.scalar(
        select(AssessmentSessionPlan.id).where(
            AssessmentSessionPlan.assessment_session_id == assessment.id
        )
    )
    if plan is None:
        return None
    return await _session_response(session, assessment)


def literacy_response(
    row: LiteracyEstimate | None, catalog_version: str, catalog_size: int
) -> LiteracyEstimateResponse:
    return LiteracyEstimateResponse(
        id=row.id if row else None,
        assessment_session_id=row.assessment_session_id if row else None,
        catalog_size=row.catalog_size if row else catalog_size,
        catalog_version=row.catalog_version if row else catalog_version,
        sample_size=row.sample_size if row else 0,
        known_count=row.known_count if row else 0,
        unknown_count=row.unknown_count if row else 0,
        sampling_method=row.sampling_method if row else None,
        sampling_version=row.sampling_version if row else None,
        estimate=row.estimate if row else None,
        lower_bound=row.lower_bound if row else None,
        upper_bound=row.upper_bound if row else None,
        is_sufficient=row.is_sufficient if row else False,
        estimation_version=row.estimation_version if row else LITERACY_ESTIMATION_VERSION,
        limitation=LITERACY_LIMITATION,
        created_at=row.created_at if row else None,
    )


async def latest_literacy_estimate(
    session: AsyncSession, child_id: uuid.UUID
) -> LiteracyEstimateResponse:
    row = await session.scalar(
        select(LiteracyEstimate)
        .where(LiteracyEstimate.child_id == child_id)
        .order_by(LiteracyEstimate.created_at.desc())
    )
    catalog_version, catalog_size = await _current_catalog_frame(session)
    return literacy_response(row, catalog_version, catalog_size)


async def literacy_history(
    session: AsyncSession, child_id: uuid.UUID
) -> list[LiteracyEstimateResponse]:
    rows = list(
        (
            await session.scalars(
                select(LiteracyEstimate)
                .where(LiteracyEstimate.child_id == child_id)
                .order_by(LiteracyEstimate.created_at.desc())
            )
        ).all()
    )
    catalog_version, catalog_size = await _current_catalog_frame(session)
    return [literacy_response(row, catalog_version, catalog_size) for row in rows]
