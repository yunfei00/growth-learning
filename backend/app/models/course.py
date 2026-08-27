"""Reusable course paths layered over canonical knowledge and evidence."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


class CourseSubject(StrEnum):
    CHINESE = "chinese"
    MATH = "math"
    ENGLISH = "english"
    SCIENCE = "science"


class CourseSourceType(StrEnum):
    SYSTEM = "system"
    FAMILY = "family"
    TEACHER = "teacher"
    TEXTBOOK_REFERENCE = "textbook_reference"


class CourseStatus(StrEnum):
    DRAFT = "draft"
    ENABLED = "enabled"
    ARCHIVED = "archived"


class ActivityType(StrEnum):
    KNOWLEDGE_LEARNING = "knowledge_learning"
    GUIDED_PRACTICE = "guided_practice"
    INDEPENDENT_PRACTICE = "independent_practice"
    KNOWLEDGE_REVIEW = "knowledge_review"
    KNOWLEDGE_CHECK = "knowledge_check"
    LISTENING = "listening"
    SPEAKING = "speaking"
    CHARACTER_LEARNING = "character_learning"
    CHARACTER_REVIEW = "character_review"
    RECOGNITION_CHECK = "recognition_check"
    READING = "reading"
    SCIENCE_REFERENCE = "science_reference"
    OFFLINE_INSTRUCTION = "offline_instruction"


class KnowledgePointRole(StrEnum):
    PRIMARY = "primary"
    REVIEW = "review"
    OPTIONAL = "optional"
    PREREQUISITE = "prerequisite"


class EnrollmentStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ActivityProgressStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class CatalogRelease(TimestampMixin, Base):
    """Immutable provenance frame for one catalog snapshot."""

    __tablename__ = "catalog_releases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    catalog_version: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(500))
    license: Mapped[str | None] = mapped_column(String(120))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(default=False, server_default="false", nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class CharacterCatalogEntry(TimestampMixin, Base):
    """Membership of a canonical character in a versioned catalog snapshot."""

    __tablename__ = "character_catalog_entries"
    __table_args__ = (
        UniqueConstraint("catalog_release_id", "knowledge_point_id", name="uq_catalog_entry_point"),
        UniqueConstraint("catalog_release_id", "order_index", name="uq_catalog_entry_order"),
        CheckConstraint("order_index >= 0", name="ck_catalog_entry_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    catalog_release_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("catalog_releases.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(500))


class Course(TimestampMixin, Base):
    __tablename__ = "courses"
    __table_args__ = (
        CheckConstraint(
            "subject IN ('chinese', 'math', 'english', 'science')",
            name="ck_courses_subject",
        ),
        CheckConstraint(
            "source_type IN ('system', 'family', 'teacher', 'textbook_reference')",
            name="ck_courses_source",
        ),
        CheckConstraint("status IN ('draft', 'enabled', 'archived')", name="ck_courses_status"),
        CheckConstraint("version >= 1", name="ck_courses_version"),
        CheckConstraint(
            "(source_type = 'system' AND family_id IS NULL AND teacher_id IS NULL) OR "
            "(source_type IN ('family', 'textbook_reference') AND family_id IS NOT NULL "
            "AND teacher_id IS NULL) OR "
            "(source_type = 'teacher' AND family_id IS NULL AND teacher_id IS NOT NULL)",
            name="ck_courses_owner",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    subject: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    family_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("families.id", ondelete="RESTRICT"), index=True
    )
    teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teacher_profiles.id", ondelete="RESTRICT"), index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    recommended_age_min: Mapped[int | None] = mapped_column(Integer)
    recommended_age_max: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft", server_default="draft")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    system_key: Mapped[str | None] = mapped_column(String(100), unique=True)
    reference_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class CourseUnit(TimestampMixin, Base):
    __tablename__ = "course_units"
    __table_args__ = (
        UniqueConstraint("course_id", "order_index", name="uq_course_unit_order"),
        CheckConstraint("order_index >= 0", name="ck_course_units_order"),
        CheckConstraint(
            "status IN ('draft', 'enabled', 'archived')", name="ck_course_units_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="enabled", server_default="enabled")


class LearningActivity(TimestampMixin, Base):
    __tablename__ = "learning_activities"
    __table_args__ = (
        UniqueConstraint("course_unit_id", "order_index", name="uq_learning_activity_order"),
        CheckConstraint("order_index >= 0", name="ck_learning_activities_order"),
        CheckConstraint(
            "activity_type IN ('knowledge_learning', 'guided_practice', "
            "'independent_practice', 'knowledge_review', 'knowledge_check', 'listening', "
            "'speaking', 'character_learning', 'character_review', 'recognition_check', "
            "'reading', 'science_reference', 'offline_instruction')",
            name="ck_learning_activities_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'enabled', 'archived')",
            name="ck_learning_activities_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_unit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_units.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    activity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="enabled", server_default="enabled")
    content_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ActivityKnowledgePoint(TimestampMixin, Base):
    __tablename__ = "activity_knowledge_points"
    __table_args__ = (
        UniqueConstraint("activity_id", "knowledge_point_id", name="uq_activity_knowledge_point"),
        CheckConstraint("order_index >= 0", name="ck_activity_knowledge_points_order"),
        CheckConstraint(
            "role IN ('primary', 'review', 'optional', 'prerequisite')",
            name="ck_activity_knowledge_points_role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    activity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_activities.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)


class ChildCourseEnrollment(TimestampMixin, Base):
    __tablename__ = "child_course_enrollments"
    __table_args__ = (
        UniqueConstraint("child_id", "course_id", name="uq_child_course_enrollment"),
        CheckConstraint(
            "status IN ('planned', 'active', 'paused', 'completed', 'archived')",
            name="ck_child_course_enrollments_status",
        ),
        CheckConstraint("path_order >= 0", name="ck_child_course_enrollments_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    course_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="planned", server_default="planned")
    path_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    current_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("course_units.id", ondelete="RESTRICT")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class CourseActivityProgress(TimestampMixin, Base):
    __tablename__ = "course_activity_progress"
    __table_args__ = (
        UniqueConstraint("enrollment_id", "activity_id", name="uq_course_activity_progress"),
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed')",
            name="ck_course_activity_progress_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("child_course_enrollments.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    activity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_activities.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    learning_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("learning_sessions.id", ondelete="RESTRICT")
    )
    assessment_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assessment_sessions.id", ondelete="RESTRICT")
    )
    reading_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reading_sessions.id", ondelete="RESTRICT")
    )
    experiment_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("experiment_sessions.id", ondelete="RESTRICT")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
