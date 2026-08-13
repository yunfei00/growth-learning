"""Unified growth archive, immutable reports/books, and private export jobs."""

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
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


class GrowthEventCategory(StrEnum):
    LEARNING = "learning"
    ASSESSMENT = "assessment"
    READING = "reading"
    SCIENCE = "science"
    FAMILY = "family"
    ORIGINAL_WORDS = "original_words"
    ACHIEVEMENT = "achievement"
    REPORT = "report"


class GrowthEventType(StrEnum):
    LEARNING_MILESTONE = "learning_milestone"
    ASSESSMENT_MILESTONE = "assessment_milestone"
    READING_MILESTONE = "reading_milestone"
    SCIENCE_MILESTONE = "science_milestone"
    ORIGINAL_WORDS = "original_words"
    MANUAL_GROWTH_NOTE = "manual_growth_note"
    FAMILY_OBSERVATION = "family_observation"
    ACHIEVEMENT = "achievement"
    REPORT_MARKER = "report_marker"


class GrowthSourceType(StrEnum):
    SYSTEM = "system"
    PARENT = "parent"
    COMPANION = "companion"


class GrowthReportPeriod(StrEnum):
    MONTHLY = "monthly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class GrowthBookEdition(StrEnum):
    YEARLY = "yearly"
    AGE_YEAR = "age_year"


class ExportJobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class GrowthEvent(TimestampMixin, Base):
    """Child-centric projection that always keeps a traceable evidence reference."""

    __tablename__ = "growth_events"
    __table_args__ = (
        UniqueConstraint("child_id", "idempotency_key", name="uq_growth_event_idempotency"),
        CheckConstraint(
            "event_type IN ('learning_milestone', 'assessment_milestone', "
            "'reading_milestone', 'science_milestone', 'original_words', "
            "'manual_growth_note', 'family_observation', 'achievement', 'report_marker')",
            name="ck_growth_events_type",
        ),
        CheckConstraint(
            "category IN ('learning', 'assessment', 'reading', 'science', 'family', "
            "'original_words', 'achievement', 'report')",
            name="ck_growth_events_category",
        ),
        CheckConstraint(
            "source_type IN ('system', 'parent', 'companion')",
            name="ck_growth_events_source",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    source_entity_type: Mapped[str | None] = mapped_column(String(60), index=True)
    source_entity_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(180))
    evidence_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    policy_version: Mapped[str] = mapped_column(
        String(30), default="growth-event-v1", server_default="growth-event-v1", nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    correction_of_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("growth_events.id", ondelete="RESTRICT"), index=True
    )


class GrowthMediaAsset(Base):
    """Private media attached to a manual growth event."""

    __tablename__ = "growth_media_assets"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="ck_growth_media_size"),
        CheckConstraint("media_kind IN ('image', 'video', 'audio')", name="ck_growth_media_kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    growth_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("growth_events.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    object_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    uploader_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class GrowthReport(TimestampMixin, Base):
    """Stable report identity; generated content is append-only in versions."""

    __tablename__ = "growth_reports"
    __table_args__ = (
        UniqueConstraint(
            "child_id", "period_type", "period_start", "period_end", name="uq_growth_report_period"
        ),
        CheckConstraint(
            "period_type IN ('monthly', 'yearly', 'custom')", name="ck_growth_report_period"
        ),
        CheckConstraint("period_end >= period_start", name="ck_growth_report_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    period_type: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )


class GrowthReportVersion(Base):
    """Immutable deterministic report snapshot with optional separate AI narrative."""

    __tablename__ = "growth_report_versions"
    __table_args__ = (
        UniqueConstraint("report_id", "version_number", name="uq_growth_report_version"),
        CheckConstraint("version_number >= 1", name="ck_growth_report_version_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("growth_reports.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    source_cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(30), nullable=False)
    metrics_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    deterministic_sections: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    selected_event_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    ai_narrative: Mapped[str | None] = mapped_column(Text)
    ai_provider: Mapped[str | None] = mapped_column(String(60))
    ai_model: Mapped[str | None] = mapped_column(String(120))
    ai_prompt_version: Mapped[str | None] = mapped_column(String(30))
    ai_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GrowthBook(TimestampMixin, Base):
    """Memory-oriented edition identity distinct from analytical reports."""

    __tablename__ = "growth_books"
    __table_args__ = (
        UniqueConstraint("child_id", "edition_type", "edition_key", name="uq_growth_book_edition"),
        CheckConstraint("edition_type IN ('yearly', 'age_year')", name="ck_growth_book_edition"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    edition_type: Mapped[str] = mapped_column(String(20), nullable=False)
    edition_key: Mapped[str] = mapped_column(String(40), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )


class GrowthBookVersion(Base):
    """Immutable curated book snapshot and its parent message."""

    __tablename__ = "growth_book_versions"
    __table_args__ = (
        UniqueConstraint("growth_book_id", "version_number", name="uq_growth_book_version"),
        CheckConstraint("version_number >= 1", name="ck_growth_book_version_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    growth_book_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("growth_books.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    selected_event_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    selected_media: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list, nullable=False)
    snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    parent_message: Mapped[str | None] = mapped_column(Text)
    message_author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    message_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ExportJob(TimestampMixin, Base):
    """Audited private family-export job stored in object storage."""

    __tablename__ = "export_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed', 'expired')",
            name="ck_export_jobs_status",
        ),
        CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="ck_export_jobs_size"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    child_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default=ExportJobStatus.PENDING, server_default="pending", nullable=False
    )
    schema_version: Mapped[str] = mapped_column(
        String(50), default="growth-learning-export-v1", server_default="growth-learning-export-v1"
    )
    object_key: Mapped[str | None] = mapped_column(String(512), unique=True)
    manifest_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSON)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    failure_reason: Mapped[str | None] = mapped_column(String(240))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
