"""Append-oriented child learning evidence and derived mastery state."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
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


class AssessmentOutcome(StrEnum):
    CORRECT = "correct"
    HINTED_CORRECT = "hinted_correct"
    UNCERTAIN = "uncertain"
    INCORRECT = "incorrect"


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
            "'story_exposure', 'science_experiment_exposure')",
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
    assessed_at: Mapped[datetime] = mapped_column(
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
