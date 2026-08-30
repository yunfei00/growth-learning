"""Append-oriented child learning evidence and derived mastery state."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


class SessionStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class LearningActivityType(StrEnum):
    INTRODUCED = "introduced"
    RELEARNED = "relearned"
    PARENT_MARKED_SEEN = "parent_marked_seen"
    STORY_EXPOSURE = "story_exposure"
    SCIENCE_EXPERIMENT_EXPOSURE = "science_experiment_exposure"
    GUIDED_PRACTICE = "guided_practice"
    INDEPENDENT_PRACTICE = "independent_practice"
    REVIEWED = "reviewed"
    APPLIED = "applied"


class AssessmentKind(StrEnum):
    RECOGNITION = "recognition"
    PRACTICE_CHECK = "practice_check"
    LISTENING_CHECK = "listening_check"
    ORAL_CHECK = "oral_check"
    MATH_CHECK = "math_check"


class AssessmentOutcome(StrEnum):
    CORRECT = "correct"
    HINTED_CORRECT = "hinted_correct"
    UNCERTAIN = "uncertain"
    INCORRECT = "incorrect"


class SpeechReviewDecision(StrEnum):
    MATCH = "match"
    PARTIAL_MATCH = "partial_match"
    UNCERTAIN = "uncertain"
    NO_MATCH = "no_match"
    NO_SPEECH = "no_speech"
    RECOGNITION_ERROR = "recognition_error"


class MasteryLevel(StrEnum):
    UNLEARNED = "unlearned"
    INTRODUCED = "introduced"
    RECOGNIZING = "recognizing"
    PROFICIENT = "proficient"
    STABLE = "stable"


class LearningSession(TimestampMixin, Base):
    """A bounded child learning activity performed by an authorized adult."""

    __tablename__ = "learning_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress', 'completed', 'abandoned')",
            name="ck_learning_sessions_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default=SessionStatus.IN_PROGRESS, server_default=SessionStatus.IN_PROGRESS
    )
    source: Mapped[str] = mapped_column(String(40), default="parent_assisted", nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LearningRecord(TimestampMixin, Base):
    """Immutable evidence that a canonical knowledge point was presented to a child."""

    __tablename__ = "learning_records"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "knowledge_point_id", name="uq_learning_record_session_point"
        ),
        CheckConstraint(
            "activity_type IN ('introduced', 'relearned', 'parent_marked_seen', "
            "'story_exposure', 'science_experiment_exposure', 'guided_practice', "
            "'independent_practice', 'reviewed', 'applied')",
            name="ck_learning_records_activity_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_sessions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    activity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(40), default="parent_assisted", nullable=False)
    learned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AssessmentSession(TimestampMixin, Base):
    """A bounded recognition check performed by an authorized adult."""

    __tablename__ = "assessment_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress', 'completed', 'abandoned')",
            name="ck_assessment_sessions_status",
        ),
        CheckConstraint(
            "assessment_kind IN ('recognition', 'practice_check', 'listening_check', "
            "'oral_check', 'math_check')",
            name="ck_assessment_sessions_kind",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    evaluator_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default=SessionStatus.IN_PROGRESS, server_default=SessionStatus.IN_PROGRESS
    )
    source: Mapped[str] = mapped_column(String(40), default="quick_recognition", nullable=False)
    assessment_kind: Mapped[str] = mapped_column(
        String(30),
        default=AssessmentKind.RECOGNITION,
        server_default=AssessmentKind.RECOGNITION,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AssessmentItem(TimestampMixin, Base):
    """Immutable outcome evidence for one child and one canonical knowledge point."""

    __tablename__ = "assessment_items"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "knowledge_point_id", name="uq_assessment_item_session_point"
        ),
        CheckConstraint(
            "outcome IN ('correct', 'hinted_correct', 'uncertain', 'incorrect')",
            name="ck_assessment_items_outcome",
        ),
        CheckConstraint(
            "response_time_ms IS NULL OR response_time_ms >= 0",
            name="ck_assessment_items_response_time",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_sessions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    evaluator_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    hint_used: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    skill_dimension: Mapped[str | None] = mapped_column(String(60))
    evidence_metadata: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict, server_default="{}", nullable=False
    )
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CharacterSpeechAttempt(Base):
    """Privacy-minimal ASR evidence attached to the canonical assessment session."""

    __tablename__ = "character_speech_attempts"
    __table_args__ = (
        UniqueConstraint(
            "assessment_session_id",
            "knowledge_point_id",
            "attempt_index",
            name="uq_character_speech_attempt_session_point_index",
        ),
        CheckConstraint("attempt_index >= 1", name="ck_character_speech_attempts_index"),
        CheckConstraint(
            "decision IN ('match', 'partial_match', 'uncertain', 'no_match', "
            "'no_speech', 'recognition_error')",
            name="ck_character_speech_attempts_decision",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_character_speech_attempts_duration",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_character_speech_attempts_confidence",
        ),
        CheckConstraint(
            "tone_evaluation IN ('matched', 'mismatched', 'unavailable')",
            name="ck_character_speech_attempts_tone_evaluation",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    assessment_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_sessions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    attempt_index: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    transcript: Mapped[str | None] = mapped_column(Text)
    alternatives_json: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, default=list, server_default="[]", nullable=False
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    confidence_available: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    normalized_readings_json: Mapped[list[str]] = mapped_column(
        JSON, default=list, server_default="[]", nullable=False
    )
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    syllable_match: Mapped[bool | None] = mapped_column(Boolean)
    tone_match: Mapped[bool | None] = mapped_column(Boolean)
    tone_evaluation: Mapped[str] = mapped_column(
        String(20), default="unavailable", server_default="unavailable", nullable=False
    )
    explicit_unknown: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    hint_used: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    provider_metadata: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict, server_default="{}", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AssessmentOverride(Base):
    """Append-only parent correction while the machine result remains auditable."""

    __tablename__ = "assessment_overrides"
    __table_args__ = (
        CheckConstraint(
            "original_outcome IN ('correct', 'hinted_correct', 'uncertain', 'incorrect')",
            name="ck_assessment_overrides_original",
        ),
        CheckConstraint(
            "override_outcome IN ('correct', 'hinted_correct', 'uncertain', 'incorrect')",
            name="ck_assessment_overrides_override",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    assessment_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_items.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    original_outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    override_outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    overridden_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    override_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    overridden_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChildKnowledgeState(TimestampMixin, Base):
    """Rebuildable mastery projection; raw learning and assessment evidence remains canonical."""

    __tablename__ = "child_knowledge_states"
    __table_args__ = (
        UniqueConstraint(
            "child_id", "knowledge_point_id", name="uq_child_knowledge_state_child_point"
        ),
        CheckConstraint(
            "mastery_level IN ('unlearned', 'introduced', 'recognizing', 'proficient', 'stable')",
            name="ck_child_knowledge_states_level",
        ),
        CheckConstraint(
            "mastery_score >= 0 AND mastery_score <= 1",
            name="ck_child_knowledge_states_score",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    mastery_level: Mapped[str] = mapped_column(
        String(20), default=MasteryLevel.UNLEARNED, server_default=MasteryLevel.UNLEARNED
    )
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    first_introduced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_learning_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    correct_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    hinted_correct_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    uncertain_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    incorrect_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    consecutive_correct: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    consecutive_incorrect: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    average_response_time_ms: Mapped[float | None] = mapped_column(Float)
    is_priority: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    algorithm_version: Mapped[str] = mapped_column(String(20), default="v1", server_default="v1")
    policy_key: Mapped[str] = mapped_column(
        String(80), default="chinese-character-v1", server_default="chinese-character-v1"
    )
    state_code: Mapped[str] = mapped_column(
        String(40), default=MasteryLevel.UNLEARNED, server_default=MasteryLevel.UNLEARNED
    )
    dimensions_json: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict, server_default="{}", nullable=False
    )
