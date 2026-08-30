"""Reusable course paths layered over canonical knowledge and evidence."""

import uuid
from datetime import datetime
from enum import IntEnum, StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
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


class EducationStage(StrEnum):
    FOUNDATION = "foundation"
    PRIMARY = "primary"
    JUNIOR_MIDDLE = "junior_middle"


class GradeLevel(IntEnum):
    GRADE_1 = 1
    GRADE_2 = 2
    GRADE_3 = 3
    GRADE_4 = 4
    GRADE_5 = 5
    GRADE_6 = 6
    GRADE_7 = 7
    GRADE_8 = 8
    GRADE_9 = 9


GRADE_LEVEL_LABELS: dict[int, str] = {
    1: "一年级",
    2: "二年级",
    3: "三年级",
    4: "四年级",
    5: "五年级",
    6: "六年级",
    7: "七年级",
    8: "八年级",
    9: "九年级",
}


class Semester(StrEnum):
    FULL_YEAR = "full_year"
    SEMESTER_1 = "semester_1"
    SEMESTER_2 = "semester_2"


class CurriculumReleaseStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class CurriculumSourceType(StrEnum):
    PROJECT_CURATED = "project_curated"
    CURRICULUM_STANDARD_REFERENCE = "curriculum_standard_reference"
    TEXTBOOK_REFERENCE = "textbook_reference"
    TEACHER_CURATED = "teacher_curated"


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
            "education_stage IN ('foundation', 'primary', 'junior_middle')",
            name="ck_courses_education_stage",
        ),
        CheckConstraint(
            "semester IN ('full_year', 'semester_1', 'semester_2')",
            name="ck_courses_semester",
        ),
        CheckConstraint(
            "(education_stage = 'foundation' AND grade_level IS NULL) OR "
            "(education_stage = 'primary' AND grade_level BETWEEN 1 AND 6) OR "
            "(education_stage = 'junior_middle' AND grade_level BETWEEN 7 AND 9)",
            name="ck_courses_stage_grade",
        ),
        UniqueConstraint(
            "curriculum_key", "curriculum_version", name="uq_courses_curriculum_version"
        ),
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
    education_stage: Mapped[str] = mapped_column(
        String(30), default=EducationStage.FOUNDATION, server_default="foundation", nullable=False
    )
    grade_level: Mapped[int | None] = mapped_column(Integer, index=True)
    semester: Mapped[str] = mapped_column(
        String(20), default=Semester.FULL_YEAR, server_default="full_year", nullable=False
    )
    curriculum_key: Mapped[str | None] = mapped_column(String(180), index=True)
    curriculum_version: Mapped[str | None] = mapped_column(String(80), index=True)
    curriculum_release_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("curriculum_releases.id", ondelete="RESTRICT"), unique=True, index=True
    )
    reference_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class CurriculumRelease(TimestampMixin, Base):
    """Audited immutable version container for one curriculum path."""

    __tablename__ = "curriculum_releases"
    __table_args__ = (
        UniqueConstraint(
            "curriculum_key", "release_version", name="uq_curriculum_release_identity"
        ),
        CheckConstraint(
            "status IN ('draft', 'in_review', 'published', 'archived')",
            name="ck_curriculum_releases_status",
        ),
        CheckConstraint(
            "education_stage IN ('foundation', 'primary', 'junior_middle')",
            name="ck_curriculum_releases_stage",
        ),
        CheckConstraint(
            "semester IN ('full_year', 'semester_1', 'semester_2')",
            name="ck_curriculum_releases_semester",
        ),
        CheckConstraint(
            "(education_stage = 'foundation' AND grade_level IS NULL) OR "
            "(education_stage = 'primary' AND grade_level BETWEEN 1 AND 6) OR "
            "(education_stage = 'junior_middle' AND grade_level BETWEEN 7 AND 9)",
            name="ck_curriculum_releases_stage_grade",
        ),
        CheckConstraint(
            "subject IN ('chinese', 'math', 'english', 'science')",
            name="ck_curriculum_releases_subject",
        ),
        CheckConstraint(
            "source_type IN ('project_curated', 'curriculum_standard_reference', "
            "'textbook_reference', 'teacher_curated')",
            name="ck_curriculum_releases_source_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    curriculum_key: Mapped[str] = mapped_column(String(180), index=True, nullable=False)
    release_version: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    education_stage: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    grade_level: Mapped[int | None] = mapped_column(Integer, index=True)
    semester: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), default=CurriculumReleaseStatus.DRAFT, server_default="draft", nullable=False
    )
    source_type: Mapped[str] = mapped_column(
        String(40), default=CurriculumSourceType.PROJECT_CURATED, nullable=False
    )
    source_name: Mapped[str] = mapped_column(String(160), default="Growth Learning", nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(500))
    license: Mapped[str | None] = mapped_column(String(120))
    copyright_notice: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    published_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    change_summary: Mapped[str | None] = mapped_column(Text)
    validation_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


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


class CourseLesson(TimestampMixin, Base):
    """Optional transition layer for legacy courses, required by formal curricula."""

    __tablename__ = "course_lessons"
    __table_args__ = (
        UniqueConstraint("course_unit_id", "order_index", name="uq_course_lesson_order"),
        CheckConstraint("order_index >= 0", name="ck_course_lessons_order"),
        CheckConstraint(
            "status IN ('draft', 'enabled', 'archived')", name="ck_course_lessons_status"
        ),
        CheckConstraint(
            "estimated_minutes IS NULL OR estimated_minutes > 0",
            name="ck_course_lessons_estimated_minutes",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_unit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_units.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft", server_default="draft")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


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
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("course_lessons.id", ondelete="RESTRICT"), index=True
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
    reference_code: Mapped[str | None] = mapped_column(String(160))
    curriculum_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


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
    curriculum_release_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("curriculum_releases.id", ondelete="RESTRICT"), index=True
    )
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


class CoursePlatformEvent(Base):
    """Privacy-friendly first-party course analytics without child content payloads."""

    __tablename__ = "course_platform_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('course_started', 'lesson_started', 'lesson_completed', "
            "'activity_completed', 'course_returned')",
            name="ck_course_platform_events_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    enrollment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("child_course_enrollments.id", ondelete="RESTRICT"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    is_first_party: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
