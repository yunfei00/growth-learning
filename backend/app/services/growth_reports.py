"""Evidence-backed immutable Growth Report V1 snapshots."""

import json
import uuid
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.ai.base import AICompletionRequest, AIMessage, AIProvider
from app.models import (
    AssessmentKind,
    AssessmentSession,
    ChildKnowledgeState,
    ChildReviewSchedule,
    ExperimentEvidence,
    ExperimentSession,
    GrowthEvent,
    GrowthReport,
    GrowthReportVersion,
    KnowledgePoint,
    KnowledgeType,
    LearningRecord,
    LiteracyEstimate,
    MasteryLevel,
    ReadingAnswer,
    ReadingMode,
    ReadingSession,
    ReadingStatus,
    StoryVersion,
)
from app.schemas.growth import (
    GrowthReportGenerate,
    GrowthReportSummary,
    GrowthReportVersionResponse,
)

REPORT_POLICY_VERSION = "growth-report-v1"
AI_PROMPT_VERSION = "growth-report-narrative-v1"


def _bounds(start: date, end: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(start, time.min, tzinfo=UTC),
        datetime.combine(end + timedelta(days=1), time.min, tzinfo=UTC),
    )


async def build_report_snapshot(
    session: AsyncSession, child_id: uuid.UUID, period_start: date, period_end: date
) -> tuple[dict[str, object], dict[str, object], list[str]]:
    start_at, end_exclusive = _bounds(period_start, period_end)
    cutoff = datetime.now(UTC)

    states = list(
        (
            await session.scalars(
                select(ChildKnowledgeState).where(
                    ChildKnowledgeState.child_id == child_id,
                    ChildKnowledgeState.knowledge_point_id.in_(
                        select(KnowledgePoint.id).where(
                            KnowledgePoint.type == KnowledgeType.CHINESE_CHARACTER
                        )
                    ),
                )
            )
        ).all()
    )
    state_counts = {
        level.value: sum(1 for state in states if state.mastery_level == level)
        for level in MasteryLevel
    }
    newly_exposed = int(
        await session.scalar(
            select(func.count(func.distinct(LearningRecord.knowledge_point_id))).where(
                LearningRecord.child_id == child_id,
                LearningRecord.learned_at >= start_at,
                LearningRecord.learned_at < end_exclusive,
                LearningRecord.knowledge_point_id.in_(
                    select(KnowledgePoint.id).where(
                        KnowledgePoint.type == KnowledgeType.CHINESE_CHARACTER
                    )
                ),
            )
        )
        or 0
    )
    review_backlog = int(
        await session.scalar(
            select(func.count())
            .select_from(ChildReviewSchedule)
            .where(
                ChildReviewSchedule.child_id == child_id,
                ChildReviewSchedule.next_review_at <= cutoff,
                ChildReviewSchedule.knowledge_point_id.in_(
                    select(KnowledgePoint.id).where(
                        KnowledgePoint.type == KnowledgeType.CHINESE_CHARACTER
                    )
                ),
            )
        )
        or 0
    )
    assessment_rows = list(
        (
            await session.scalars(
                select(AssessmentSession).where(
                    AssessmentSession.child_id == child_id,
                    AssessmentSession.status == "completed",
                    AssessmentSession.assessment_kind == AssessmentKind.RECOGNITION,
                    AssessmentSession.completed_at >= start_at,
                    AssessmentSession.completed_at < end_exclusive,
                )
            )
        ).all()
    )
    latest_literacy = await session.scalar(
        select(LiteracyEstimate)
        .where(LiteracyEstimate.child_id == child_id, LiteracyEstimate.created_at < end_exclusive)
        .order_by(LiteracyEstimate.created_at.desc())
        .limit(1)
    )

    reading_rows = list(
        (
            await session.execute(
                select(ReadingSession, StoryVersion)
                .join(StoryVersion, StoryVersion.id == ReadingSession.story_version_id)
                .where(
                    ReadingSession.child_id == child_id,
                    ReadingSession.status == ReadingStatus.COMPLETED,
                    ReadingSession.completed_at >= start_at,
                    ReadingSession.completed_at < end_exclusive,
                )
            )
        ).all()
    )
    reading_session_ids = [item.id for item, _ in reading_rows]
    answers = (
        list(
            (
                await session.scalars(
                    select(ReadingAnswer).where(
                        ReadingAnswer.reading_session_id.in_(reading_session_ids)
                    )
                )
            ).all()
        )
        if reading_session_ids
        else []
    )
    comprehension_responses = len(answers)
    comprehension_supported = comprehension_responses >= 5

    science_rows = list(
        (
            await session.scalars(
                select(ExperimentSession).where(
                    ExperimentSession.child_id == child_id,
                    ExperimentSession.status == "completed",
                    ExperimentSession.completed_at >= start_at,
                    ExperimentSession.completed_at < end_exclusive,
                )
            )
        ).all()
    )
    science_ids = [item.id for item in science_rows]
    evidence = (
        list(
            (
                await session.scalars(
                    select(ExperimentEvidence).where(
                        ExperimentEvidence.experiment_session_id.in_(science_ids)
                    )
                )
            ).all()
        )
        if science_ids
        else []
    )
    tags = sorted({tag for item in evidence for tag in item.capability_tags})
    original_words = [
        item.original_text
        for item in evidence
        if item.evidence_type in {"child_original_words", "question_asked"}
    ]

    period_events = list(
        (
            await session.scalars(
                select(GrowthEvent)
                .where(
                    GrowthEvent.child_id == child_id,
                    GrowthEvent.archived_at.is_(None),
                    GrowthEvent.occurred_at >= start_at,
                    GrowthEvent.occurred_at < end_exclusive,
                )
                .order_by(GrowthEvent.occurred_at.desc())
            )
        ).all()
    )
    manual_events = [item for item in period_events if item.source_type != "system"]

    literacy_payload: dict[str, object] = {
        "available": bool(latest_literacy and latest_literacy.is_sufficient),
        "estimate": round(latest_literacy.estimate)
        if latest_literacy and latest_literacy.estimate is not None
        else None,
        "catalog_size": latest_literacy.catalog_size if latest_literacy else None,
        "disclaimer": "该结果仅代表当前系统字库范围，不代表孩子全部汉字识字量。",
    }
    metrics: dict[str, object] = {
        "period": {"start": period_start.isoformat(), "end": period_end.isoformat()},
        "learning": {
            "newly_exposed": newly_exposed,
            "current_introduced_or_higher": len(states) - state_counts[MasteryLevel.UNLEARNED],
            "stable": state_counts[MasteryLevel.STABLE],
            "recognizing": state_counts[MasteryLevel.RECOGNIZING],
            "priority": sum(1 for state in states if state.is_priority),
            "review_backlog": review_backlog,
            "assessment_count": len(assessment_rows),
            "monthly_assessment_count": sum(
                1 for item in assessment_rows if item.source == "monthly_assessment"
            ),
            "literacy_estimate": literacy_payload,
        },
        "reading": {
            "stories_read": len(reading_rows),
            "independent": sum(
                1 for item, _ in reading_rows if item.reading_mode == ReadingMode.INDEPENDENT
            ),
            "with_help": sum(
                1 for item, _ in reading_rows if item.reading_mode == ReadingMode.WITH_HELP
            ),
            "themes": sorted({version.theme for _, version in reading_rows}),
            "comprehension_samples": comprehension_responses,
            "comprehension_outcomes": {
                outcome: sum(1 for answer in answers if answer.outcome == outcome)
                for outcome in ("correct", "with_help", "partial", "incorrect")
            },
        },
        "science": {
            "experiments_completed": len(science_rows),
            "experiment_titles": [
                str(item.experiment_snapshot.get("title", "科学实验")) for item in science_rows
            ],
            "original_words": original_words,
            "capability_evidence_tags": tags,
            "numeric_score": None,
        },
        "family_records": {
            "count": len(manual_events),
            "selected_original_text": [item.body for item in manual_events[:10]],
        },
    }
    sections: dict[str, object] = {
        "learning": (
            "本月尚无正式识字检测。"
            if not any(item.source == "monthly_assessment" for item in assessment_rows)
            else "本周期已有正式识字检测，结果以原始评估记录为准。"
        ),
        "reading": (
            "阅读理解样本较少，暂不形成趋势判断。"
            if not comprehension_supported
            else "阅读理解样本已达到 V1 趋势展示门槛，请结合具体题目和陪伴方式理解。"
        ),
        "science": (
            "本周期尚无完成的科学实验。"
            if not science_rows
            else (
                f"本周期完成 {len(science_rows)} 次科学实验；能力标签只表示观察到的证据，不是分数。"
            )
        ),
        "family": "本周期尚无家庭成长记录。"
        if not manual_events
        else f"家人记录了 {len(manual_events)} 个成长瞬间。",
        "next_suggestion": (
            "最近复习积压较多，未来几天建议减少新字并优先完成复习。"
            if review_backlog >= 10
            else "继续保持少量新字、及时复习，并保留真实阅读或探索记录。"
        ),
    }
    return metrics, sections, [str(item.id) for item in period_events[:20]]


async def _optional_ai_narrative(
    provider: AIProvider | None,
    *,
    enabled: bool,
    metrics: dict[str, object],
    sections: dict[str, object],
) -> tuple[str | None, str | None, str | None]:
    if not enabled or provider is None:
        return None, None, None
    try:
        response = await provider.complete(
            AICompletionRequest(
                messages=[
                    AIMessage(
                        role="system",
                        content=(
                            "将结构化成长报告改写为一段克制、温暖的家长摘要。只使用给定事实，"
                            '不诊断、不评分、不添加永久能力标签。返回 JSON：{"narrative": "..."}。'
                        ),
                    ),
                    AIMessage(
                        role="user",
                        content=json.dumps(
                            {"metrics": metrics, "sections": sections}, ensure_ascii=False
                        ),
                    ),
                ],
                json_response=True,
                max_tokens=500,
            )
        )
        payload = json.loads(response.text)
        narrative = payload.get("narrative")
        if not isinstance(narrative, str) or not narrative.strip():
            return None, None, None
    except Exception:
        # The deterministic report is authoritative; an optional provider outage must not block it.
        return None, None, None
    return narrative.strip(), response.provider, response.model


async def generate_growth_report(
    session: AsyncSession,
    *,
    child_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    payload: GrowthReportGenerate,
    provider: AIProvider | None = None,
) -> GrowthReportVersion:
    report = await session.scalar(
        select(GrowthReport).where(
            GrowthReport.child_id == child_id,
            GrowthReport.period_type == payload.period_type,
            GrowthReport.period_start == payload.period_start,
            GrowthReport.period_end == payload.period_end,
        )
    )
    if report is None:
        report = GrowthReport(
            child_id=child_id,
            period_type=payload.period_type,
            period_start=payload.period_start,
            period_end=payload.period_end,
            created_by_user_id=actor_user_id,
        )
        session.add(report)
        await session.flush()
    latest = int(
        await session.scalar(
            select(func.max(GrowthReportVersion.version_number)).where(
                GrowthReportVersion.report_id == report.id
            )
        )
        or 0
    )
    metrics, sections, event_ids = await build_report_snapshot(
        session, child_id, payload.period_start, payload.period_end
    )
    narrative, ai_provider, ai_model = await _optional_ai_narrative(
        provider,
        enabled=payload.include_ai_narrative,
        metrics=metrics,
        sections=sections,
    )
    now = datetime.now(UTC)
    version = GrowthReportVersion(
        report_id=report.id,
        version_number=latest + 1,
        source_cutoff_at=now,
        policy_version=REPORT_POLICY_VERSION,
        metrics_snapshot=metrics,
        deterministic_sections=sections,
        selected_event_ids=event_ids,
        ai_narrative=narrative,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_prompt_version=AI_PROMPT_VERSION if narrative else None,
        ai_generated_at=now if narrative else None,
    )
    session.add(version)
    await session.commit()
    await session.refresh(version)
    return version


async def report_version_response(
    session: AsyncSession, version: GrowthReportVersion
) -> GrowthReportVersionResponse:
    report = await session.get(GrowthReport, version.report_id)
    if report is None:
        raise LookupError("Growth report not found")
    return GrowthReportVersionResponse(
        id=version.id,
        report_id=report.id,
        version_number=version.version_number,
        period_type=report.period_type,
        period_start=report.period_start,
        period_end=report.period_end,
        generated_at=version.generated_at,
        source_cutoff_at=version.source_cutoff_at,
        policy_version=version.policy_version,
        metrics=version.metrics_snapshot,
        sections=version.deterministic_sections,
        selected_event_ids=[uuid.UUID(item) for item in version.selected_event_ids],
        ai_narrative=version.ai_narrative,
        ai_provider=version.ai_provider,
        ai_model=version.ai_model,
        ai_prompt_version=version.ai_prompt_version,
    )


async def list_growth_reports(
    session: AsyncSession, child_id: uuid.UUID
) -> list[GrowthReportSummary]:
    reports = list(
        (
            await session.scalars(
                select(GrowthReport)
                .where(GrowthReport.child_id == child_id)
                .order_by(GrowthReport.period_end.desc())
            )
        ).all()
    )
    result: list[GrowthReportSummary] = []
    for report in reports:
        version = await session.scalar(
            select(GrowthReportVersion)
            .where(GrowthReportVersion.report_id == report.id)
            .order_by(GrowthReportVersion.version_number.desc())
            .limit(1)
        )
        if version:
            result.append(
                GrowthReportSummary(
                    id=report.id,
                    period_type=report.period_type,
                    period_start=report.period_start,
                    period_end=report.period_end,
                    latest_version=version.version_number,
                    generated_at=version.generated_at,
                )
            )
    return result
