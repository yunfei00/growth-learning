"""Deterministic, idempotent projection of meaningful child growth events."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssessmentKind,
    AssessmentSession,
    ChildKnowledgeState,
    ExperimentEvidence,
    ExperimentEvidenceType,
    ExperimentSession,
    ExperimentSessionStatus,
    FamilyRole,
    GrowthEvent,
    GrowthEventCategory,
    GrowthEventType,
    GrowthSourceType,
    KnowledgePoint,
    KnowledgeType,
    LearningRecord,
    MasteryLevel,
    ReadingMode,
    ReadingSession,
    ReadingStatus,
    StoryVersion,
    User,
)
from app.schemas.growth import (
    GrowthEventCreate,
    GrowthEventPage,
    GrowthEventResponse,
    GrowthMediaResponse,
)

POLICY_VERSION = "growth-event-v1"


@dataclass(frozen=True)
class ProjectionResult:
    created: int
    existing: int


def _source_url(event: GrowthEvent) -> str | None:
    if event.source_entity_id is None:
        return None
    if event.source_entity_type == "reading_session":
        version_id = event.evidence_snapshot.get("story_version_id")
        return f"/read/{version_id}" if version_id else None
    if event.source_entity_type == "experiment_session":
        return f"/science/session/{event.source_entity_id}"
    if event.source_entity_type == "assessment_session":
        return "/learn/characters"
    return None


async def event_response(session: AsyncSession, event: GrowthEvent) -> GrowthEventResponse:
    from app.models import GrowthMediaAsset

    actor_name = None
    if event.actor_user_id:
        actor_name = await session.scalar(
            select(User.display_name).where(User.id == event.actor_user_id)
        )
    media = list(
        (
            await session.scalars(
                select(GrowthMediaAsset)
                .where(GrowthMediaAsset.growth_event_id == event.id)
                .order_by(GrowthMediaAsset.created_at)
            )
        ).all()
    )
    return GrowthEventResponse(
        id=event.id,
        child_id=event.child_id,
        event_type=event.event_type,
        category=event.category,
        occurred_at=event.occurred_at,
        title=event.title,
        body=event.body,
        source_type=event.source_type,
        actor_user_id=event.actor_user_id,
        actor_display_name=actor_name,
        source_entity_type=event.source_entity_type,
        source_entity_id=event.source_entity_id,
        source_url=_source_url(event),
        evidence_snapshot=event.evidence_snapshot,
        policy_version=event.policy_version,
        archived_at=event.archived_at,
        media=[
            GrowthMediaResponse(
                id=item.id,
                media_kind=item.media_kind,
                mime_type=item.mime_type,
                size_bytes=item.size_bytes,
                original_filename=item.original_filename,
                created_at=item.created_at,
                content_url=(
                    f"/api/v1/children/{event.child_id}/growth/events/{event.id}/media/{item.id}/content"
                ),
            )
            for item in media
        ],
    )


async def _emit(
    session: AsyncSession,
    *,
    child_id: uuid.UUID,
    key: str,
    event_type: str,
    category: str,
    occurred_at: datetime,
    title: str,
    body: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    snapshot: dict[str, object] | None = None,
) -> bool:
    exists = await session.scalar(
        select(GrowthEvent.id).where(
            GrowthEvent.child_id == child_id, GrowthEvent.idempotency_key == key
        )
    )
    if exists:
        return False
    session.add(
        GrowthEvent(
            child_id=child_id,
            event_type=event_type,
            category=category,
            occurred_at=occurred_at,
            title=title,
            body=body,
            source_type=GrowthSourceType.SYSTEM,
            source_entity_type=entity_type,
            source_entity_id=entity_id,
            idempotency_key=key,
            evidence_snapshot=snapshot or {},
            policy_version=POLICY_VERSION,
        )
    )
    return True


async def project_growth_events(session: AsyncSession, child_id: uuid.UUID) -> ProjectionResult:
    """Append missing V1 projections; manual records are never deleted or rewritten."""
    created = 0
    existing = 0

    introduced_count = int(
        await session.scalar(
            select(func.count(func.distinct(LearningRecord.knowledge_point_id))).where(
                LearningRecord.child_id == child_id,
                LearningRecord.knowledge_point_id.in_(
                    select(KnowledgePoint.id).where(
                        KnowledgePoint.type == KnowledgeType.CHINESE_CHARACTER
                    )
                ),
            )
        )
        or 0
    )
    stable_count = int(
        await session.scalar(
            select(func.count())
            .select_from(ChildKnowledgeState)
            .where(
                ChildKnowledgeState.child_id == child_id,
                ChildKnowledgeState.mastery_level == MasteryLevel.STABLE,
                ChildKnowledgeState.knowledge_point_id.in_(
                    select(KnowledgePoint.id).where(
                        KnowledgePoint.type == KnowledgeType.CHINESE_CHARACTER
                    )
                ),
            )
        )
        or 0
    )
    for threshold, count, kind, title in (
        (100, introduced_count, "introduced", "第一次接触 100 个汉字"),
        (100, stable_count, "stable", "稳定掌握达到 100 个汉字"),
    ):
        if count >= threshold:
            occurred = await session.scalar(
                select(func.max(LearningRecord.learned_at)).where(
                    LearningRecord.child_id == child_id,
                    LearningRecord.knowledge_point_id.in_(
                        select(KnowledgePoint.id).where(
                            KnowledgePoint.type == KnowledgeType.CHINESE_CHARACTER
                        )
                    ),
                )
            ) or datetime.now(UTC)
            made = await _emit(
                session,
                child_id=child_id,
                key=f"learning:{kind}:{threshold}:{POLICY_VERSION}",
                event_type=GrowthEventType.LEARNING_MILESTONE,
                category=GrowthEventCategory.LEARNING,
                occurred_at=occurred,
                title=title,
                body=f"当前系统证据支持该里程碑，共 {count} 个；统计范围仅限当前字库。",
                snapshot={"threshold": threshold, "observed_count": count, "bounded_catalog": True},
            )
            created += int(made)
            existing += int(not made)

    assessments = list(
        (
            await session.scalars(
                select(AssessmentSession).where(
                    AssessmentSession.child_id == child_id,
                    AssessmentSession.status == "completed",
                    AssessmentSession.assessment_kind == AssessmentKind.RECOGNITION,
                )
            )
        ).all()
    )
    for item in assessments:
        if item.source not in {"weekly_check", "monthly_assessment"}:
            continue
        label = "月度识字检测" if item.source == "monthly_assessment" else "周度小挑战"
        made = await _emit(
            session,
            child_id=child_id,
            key=f"assessment:{item.id}:completed:{POLICY_VERSION}",
            event_type=GrowthEventType.ASSESSMENT_MILESTONE,
            category=GrowthEventCategory.ASSESSMENT,
            occurred_at=item.completed_at or item.started_at,
            title=f"完成{label}",
            body="检测结果保留为原始评估证据，不由成长事件改写。",
            entity_type="assessment_session",
            entity_id=item.id,
            snapshot={"assessment_source": item.source},
        )
        created += int(made)
        existing += int(not made)

    reading_rows = list(
        (
            await session.execute(
                select(ReadingSession, StoryVersion)
                .join(StoryVersion, StoryVersion.id == ReadingSession.story_version_id)
                .where(
                    ReadingSession.child_id == child_id,
                    ReadingSession.status == ReadingStatus.COMPLETED,
                )
                .order_by(ReadingSession.completed_at)
            )
        ).all()
    )
    for reading, version in reading_rows:
        independent = reading.reading_mode == ReadingMode.INDEPENDENT
        title = f"{'独立读完' if independent else '完成阅读'}《{version.title}》"
        made = await _emit(
            session,
            child_id=child_id,
            key=f"reading:{reading.id}:completed:{POLICY_VERSION}",
            event_type=GrowthEventType.READING_MILESTONE,
            category=GrowthEventCategory.READING,
            occurred_at=reading.completed_at or reading.started_at,
            title=title,
            body="这是一条真实阅读会话记录。",
            entity_type="reading_session",
            entity_id=reading.id,
            snapshot={"story_version_id": str(version.id), "reading_mode": reading.reading_mode},
        )
        created += int(made)
        existing += int(not made)
    if len(reading_rows) >= 10:
        reading, _ = reading_rows[9]
        made = await _emit(
            session,
            child_id=child_id,
            key=f"reading:count:10:{POLICY_VERSION}",
            event_type=GrowthEventType.ACHIEVEMENT,
            category=GrowthEventCategory.ACHIEVEMENT,
            occurred_at=reading.completed_at or reading.started_at,
            title="完成 10 篇故事阅读",
            body="累计完成 10 次有持久记录的阅读会话。",
            snapshot={"threshold": 10},
        )
        created += int(made)
        existing += int(not made)

    experiments = list(
        (
            await session.scalars(
                select(ExperimentSession)
                .where(
                    ExperimentSession.child_id == child_id,
                    ExperimentSession.status == ExperimentSessionStatus.COMPLETED,
                )
                .order_by(ExperimentSession.completed_at)
            )
        ).all()
    )
    for experiment in experiments:
        experiment_title = str(experiment.experiment_snapshot.get("title", "科学实验"))
        made = await _emit(
            session,
            child_id=child_id,
            key=f"science:{experiment.id}:completed:{POLICY_VERSION}",
            event_type=GrowthEventType.SCIENCE_MILESTONE,
            category=GrowthEventCategory.SCIENCE,
            occurred_at=experiment.completed_at or experiment.updated_at,
            title=f"完成科学实验《{experiment_title}》",
            body="保留预测、观察和孩子原话等原始实验证据。",
            entity_type="experiment_session",
            entity_id=experiment.id,
            snapshot={"experiment_title": experiment_title},
        )
        created += int(made)
        existing += int(not made)
    for threshold in (5, 10):
        if len(experiments) >= threshold:
            experiment = experiments[threshold - 1]
            made = await _emit(
                session,
                child_id=child_id,
                key=f"science:count:{threshold}:{POLICY_VERSION}",
                event_type=GrowthEventType.ACHIEVEMENT,
                category=GrowthEventCategory.ACHIEVEMENT,
                occurred_at=experiment.completed_at or experiment.updated_at,
                title=f"完成 {threshold} 次科学实验",
                body=f"累计完成 {threshold} 次有真实证据的家庭科学探索。",
                snapshot={"threshold": threshold},
            )
            created += int(made)
            existing += int(not made)

    evidence_rows = list(
        (
            await session.scalars(
                select(ExperimentEvidence).where(
                    ExperimentEvidence.child_id == child_id,
                    ExperimentEvidence.evidence_type.in_(
                        [
                            ExperimentEvidenceType.CHILD_ORIGINAL_WORDS,
                            ExperimentEvidenceType.QUESTION_ASKED,
                        ]
                    ),
                )
            )
        ).all()
    )
    for evidence in evidence_rows:
        is_question = evidence.evidence_type == ExperimentEvidenceType.QUESTION_ASKED
        made = await _emit(
            session,
            child_id=child_id,
            key=f"science-evidence:{evidence.id}:{POLICY_VERSION}",
            event_type=GrowthEventType.ORIGINAL_WORDS,
            category=GrowthEventCategory.ORIGINAL_WORDS,
            occurred_at=evidence.captured_at,
            title="主动提出科学问题" if is_question else "实验中的孩子原话",
            body=evidence.original_text,
            entity_type="experiment_session",
            entity_id=evidence.experiment_session_id,
            snapshot={"evidence_id": str(evidence.id), "evidence_type": evidence.evidence_type},
        )
        created += int(made)
        existing += int(not made)

    await session.commit()
    return ProjectionResult(created=created, existing=existing)


async def create_manual_growth_event(
    session: AsyncSession,
    *,
    child_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    family_role: str,
    payload: GrowthEventCreate,
) -> GrowthEvent:
    event = GrowthEvent(
        child_id=child_id,
        event_type=payload.event_type,
        category=payload.category,
        occurred_at=payload.occurred_at,
        title=payload.title or "记录成长",
        body=payload.text,
        source_type=(
            GrowthSourceType.PARENT
            if family_role == FamilyRole.ADMIN
            else GrowthSourceType.COMPANION
        ),
        actor_user_id=actor_user_id,
        evidence_snapshot={"original_text_preserved": True},
        policy_version=POLICY_VERSION,
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event


async def list_growth_events(
    session: AsyncSession,
    child_id: uuid.UUID,
    *,
    category: str | None = None,
    year: int | None = None,
    month: int | None = None,
    page: int = 1,
    page_size: int = 30,
) -> GrowthEventPage:
    conditions = [GrowthEvent.child_id == child_id, GrowthEvent.archived_at.is_(None)]
    if category:
        conditions.append(GrowthEvent.category == category)
    if year:
        conditions.append(func.extract("year", GrowthEvent.occurred_at) == year)
    if month:
        conditions.append(func.extract("month", GrowthEvent.occurred_at) == month)
    total = int(
        await session.scalar(select(func.count()).select_from(GrowthEvent).where(*conditions)) or 0
    )
    events = list(
        (
            await session.scalars(
                select(GrowthEvent)
                .where(*conditions)
                .order_by(GrowthEvent.occurred_at.desc(), GrowthEvent.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return GrowthEventPage(
        items=[await event_response(session, event) for event in events],
        page=page,
        page_size=page_size,
        total=total,
        pages=max(1, (total + page_size - 1) // page_size),
    )
