"""Weekend science catalog, household materials, and authentic experiment evidence."""

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
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


class ScienceDifficulty(StrEnum):
    INTRO = "intro"
    EXPLORE = "explore"
    ADVANCED = "advanced"


class ScienceExperimentStatus(StrEnum):
    DRAFT = "draft"
    ENABLED = "enabled"
    ARCHIVED = "archived"


class ScienceExperimentSource(StrEnum):
    SYSTEM = "system"
    FAMILY = "family"


class ExperimentSessionStatus(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class ExperimentStep(StrEnum):
    QUESTION = "question"
    PREDICTION = "prediction"
    MATERIALS = "materials"
    EXPERIMENT = "experiment"
    OBSERVATION = "observation"
    EXPLANATION = "explanation"
    FOLLOW_UP = "follow_up"
    SUMMARY = "summary"
    COMPLETE = "complete"


class ExperimentEvidenceType(StrEnum):
    PREDICTION = "prediction"
    OBSERVATION = "observation"
    CHILD_SUMMARY = "child_summary"
    QUESTION_ASKED = "question_asked"
    CHILD_ORIGINAL_WORDS = "child_original_words"
    PARENT_EXPLANATION = "parent_explanation"


class ExperimentMediaKind(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class ScienceExperiment(TimestampMixin, Base):
    """Mutable catalog identity; every content revision also creates an immutable version."""

    __tablename__ = "science_experiments"
    __table_args__ = (
        CheckConstraint("age_min >= 0", name="ck_science_experiments_age_min"),
        CheckConstraint(
            "age_max IS NULL OR age_max >= age_min", name="ck_science_experiments_age_range"
        ),
        CheckConstraint(
            "difficulty IN ('intro', 'explore', 'advanced')",
            name="ck_science_experiments_difficulty",
        ),
        CheckConstraint(
            "status IN ('draft', 'enabled', 'archived')",
            name="ck_science_experiments_status",
        ),
        CheckConstraint(
            "source_type IN ('system', 'family')", name="ck_science_experiments_source"
        ),
        CheckConstraint("estimated_duration_minutes > 0", name="ck_science_experiments_duration"),
        CheckConstraint("content_version >= 1", name="ck_science_experiments_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    canonical_key: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    age_min: Mapped[int] = mapped_column(Integer, nullable=False)
    age_max: Mapped[int | None] = mapped_column(Integer)
    difficulty: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    estimated_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    guiding_question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_phenomenon: Mapped[str] = mapped_column(Text, nullable=False)
    child_friendly_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    parent_scientific_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    safety_notes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    common_failure_reasons: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    follow_up_questions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    likely_child_questions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    steps: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=ScienceExperimentStatus.DRAFT, server_default="draft", nullable=False
    )
    source_type: Mapped[str] = mapped_column(
        String(20), default=ScienceExperimentSource.SYSTEM, server_default="system", nullable=False
    )
    owner_family_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("families.id", ondelete="RESTRICT"), index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    content_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class ScienceExperimentVersion(Base):
    """Immutable authored snapshot used by future child experiment sessions."""

    __tablename__ = "science_experiment_versions"
    __table_args__ = (
        UniqueConstraint(
            "experiment_id", "version_number", name="uq_science_experiment_version_number"
        ),
        CheckConstraint("version_number >= 1", name="ck_science_experiment_versions_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("science_experiments.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ExperimentMaterial(TimestampMixin, Base):
    """Reusable, non-commerce household material concept."""

    __tablename__ = "experiment_materials"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    canonical_key: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(String(40))
    category: Mapped[str | None] = mapped_column(String(60), index=True)
    safety_note: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class ExperimentMaterialRequirement(TimestampMixin, Base):
    """Required/optional material with authored quantity and substitution guidance."""

    __tablename__ = "experiment_material_requirements"
    __table_args__ = (
        UniqueConstraint("experiment_id", "material_id", name="uq_experiment_material_requirement"),
        CheckConstraint("position >= 0", name="ck_experiment_material_requirement_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("science_experiments.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    material_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiment_materials.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    quantity_text: Mapped[str | None] = mapped_column(String(120))
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    substitution_notes: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class FamilyMaterial(TimestampMixin, Base):
    """Household-scoped inventory; only a family admin manages the global record."""

    __tablename__ = "family_materials"
    __table_args__ = (
        UniqueConstraint("family_id", "material_id", name="uq_family_material_inventory"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    material_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiment_materials.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    is_owned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    quantity_text: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )


class ExperimentKnowledgePoint(TimestampMixin, Base):
    """Catalog linkage that enables explicit exposure, never recognition correctness."""

    __tablename__ = "experiment_knowledge_points"
    __table_args__ = (
        UniqueConstraint(
            "experiment_id", "knowledge_point_id", name="uq_experiment_knowledge_point"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("science_experiments.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    exposure_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class ExperimentSession(TimestampMixin, Base):
    """One child's resumable experiment using an immutable authored snapshot."""

    __tablename__ = "experiment_sessions"
    __table_args__ = (
        UniqueConstraint("child_id", "request_key", name="uq_experiment_session_request_key"),
        CheckConstraint(
            "status IN ('planned', 'in_progress', 'completed', 'abandoned')",
            name="ck_experiment_sessions_status",
        ),
        CheckConstraint(
            "current_step IN ('question', 'prediction', 'materials', 'experiment', "
            "'observation', 'explanation', 'follow_up', 'summary', 'complete')",
            name="ck_experiment_sessions_step",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("science_experiments.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    experiment_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("science_experiment_versions.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    experiment_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    accompanying_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    request_key: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(
        String(20),
        default=ExperimentSessionStatus.IN_PROGRESS,
        server_default="in_progress",
        nullable=False,
    )
    current_step: Mapped[str] = mapped_column(
        String(24), default=ExperimentStep.QUESTION, server_default="question", nullable=False
    )
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parent_note: Mapped[str | None] = mapped_column(Text)
    exposure_learning_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("learning_sessions.id", ondelete="RESTRICT"), unique=True, index=True
    )


class ExperimentEvidence(Base):
    """Append-only original text and non-scoring capability tags."""

    __tablename__ = "experiment_evidence"
    __table_args__ = (
        UniqueConstraint("experiment_session_id", "client_key", name="uq_experiment_evidence_key"),
        CheckConstraint(
            "evidence_type IN ('prediction', 'observation', 'child_summary', "
            "'question_asked', 'child_original_words', 'parent_explanation')",
            name="ck_experiment_evidence_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    experiment_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiment_sessions.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    capability_tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    recorder_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    client_key: Mapped[str | None] = mapped_column(String(80))
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    derived_summary: Mapped[str | None] = mapped_column(Text)
    derived_provider: Mapped[str | None] = mapped_column(String(60))
    derived_model: Mapped[str | None] = mapped_column(String(120))
    derived_version: Mapped[str | None] = mapped_column(String(30))


class ExperimentMediaAsset(Base):
    """Private object metadata tied to exactly one household experiment session."""

    __tablename__ = "experiment_media_assets"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="ck_experiment_media_size"),
        CheckConstraint(
            "media_kind IN ('image', 'video', 'audio')", name="ck_experiment_media_kind"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    experiment_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiment_sessions.id", ondelete="RESTRICT"), index=True, nullable=False
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
