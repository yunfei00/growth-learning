"""Representative, resumable literacy diagnostics over the current character catalog.

This service intentionally keeps literacy diagnostics separate from the monthly
review-biased sample.  It uses the persisted catalog order as a sampling frame,
selects one item per equal-width stratum, and stores the selected targets before
any answers are accepted.  Only directly answered targets create assessment
and mastery evidence; untested characters are never inferred.
"""

from __future__ import annotations

import math
import random
import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssessmentItem,
    AssessmentKind,
    AssessmentOutcome,
    AssessmentSession,
    AssessmentSessionPlan,
    AssessmentSessionTarget,
    CatalogRelease,
    CharacterCatalogEntry,
    CharacterSpeechAttempt,
    ChineseCharacter,
    KnowledgePoint,
    KnowledgeStatus,
    LiteracyEstimate,
    SessionStatus,
)
from app.schemas.learning import SpeechAttemptCreate, SpeechAttemptResponse
from app.schemas.literacy_diagnostic import (
    LiteracyDiagnosticBatchSubmit,
    LiteracyDiagnosticHistoryEntry,
    LiteracyDiagnosticOverviewResponse,
    LiteracyDiagnosticResultResponse,
    LiteracyDiagnosticSessionResponse,
    LiteracyDiagnosticTargetResponse,
)
from app.services.character_speech import evaluate_character_speech, speech_attempt_response
from app.services.mastery import recompute_child_knowledge_state
from app.services.review_planning import recompute_review_schedule

LITERACY_DIAGNOSTIC_SOURCE = "literacy_diagnostic"
LITERACY_DIAGNOSTIC_SAMPLE_SIZE = 120
LITERACY_DIAGNOSTIC_SEGMENT_SIZE = 30
LITERACY_DIAGNOSTIC_SAMPLING_METHOD = "equal_catalog_strata"
LITERACY_DIAGNOSTIC_SAMPLING_VERSION = "literacy-v2"
# Existing LiteracyEstimate.estimation_version is varchar(20); keep the stored
# identifier compact while the product/API name remains Literacy Diagnostic V2.
LITERACY_DIAGNOSTIC_ESTIMATION_VERSION = "literacy-diag-v2"
LITERACY_DIAGNOSTIC_LIMITATION = (
    "该结果仅估算当前 Growth Learning 字库范围内的独立识字情况；"
    "未直接检测的汉字不会被自动判定为认识或不认识。"
)


def representative_catalog_positions(
    catalog_size: int,
    seed: int,
    sample_size: int = LITERACY_DIAGNOSTIC_SAMPLE_SIZE,
) -> list[int]:
    """Select one deterministic random position from every equal catalog stratum.

    For the production 1200-character catalog and a 120-item standard sample,
    this produces exactly one position from each contiguous 10-character block.
    The function also behaves sensibly for smaller test/development catalogs.
    """

    if catalog_size <= 0 or sample_size <= 0:
        return []
    target_size = min(catalog_size, sample_size)
    rng = random.Random(seed)
    output: list[int] = []
    for index in range(target_size):
        start = math.floor(index * catalog_size / target_size)
        end_exclusive = math.floor((index + 1) * catalog_size / target_size)
        if end_exclusive <= start:
            end_exclusive = start + 1
        output.append(rng.randrange(start, end_exclusive))
    return output


def wilson_literacy_estimate(
    known_count: int,
    sample_size: int,
    catalog_size: int,
) -> tuple[int, int, int]:
    """Return point estimate and a conservative 95% Wilson interval."""

    if sample_size <= 0 or catalog_size <= 0:
        return 0, 0, 0
    known_count = min(max(known_count, 0), sample_size)
    proportion = known_count / sample_size
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
    estimate = min(catalog_size, max(0, round(proportion * catalog_size)))
    lower = min(catalog_size, max(0, round((center - margin) * catalog_size)))
    upper = min(catalog_size, max(0, round((center + margin) * catalog_size)))
    return estimate, lower, upper


async def _current_catalog_rows(
    session: AsyncSession,
) -> tuple[CatalogRelease, list[tuple[CharacterCatalogEntry, KnowledgePoint, ChineseCharacter]]]:
    release = await session.scalar(
        select(CatalogRelease)
        .where(CatalogRelease.is_current.is_(True))
        .order_by(CatalogRelease.imported_at.desc(), CatalogRelease.id.desc())
        .limit(1)
    )
    if release is None:
        raise ValueError("No current character catalog release is available")
    rows = list(
        (
            await session.execute(
                select(CharacterCatalogEntry, KnowledgePoint, ChineseCharacter)
                .join(
                    KnowledgePoint,
                    KnowledgePoint.id == CharacterCatalogEntry.knowledge_point_id,
                )
                .join(
                    ChineseCharacter,
                    ChineseCharacter.knowledge_point_id == KnowledgePoint.id,
                )
                .where(
                    CharacterCatalogEntry.catalog_release_id == release.id,
                    KnowledgePoint.status == KnowledgeStatus.ACTIVE,
                    ChineseCharacter.is_enabled.is_(True),
                )
                .order_by(CharacterCatalogEntry.order_index)
            )
        ).all()
    )
    if not rows:
        raise ValueError("The current character catalog has no enabled characters")
    return release, rows


async def _assessment(
    session: AsyncSession,
    child_id: uuid.UUID,
    assessment_session_id: uuid.UUID,
) -> AssessmentSession:
    assessment = await session.scalar(
        select(AssessmentSession).where(
            AssessmentSession.id == assessment_session_id,
            AssessmentSession.child_id == child_id,
            AssessmentSession.source == LITERACY_DIAGNOSTIC_SOURCE,
            AssessmentSession.assessment_kind == AssessmentKind.RECOGNITION,
        )
    )
    if assessment is None:
        raise LookupError("Literacy diagnostic session not found")
    return assessment


async def _result_for_assessment(
    session: AsyncSession,
    assessment: AssessmentSession,
) -> LiteracyDiagnosticResultResponse | None:
    estimate = await session.scalar(
        select(LiteracyEstimate).where(
            LiteracyEstimate.assessment_session_id == assessment.id,
            LiteracyEstimate.estimation_version == LITERACY_DIAGNOSTIC_ESTIMATION_VERSION,
        )
    )
    if estimate is None:
        return None
    counts = dict(
        (
            await session.execute(
                select(AssessmentItem.outcome, func.count())
                .where(AssessmentItem.session_id == assessment.id)
                .group_by(AssessmentItem.outcome)
            )
        ).all()
    )
    directly_known = int(counts.get(AssessmentOutcome.CORRECT, 0))
    uncertain = int(counts.get(AssessmentOutcome.UNCERTAIN, 0))
    unknown = int(counts.get(AssessmentOutcome.INCORRECT, 0))
    return LiteracyDiagnosticResultResponse(
        assessment_session_id=assessment.id,
        catalog_size=estimate.catalog_size,
        catalog_version=estimate.catalog_version,
        sample_size=estimate.sample_size,
        estimated_known=int(round(estimate.estimate or 0)),
        lower_bound=int(round(estimate.lower_bound or 0)),
        upper_bound=int(round(estimate.upper_bound or 0)),
        directly_known=directly_known,
        uncertain=uncertain,
        unknown=unknown,
        untested=max(0, estimate.catalog_size - estimate.sample_size),
        estimation_version=estimate.estimation_version,
        limitation=LITERACY_DIAGNOSTIC_LIMITATION,
        created_at=estimate.created_at,
    )


async def _create_result(
    session: AsyncSession,
    assessment: AssessmentSession,
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
    if plan is None:
        raise ValueError("Literacy diagnostic session has no persisted sampling plan")
    counts = dict(
        (
            await session.execute(
                select(AssessmentItem.outcome, func.count())
                .where(AssessmentItem.session_id == assessment.id)
                .group_by(AssessmentItem.outcome)
            )
        ).all()
    )
    sample_size = int(sum(counts.values()))
    known_count = int(counts.get(AssessmentOutcome.CORRECT, 0))
    estimate, lower, upper = wilson_literacy_estimate(
        known_count, sample_size, plan.eligible_catalog_size
    )
    row = LiteracyEstimate(
        child_id=assessment.child_id,
        assessment_session_id=assessment.id,
        catalog_size=plan.eligible_catalog_size,
        catalog_version=plan.catalog_version,
        sample_size=sample_size,
        known_count=known_count,
        # Legacy field means "not independently correct".  The dedicated API
        # separately exposes uncertain and incorrect counts.
        unknown_count=sample_size - known_count,
        sampling_method=plan.sampling_method,
        sampling_version=plan.sampling_version,
        estimate=float(estimate),
        lower_bound=float(lower),
        upper_bound=float(upper),
        is_sufficient=sample_size > 0,
        estimation_version=LITERACY_DIAGNOSTIC_ESTIMATION_VERSION,
    )
    session.add(row)
    await session.flush()
    return row


async def literacy_diagnostic_session_response(
    session: AsyncSession,
    assessment: AssessmentSession,
) -> LiteracyDiagnosticSessionResponse:
    plan = await session.scalar(
        select(AssessmentSessionPlan).where(
            AssessmentSessionPlan.assessment_session_id == assessment.id
        )
    )
    if plan is None:
        raise ValueError("Literacy diagnostic session has no persisted sampling plan")
    rows = list(
        (
            await session.execute(
                select(AssessmentSessionTarget, ChineseCharacter, AssessmentItem)
                .join(
                    KnowledgePoint,
                    KnowledgePoint.id == AssessmentSessionTarget.knowledge_point_id,
                )
                .join(
                    ChineseCharacter,
                    ChineseCharacter.knowledge_point_id == KnowledgePoint.id,
                )
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
    attempts = list(
        (
            await session.scalars(
                select(CharacterSpeechAttempt)
                .where(CharacterSpeechAttempt.assessment_session_id == assessment.id)
                .order_by(
                    CharacterSpeechAttempt.knowledge_point_id,
                    CharacterSpeechAttempt.attempt_index,
                )
            )
        ).all()
    )
    attempts_by_point: dict[uuid.UUID, list[CharacterSpeechAttempt]] = {}
    for attempt in attempts:
        attempts_by_point.setdefault(attempt.knowledge_point_id, []).append(attempt)
    completed = sum(item is not None for _, _, item in rows)
    total = len(rows)
    total_segments = max(1, math.ceil(total / LITERACY_DIAGNOSTIC_SEGMENT_SIZE))
    current_segment = min(
        total_segments,
        max(1, completed // LITERACY_DIAGNOSTIC_SEGMENT_SIZE + 1),
    )
    segment_break_due = (
        completed > 0
        and completed < total
        and completed % LITERACY_DIAGNOSTIC_SEGMENT_SIZE == 0
    )
    return LiteracyDiagnosticSessionResponse(
        id=assessment.id,
        child_id=assessment.child_id,
        status=assessment.status,
        sampling_method=plan.sampling_method,
        sampling_version=plan.sampling_version,
        eligible_catalog_size=plan.eligible_catalog_size,
        catalog_version=plan.catalog_version,
        segment_size=LITERACY_DIAGNOSTIC_SEGMENT_SIZE,
        total_segments=total_segments,
        current_segment=current_segment,
        segment_break_due=segment_break_due,
        started_at=assessment.started_at,
        completed_at=assessment.completed_at,
        total_items=total,
        completed_items=completed,
        targets=[
            LiteracyDiagnosticTargetResponse(
                knowledge_point_id=target.knowledge_point_id,
                character=character.character,
                pinyin=character.pinyin,
                position=target.position,
                sampling_class=target.sampling_class,
                outcome=item.outcome if item else None,
                assessment_item_id=item.id if item else None,
                response_time_ms=item.response_time_ms if item else None,
                evaluation_method=(
                    (item.evidence_metadata or {}).get("evaluation_method", "parent_manual")
                    if item
                    else None
                ),
                speech_attempts=[
                    speech_attempt_response(attempt)
                    for attempt in attempts_by_point.get(target.knowledge_point_id, [])
                ],
            )
            for target, character, item in rows
        ],
        result=await _result_for_assessment(session, assessment),
    )


async def start_or_resume_literacy_diagnostic(
    session: AsyncSession,
    child_id: uuid.UUID,
    evaluator_user_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> LiteracyDiagnosticSessionResponse:
    now = now or datetime.now(UTC)
    active = await session.scalar(
        select(AssessmentSession)
        .where(
            AssessmentSession.child_id == child_id,
            AssessmentSession.source == LITERACY_DIAGNOSTIC_SOURCE,
            AssessmentSession.status == SessionStatus.IN_PROGRESS,
        )
        .order_by(AssessmentSession.started_at.desc())
        .limit(1)
    )
    if active is not None:
        return await literacy_diagnostic_session_response(session, active)

    release, catalog_rows = await _current_catalog_rows(session)
    assessment = AssessmentSession(
        child_id=child_id,
        evaluator_user_id=evaluator_user_id,
        status=SessionStatus.IN_PROGRESS,
        source=LITERACY_DIAGNOSTIC_SOURCE,
        assessment_kind=AssessmentKind.RECOGNITION,
        started_at=now,
    )
    session.add(assessment)
    await session.flush()
    positions = representative_catalog_positions(
        len(catalog_rows), assessment.id.int, LITERACY_DIAGNOSTIC_SAMPLE_SIZE
    )
    session.add(
        AssessmentSessionPlan(
            assessment_session_id=assessment.id,
            sampling_method=LITERACY_DIAGNOSTIC_SAMPLING_METHOD,
            sampling_version=LITERACY_DIAGNOSTIC_SAMPLING_VERSION,
            eligible_catalog_size=len(catalog_rows),
            catalog_version=release.catalog_version,
        )
    )
    for sample_index, catalog_position in enumerate(positions):
        entry, point, _character = catalog_rows[catalog_position]
        session.add(
            AssessmentSessionTarget(
                assessment_session_id=assessment.id,
                knowledge_point_id=point.id,
                position=sample_index,
                sampling_class=f"stratum_{sample_index + 1:03d}",
            )
        )
        # Keep a small audit assertion in code: the selected row must still be
        # the persisted catalog entry used to build this sampling frame.
        assert entry.knowledge_point_id == point.id
    await session.commit()
    return await literacy_diagnostic_session_response(session, assessment)


async def get_literacy_diagnostic_session(
    session: AsyncSession,
    child_id: uuid.UUID,
    assessment_session_id: uuid.UUID,
) -> LiteracyDiagnosticSessionResponse:
    assessment = await _assessment(session, child_id, assessment_session_id)
    return await literacy_diagnostic_session_response(session, assessment)


async def submit_literacy_diagnostic_items(
    session: AsyncSession,
    child_id: uuid.UUID,
    assessment_session_id: uuid.UUID,
    evaluator_user_id: uuid.UUID,
    payload: LiteracyDiagnosticBatchSubmit,
    *,
    now: datetime | None = None,
) -> LiteracyDiagnosticSessionResponse:
    now = now or datetime.now(UTC)
    assessment = await _assessment(session, child_id, assessment_session_id)
    if assessment.status != SessionStatus.IN_PROGRESS:
        raise RuntimeError("Literacy diagnostic session is no longer in progress")
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
        raise ValueError("Submission contains a character outside the diagnostic sample")
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
        raise RuntimeError("One or more diagnostic characters already have preserved evidence")

    for item in payload.items:
        if item.evaluation_method == "speech_assisted" and not item.speech_attempt_ids:
            raise ValueError("Speech-assisted outcomes require speech attempt evidence")
        if item.speech_attempt_ids:
            valid_attempt_ids = set(
                (
                    await session.scalars(
                        select(CharacterSpeechAttempt.id).where(
                            CharacterSpeechAttempt.id.in_(item.speech_attempt_ids),
                            CharacterSpeechAttempt.assessment_session_id == assessment.id,
                            CharacterSpeechAttempt.knowledge_point_id == item.knowledge_point_id,
                        )
                    )
                ).all()
            )
            if valid_attempt_ids != set(item.speech_attempt_ids):
                raise ValueError("Speech evidence does not belong to this diagnostic target")
        session.add(
            AssessmentItem(
                session_id=assessment.id,
                child_id=child_id,
                knowledge_point_id=item.knowledge_point_id,
                evaluator_user_id=evaluator_user_id,
                outcome=item.outcome,
                response_time_ms=item.response_time_ms,
                hint_used=False,
                skill_dimension="independent_recognition",
                evidence_metadata={
                    "evaluation_method": item.evaluation_method,
                    "diagnostic_version": LITERACY_DIAGNOSTIC_ESTIMATION_VERSION,
                    "speech_attempt_ids": [str(value) for value in item.speech_attempt_ids],
                },
                assessed_at=now,
            )
        )
    await session.flush()

    # Assessment evidence is real evidence, but there is deliberately no
    # LearningRecord.  Recompute only the directly tested knowledge points.
    for point_id in submitted_ids:
        await recompute_child_knowledge_state(session, child_id, point_id)
        await recompute_review_schedule(session, child_id, point_id)

    completed_count = int(
        await session.scalar(
            select(func.count()).select_from(AssessmentItem).where(
                AssessmentItem.session_id == assessment.id
            )
        )
        or 0
    )
    target_count = len(targets)
    if completed_count == target_count:
        assessment.status = SessionStatus.COMPLETED
        assessment.completed_at = now
        await _create_result(session, assessment)
    await session.commit()
    return await literacy_diagnostic_session_response(session, assessment)


async def persist_literacy_diagnostic_speech_attempt(
    session: AsyncSession,
    child_id: uuid.UUID,
    assessment_session_id: uuid.UUID,
    evaluator_user_id: uuid.UUID,
    payload: SpeechAttemptCreate,
) -> SpeechAttemptResponse:
    if payload.hint_used:
        raise ValueError("Literacy diagnostics do not allow answer hints")
    assessment = await _assessment(session, child_id, assessment_session_id)
    if assessment.status != SessionStatus.IN_PROGRESS:
        raise RuntimeError("Literacy diagnostic session is no longer in progress")
    target = await session.scalar(
        select(AssessmentSessionTarget).where(
            AssessmentSessionTarget.assessment_session_id == assessment.id,
            AssessmentSessionTarget.knowledge_point_id == payload.knowledge_point_id,
        )
    )
    if target is None:
        raise ValueError("Speech attempt target is outside the persisted diagnostic sample")
    existing_item = await session.scalar(
        select(AssessmentItem.id).where(
            AssessmentItem.session_id == assessment.id,
            AssessmentItem.knowledge_point_id == payload.knowledge_point_id,
        )
    )
    if existing_item is not None:
        raise RuntimeError("This diagnostic character has already been answered")
    character = await session.scalar(
        select(ChineseCharacter).where(
            ChineseCharacter.knowledge_point_id == target.knowledge_point_id,
            ChineseCharacter.is_enabled.is_(True),
        )
    )
    if character is None:
        raise ValueError("Diagnostic target is not an enabled Chinese character")
    existing = await session.scalar(
        select(CharacterSpeechAttempt).where(
            CharacterSpeechAttempt.assessment_session_id == assessment.id,
            CharacterSpeechAttempt.knowledge_point_id == payload.knowledge_point_id,
            CharacterSpeechAttempt.attempt_index == payload.attempt_index,
        )
    )
    if existing is not None:
        return speech_attempt_response(existing)

    has_transcript = bool(payload.transcript or payload.alternatives)
    evaluation = evaluate_character_speech(
        character,
        payload.transcript,
        [item.transcript for item in payload.alternatives],
        confidence=payload.confidence,
        confidence_available=payload.confidence_available,
    )
    decision = evaluation.decision.value if has_transcript else payload.decision
    normalized_readings = (
        list(evaluation.normalized_readings) if has_transcript else payload.normalized_readings
    )
    attempt = CharacterSpeechAttempt(
        child_id=child_id,
        assessment_session_id=assessment.id,
        knowledge_point_id=payload.knowledge_point_id,
        attempt_index=payload.attempt_index,
        provider=payload.provider,
        transcript=payload.transcript,
        alternatives_json=[item.model_dump() for item in payload.alternatives],
        confidence=payload.confidence,
        confidence_available=payload.confidence_available,
        normalized_readings_json=normalized_readings,
        decision=decision,
        syllable_match=evaluation.syllable_match if has_transcript else payload.syllable_match,
        tone_match=evaluation.tone_match if has_transcript else payload.tone_match,
        tone_evaluation=(
            evaluation.tone_evaluation if has_transcript else payload.tone_evaluation
        ),
        explicit_unknown=evaluation.explicit_unknown or payload.explicit_unknown,
        hint_used=False,
        duration_ms=payload.duration_ms,
        provider_metadata={
            **payload.provider_metadata,
            "evaluator_user_id": str(evaluator_user_id),
            "diagnostic_version": LITERACY_DIAGNOSTIC_ESTIMATION_VERSION,
        },
    )
    session.add(attempt)
    await session.commit()
    await session.refresh(attempt)
    return speech_attempt_response(attempt)


async def literacy_diagnostic_history(
    session: AsyncSession,
    child_id: uuid.UUID,
    *,
    limit: int = 20,
) -> list[LiteracyDiagnosticHistoryEntry]:
    assessments = list(
        (
            await session.scalars(
                select(AssessmentSession)
                .where(
                    AssessmentSession.child_id == child_id,
                    AssessmentSession.source == LITERACY_DIAGNOSTIC_SOURCE,
                )
                .order_by(AssessmentSession.started_at.desc())
                .limit(limit)
            )
        ).all()
    )
    output: list[LiteracyDiagnosticHistoryEntry] = []
    for assessment in assessments:
        session_response = await literacy_diagnostic_session_response(session, assessment)
        counts = {
            "correct": 0,
            "uncertain": 0,
            "incorrect": 0,
        }
        for target in session_response.targets:
            if target.outcome in counts:
                counts[target.outcome] += 1
        output.append(
            LiteracyDiagnosticHistoryEntry(
                id=assessment.id,
                status=assessment.status,
                started_at=assessment.started_at,
                completed_at=assessment.completed_at,
                total_items=session_response.total_items,
                completed_items=session_response.completed_items,
                directly_known=counts["correct"],
                uncertain=counts["uncertain"],
                unknown=counts["incorrect"],
                result=session_response.result,
            )
        )
    return output


async def literacy_diagnostic_overview(
    session: AsyncSession,
    child_id: uuid.UUID,
) -> LiteracyDiagnosticOverviewResponse:
    history = await literacy_diagnostic_history(session, child_id, limit=10)
    active = await session.scalar(
        select(AssessmentSession)
        .where(
            AssessmentSession.child_id == child_id,
            AssessmentSession.source == LITERACY_DIAGNOSTIC_SOURCE,
            AssessmentSession.status == SessionStatus.IN_PROGRESS,
        )
        .order_by(AssessmentSession.started_at.desc())
        .limit(1)
    )
    latest_completed = await session.scalar(
        select(AssessmentSession)
        .where(
            AssessmentSession.child_id == child_id,
            AssessmentSession.source == LITERACY_DIAGNOSTIC_SOURCE,
            AssessmentSession.status == SessionStatus.COMPLETED,
        )
        .order_by(AssessmentSession.completed_at.desc(), AssessmentSession.started_at.desc())
        .limit(1)
    )
    return LiteracyDiagnosticOverviewResponse(
        active_session=(
            await literacy_diagnostic_session_response(session, active) if active else None
        ),
        latest_result=(
            await _result_for_assessment(session, latest_completed) if latest_completed else None
        ),
        history=history,
        recommended_sample_size=LITERACY_DIAGNOSTIC_SAMPLE_SIZE,
        segment_size=LITERACY_DIAGNOSTIC_SEGMENT_SIZE,
        limitation=LITERACY_DIAGNOSTIC_LIMITATION,
    )
