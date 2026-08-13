"""Immutable mastery-aware stories and append-oriented reading evidence."""

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
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


class StoryDifficulty(StrEnum):
    BEGINNER = "beginner"
    NORMAL = "normal"
    CHALLENGE = "challenge"


class StoryGenerationStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class StoryKnowledgeRole(StrEnum):
    STRONG_KNOWN = "strong_known"
    USABLE_RECOGNIZING = "usable_recognizing"
    TARGET = "target"
    UNEXPECTED = "unexpected"


class ReadingStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class ReadingMode(StrEnum):
    INDEPENDENT = "independent"
    WITH_HELP = "with_help"


class ReadingAnswerOutcome(StrEnum):
    CORRECT = "correct"
    WITH_HELP = "with_help"
    PARTIAL = "partial"
    INCORRECT = "incorrect"


class DailyReadingStatus(StrEnum):
    NEEDS_STORY = "needs_story"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class Story(TimestampMixin, Base):
    """Child-private story identity; content always lives in immutable versions."""

    __tablename__ = "stories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    theme: Mapped[str] = mapped_column(String(40), nullable=False)
    custom_theme: Mapped[str | None] = mapped_column(String(80))


class StoryGenerationRun(TimestampMixin, Base):
    """Safe, auditable metadata for one bounded provider attempt loop."""

    __tablename__ = "story_generation_runs"
    __table_args__ = (
        UniqueConstraint("child_id", "request_key", name="uq_story_run_child_request_key"),
        CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed')",
            name="ck_story_generation_runs_status",
        ),
        CheckConstraint("attempt_count >= 0 AND attempt_count <= 3", name="ck_story_runs_attempts"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    story_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("stories.id", ondelete="RESTRICT"), index=True
    )
    story_version_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    request_key: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(
        String(20), default=StoryGenerationStatus.PENDING, server_default="pending", nullable=False
    )
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    theme: Mapped[str] = mapped_column(String(40), nullable=False)
    target_knowledge_point_ids: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )
    provider: Mapped[str] = mapped_column(String(60), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(30), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    failure_category: Mapped[str | None] = mapped_column(String(60))
    failure_message: Mapped[str | None] = mapped_column(String(240))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StoryVersion(TimestampMixin, Base):
    """Immutable generated content plus the exact policy/snapshot that accepted it."""

    __tablename__ = "story_versions"
    __table_args__ = (
        UniqueConstraint("story_id", "version_number", name="uq_story_versions_story_number"),
        CheckConstraint("version_number >= 1", name="ck_story_versions_number"),
        CheckConstraint(
            "difficulty IN ('beginner', 'normal', 'challenge')",
            name="ck_story_versions_difficulty",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    story_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stories.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    generation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("story_generation_runs.id", ondelete="RESTRICT"),
        unique=True,
        index=True,
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    paragraphs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    theme: Mapped[str] = mapped_column(String(40), nullable=False)
    custom_theme: Mapped[str | None] = mapped_column(String(80))
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    requested_known_coverage: Mapped[float] = mapped_column(Float, nullable=False)
    actual_strong_known_coverage: Mapped[float] = mapped_column(Float, nullable=False)
    actual_usable_known_coverage: Mapped[float] = mapped_column(Float, nullable=False)
    actual_target_coverage: Mapped[float] = mapped_column(Float, nullable=False)
    actual_unexpected_coverage: Mapped[float] = mapped_column(Float, nullable=False)
    unique_known_coverage: Mapped[float] = mapped_column(Float, nullable=False)
    total_han_occurrences: Mapped[int] = mapped_column(Integer, nullable=False)
    unique_han_count: Mapped[int] = mapped_column(Integer, nullable=False)
    unexpected_characters: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    target_characters: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    mastery_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    coverage_policy_version: Mapped[str] = mapped_column(String(30), nullable=False)
    analyzer_version: Mapped[str] = mapped_column(String(30), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(30), nullable=False)
    provider: Mapped[str] = mapped_column(String(60), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)


class StoryKnowledgePoint(TimestampMixin, Base):
    """Materialized character role and occurrence evidence for an immutable version."""

    __tablename__ = "story_knowledge_points"
    __table_args__ = (
        UniqueConstraint(
            "story_version_id", "knowledge_point_id", name="uq_story_knowledge_version_point"
        ),
        CheckConstraint(
            "role IN ('strong_known', 'usable_recognizing', 'target', 'unexpected')",
            name="ck_story_knowledge_points_role",
        ),
        CheckConstraint("occurrence_count >= 0", name="ck_story_knowledge_occurrences"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    story_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("story_versions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    mastery_level_at_generation: Mapped[str | None] = mapped_column(String(20))


class ReadingQuestion(TimestampMixin, Base):
    """Immutable, structured comprehension question attached to a story version."""

    __tablename__ = "reading_questions"
    __table_args__ = (
        UniqueConstraint("story_version_id", "position", name="uq_reading_questions_position"),
        CheckConstraint("position >= 0", name="ck_reading_questions_position"),
        CheckConstraint("correct_option_index >= 0", name="ck_reading_questions_answer"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    story_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("story_versions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    question: Mapped[str] = mapped_column(String(240), nullable=False)
    options: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    correct_option_index: Mapped[int] = mapped_column(Integer, nullable=False)


class ReadingSession(TimestampMixin, Base):
    """Resumable reading activity; completion is unique for a child/version pair."""

    __tablename__ = "reading_sessions"
    __table_args__ = (
        UniqueConstraint("child_id", "story_version_id", name="uq_reading_session_child_version"),
        CheckConstraint(
            "status IN ('in_progress', 'completed', 'abandoned')",
            name="ck_reading_sessions_status",
        ),
        CheckConstraint(
            "reading_mode IN ('independent', 'with_help')",
            name="ck_reading_sessions_mode",
        ),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_reading_sessions_duration",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    story_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("story_versions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    evaluator_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    reading_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=ReadingStatus.IN_PROGRESS, server_default="in_progress", nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    parent_note: Mapped[str | None] = mapped_column(Text)
    exposure_learning_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("learning_sessions.id", ondelete="RESTRICT"), unique=True
    )


class ReadingAnswer(TimestampMixin, Base):
    """One durable evaluated answer per reading session/question."""

    __tablename__ = "reading_answers"
    __table_args__ = (
        UniqueConstraint("reading_session_id", "question_id", name="uq_reading_answer_session_q"),
        CheckConstraint(
            "outcome IN ('correct', 'with_help', 'partial', 'incorrect')",
            name="ck_reading_answers_outcome",
        ),
        CheckConstraint("selected_option_index >= 0", name="ck_reading_answers_selected"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    reading_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reading_sessions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reading_questions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    evaluator_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    selected_option_index: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DailyReadingTask(TimestampMixin, Base):
    """Coherent reading extension for a persisted Phase 5 daily plan."""

    __tablename__ = "daily_reading_tasks"
    __table_args__ = (
        UniqueConstraint("daily_plan_id", name="uq_daily_reading_task_plan"),
        CheckConstraint(
            "status IN ('needs_story', 'pending', 'in_progress', 'completed')",
            name="ck_daily_reading_tasks_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    daily_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("daily_learning_plans.id", ondelete="RESTRICT"),
        unique=True,
        index=True,
        nullable=False,
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    task_date: Mapped[date] = mapped_column(Date, nullable=False)
    story_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("story_versions.id", ondelete="RESTRICT"), index=True
    )
    reading_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reading_sessions.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default=DailyReadingStatus.NEEDS_STORY, server_default="needs_story"
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
