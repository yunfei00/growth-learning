"""Privacy-minimal speech evaluation for children's character review.

The browser owns microphone access and ASR.  This module only receives a short
transcript and structured alternatives; it never accepts or stores raw audio.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from pypinyin import Style, lazy_pinyin
from pypinyin.contrib.tone_convert import to_tone3
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssessmentItem,
    AssessmentOutcome,
    AssessmentOverride,
    AssessmentSession,
    AssessmentSessionTarget,
    AssessmentSource,
    CharacterSpeechAttempt,
    ChineseCharacter,
    SessionStatus,
    SpeechReviewDecision,
)
from app.schemas.learning import (
    AssessmentOverrideResponse,
    SpeechAttemptCreate,
    SpeechAttemptResponse,
)

_UNKNOWN_PHRASES = {
    "不知道",
    "我不知道",
    "不会",
    "我不会",
    "不会读",
    "我不会读",
    "不认识",
    "我不认识",
}
_PINYIN_TONE_RE = re.compile(r"^([a-züv]+)([1-5])$")
_PINYIN_SYLLABLE_RE = re.compile(r"^[a-züv]+$")


def normalize_pinyin(value: str) -> str:
    """Normalize tone marks, numeric tones, case, and ü/v spelling to tone3."""

    text = unicodedata.normalize("NFKC", value or "").strip().lower()
    text = re.sub(r"[\s'’\-]+", "", text).replace("u:", "ü").replace("v", "ü")
    if not text:
        return ""
    converted = to_tone3(text)
    match = _PINYIN_TONE_RE.match(converted)
    if match:
        return converted
    if _PINYIN_SYLLABLE_RE.match(converted):
        return converted
    return ""


def _readings_for_chinese(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    return [normalize_pinyin(item) for item in lazy_pinyin(text, style=Style.TONE3) if item]


def _tone_parts(reading: str) -> tuple[str, str | None]:
    match = _PINYIN_TONE_RE.match(reading)
    if match:
        return match.group(1), match.group(2)
    return reading, None


@dataclass(frozen=True)
class SpeechEvaluation:
    decision: SpeechReviewDecision
    normalized_readings: tuple[str, ...]
    syllable_match: bool | None
    tone_match: bool | None
    tone_evaluation: str
    explicit_unknown: bool = False


def _compact(value: str | None) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value or "")).lower()


def evaluate_character_speech(
    character: ChineseCharacter,
    transcript: str | None,
    alternatives: Iterable[str] = (),
    *,
    confidence: float | None = None,
    confidence_available: bool = False,
) -> SpeechEvaluation:
    """Evaluate a browser transcript conservatively.

    Confidence is retained as evidence but deliberately does not decide mastery.
    A transcript can match a curated alternate reading (for example ``行``/``hang2``),
    while a tone-only disagreement remains uncertain instead of incorrect.
    """

    del confidence, confidence_available  # never use ASR confidence as mastery
    raw_values = [value for value in [transcript, *alternatives] if value]
    compact_values = [_compact(value) for value in raw_values]
    if any(
        phrase in value
        for value in compact_values
        for phrase in _UNKNOWN_PHRASES
        if len(value) <= 18
    ):
        return SpeechEvaluation(
            SpeechReviewDecision.NO_MATCH, (), False, False, "unavailable", True
        )
    if not compact_values:
        return SpeechEvaluation(SpeechReviewDecision.NO_SPEECH, (), None, None, "unavailable")

    # Avoid treating a long sentence containing the target as an accidental answer.
    if any(len(value) > 12 or len(value) > 32 for value in compact_values):
        return SpeechEvaluation(SpeechReviewDecision.UNCERTAIN, (), None, None, "unavailable")

    expected = normalize_pinyin(character.pinyin)
    valid_readings = {expected}
    for reading in character.accepted_readings or []:
        normalized = normalize_pinyin(reading)
        if normalized:
            valid_readings.add(normalized)
    normalized: list[str] = []
    for value in compact_values:
        if any(char in value for char in character.character):
            # Short phrases such as “东方的东” are explicit enough to count.
            normalized.extend(_readings_for_chinese(character.character))
        elif re.search(r"[\u3400-\u9fff]", value):
            normalized.extend(_readings_for_chinese(value))
        else:
            pinyin = normalize_pinyin(value)
            if pinyin:
                normalized.append(pinyin)
    # Preserve order while removing duplicates.
    normalized = list(dict.fromkeys(item for item in normalized if item))
    if not normalized:
        return SpeechEvaluation(SpeechReviewDecision.UNCERTAIN, (), None, None, "unavailable")

    expected_syllable = _tone_parts(expected)[0]
    syllables = {_tone_parts(item)[0] for item in normalized}
    if expected_syllable in syllables and any(_tone_parts(item)[1] is None for item in normalized):
        return SpeechEvaluation(
            SpeechReviewDecision.PARTIAL_MATCH,
            tuple(normalized),
            True,
            None,
            "unavailable",
        )
    if valid_readings.intersection(normalized):
        return SpeechEvaluation(
            SpeechReviewDecision.MATCH,
            tuple(normalized),
            True,
            True,
            "matched",
        )
    if expected_syllable in syllables or any(
        _tone_parts(item)[0] == _tone_parts(valid)[0]
        for item in normalized
        for valid in valid_readings
    ):
        return SpeechEvaluation(
            SpeechReviewDecision.UNCERTAIN,
            tuple(normalized),
            True,
            False,
            "mismatched",
        )
    if any(_tone_parts(item)[1] is None for item in normalized):
        return SpeechEvaluation(
            SpeechReviewDecision.PARTIAL_MATCH,
            tuple(normalized),
            None,
            None,
            "unavailable",
        )
    return SpeechEvaluation(
        SpeechReviewDecision.NO_MATCH,
        tuple(normalized),
        False,
        False,
        "mismatched",
    )


def speech_attempt_response(attempt: CharacterSpeechAttempt) -> SpeechAttemptResponse:
    return SpeechAttemptResponse(
        id=attempt.id,
        attempt_index=attempt.attempt_index,
        provider=attempt.provider,
        transcript=attempt.transcript,
        alternatives=attempt.alternatives_json,
        confidence=attempt.confidence,
        confidence_available=attempt.confidence_available,
        normalized_readings=attempt.normalized_readings_json,
        decision=attempt.decision,
        syllable_match=attempt.syllable_match,
        tone_match=attempt.tone_match,
        tone_evaluation=attempt.tone_evaluation,
        explicit_unknown=attempt.explicit_unknown,
        hint_used=attempt.hint_used,
        duration_ms=attempt.duration_ms,
        created_at=attempt.created_at,
    )


async def persist_speech_attempt(
    session: AsyncSession,
    child_id: uuid.UUID,
    assessment_session_id: uuid.UUID,
    evaluator_user_id: uuid.UUID,
    payload: SpeechAttemptCreate,
) -> SpeechAttemptResponse:
    assessment = await session.scalar(
        select(AssessmentSession).where(
            AssessmentSession.id == assessment_session_id,
            AssessmentSession.child_id == child_id,
            AssessmentSession.source == AssessmentSource.DAILY_REVIEW,
            AssessmentSession.status == SessionStatus.IN_PROGRESS,
        )
    )
    if assessment is None:
        raise LookupError("Speech review session not found")
    target = await session.scalar(
        select(AssessmentSessionTarget).where(
            AssessmentSessionTarget.assessment_session_id == assessment.id,
            AssessmentSessionTarget.knowledge_point_id == payload.knowledge_point_id,
        )
    )
    if target is None:
        raise ValueError("Speech attempt target is outside the persisted review sample")
    character = await session.scalar(
        select(ChineseCharacter).where(
            ChineseCharacter.knowledge_point_id == target.knowledge_point_id
        )
    )
    if character is None:
        raise ValueError("Speech attempt target is not a Chinese character")
    existing = await session.scalar(
        select(CharacterSpeechAttempt).where(
            CharacterSpeechAttempt.assessment_session_id == assessment.id,
            CharacterSpeechAttempt.knowledge_point_id == payload.knowledge_point_id,
            CharacterSpeechAttempt.attempt_index == payload.attempt_index,
        )
    )
    if existing is not None:
        return speech_attempt_response(existing)
    evaluation = evaluate_character_speech(
        character,
        payload.transcript,
        [item.transcript for item in payload.alternatives],
        confidence=payload.confidence,
        confidence_available=payload.confidence_available,
    )
    # For an explicit no-speech/error event the browser has no transcript to
    # evaluate; preserve that transport decision while making transcript-based
    # decisions server-authoritative.
    has_transcript = bool(payload.transcript or payload.alternatives)
    decision = evaluation.decision.value if has_transcript else payload.decision
    normalized_readings = (
        list(evaluation.normalized_readings) if has_transcript else payload.normalized_readings
    )
    syllable_match = evaluation.syllable_match if has_transcript else payload.syllable_match
    tone_match = evaluation.tone_match if has_transcript else payload.tone_match
    tone_evaluation = evaluation.tone_evaluation if has_transcript else payload.tone_evaluation
    explicit_unknown = evaluation.explicit_unknown or payload.explicit_unknown
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
        syllable_match=syllable_match,
        tone_match=tone_match,
        tone_evaluation=tone_evaluation,
        explicit_unknown=explicit_unknown,
        hint_used=payload.hint_used or target.hint_requested_at is not None,
        duration_ms=payload.duration_ms,
        provider_metadata=payload.provider_metadata,
    )
    # Evaluator identity is intentionally retained in provider metadata only as a
    # non-sensitive audit marker; no audio or biometric data is persisted.
    attempt.provider_metadata = {
        **attempt.provider_metadata,
        "evaluator_user_id": str(evaluator_user_id),
    }
    session.add(attempt)
    await session.commit()
    await session.refresh(attempt)
    return speech_attempt_response(attempt)


async def mark_review_hint(
    session: AsyncSession,
    child_id: uuid.UUID,
    assessment_session_id: uuid.UUID,
    knowledge_point_id: uuid.UUID,
) -> datetime:
    assessment = await session.scalar(
        select(AssessmentSession).where(
            AssessmentSession.id == assessment_session_id,
            AssessmentSession.child_id == child_id,
            AssessmentSession.source == AssessmentSource.DAILY_REVIEW,
            AssessmentSession.status == SessionStatus.IN_PROGRESS,
        )
    )
    if assessment is None:
        raise LookupError("Speech review session not found")
    target = await session.scalar(
        select(AssessmentSessionTarget).where(
            AssessmentSessionTarget.assessment_session_id == assessment.id,
            AssessmentSessionTarget.knowledge_point_id == knowledge_point_id,
        )
    )
    if target is None:
        raise ValueError("Hint target is outside the persisted review sample")
    target.hint_requested_at = target.hint_requested_at or datetime.now(UTC)
    await session.commit()
    return target.hint_requested_at


async def override_assessment_item(
    session: AsyncSession,
    child_id: uuid.UUID,
    assessment_item_id: uuid.UUID,
    overridden_by_user_id: uuid.UUID,
    outcome: str,
    reason: str,
) -> AssessmentOverrideResponse:
    item = await session.scalar(
        select(AssessmentItem).where(
            AssessmentItem.id == assessment_item_id,
            AssessmentItem.child_id == child_id,
        )
    )
    if item is None:
        raise LookupError("Assessment item not found")
    if outcome not in {value.value for value in AssessmentOutcome}:
        raise ValueError("Unsupported assessment outcome")
    original = await session.scalar(
        select(AssessmentOverride.original_outcome)
        .where(AssessmentOverride.assessment_item_id == item.id)
        .order_by(AssessmentOverride.overridden_at.asc())
    )
    original_outcome = original or item.outcome
    override = AssessmentOverride(
        assessment_item_id=item.id,
        child_id=child_id,
        original_outcome=original_outcome,
        override_outcome=outcome,
        overridden_by_user_id=overridden_by_user_id,
        override_reason=reason,
    )
    session.add(override)
    item.outcome = outcome
    if outcome == AssessmentOutcome.HINTED_CORRECT:
        item.hint_used = True
    item.evidence_metadata = {
        **(item.evidence_metadata or {}),
        "evaluation_method": "parent_manual",
    }
    # Import lazily to keep the speech evaluator dependency-free for unit tests.
    from app.services.mastery import recompute_child_knowledge_state
    from app.services.review_planning import recompute_review_schedule

    await session.flush()
    item.evidence_metadata = {
        **(item.evidence_metadata or {}),
        "last_override_id": str(override.id),
    }
    await recompute_child_knowledge_state(session, child_id, item.knowledge_point_id)
    await recompute_review_schedule(session, child_id, item.knowledge_point_id)
    await session.commit()
    await session.refresh(override)
    return AssessmentOverrideResponse(
        id=override.id,
        original_outcome=override.original_outcome,
        override_outcome=override.override_outcome,
        overridden_by_user_id=override.overridden_by_user_id,
        override_reason=override.override_reason,
        overridden_at=override.overridden_at,
    )
