"""Parent-authorized teacher collaboration without household membership."""

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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


class TeacherProfileStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class TeacherRelationStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class ClassroomStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class ClassroomMembershipStatus(StrEnum):
    ACTIVE = "active"
    LEFT = "left"


class TeacherAssignmentType(StrEnum):
    CHARACTER_LEARNING = "character_learning"
    CHARACTER_REVIEW = "character_review"
    RECOGNITION_CHECK = "recognition_check"
    READING = "reading"
    FREEFORM_INSTRUCTION = "freeform_instruction"


class TeacherAssignmentStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"
    ARCHIVED = "archived"


class TeacherProgressStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TeacherObservationCategory(StrEnum):
    RECOGNITION = "recognition"
    READING = "reading"
    EXPRESSION = "expression"
    LEARNING_HABIT = "learning_habit"
    PARTICIPATION = "participation"
    OTHER = "other"


class TeacherProfile(TimestampMixin, Base):
    """Optional teacher mode for an authenticated adult user."""

    __tablename__ = "teacher_profiles"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'disabled')", name="ck_teacher_profiles_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), unique=True, index=True, nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    organization_name: Mapped[str | None] = mapped_column(String(120))
    short_bio: Mapped[str | None] = mapped_column(String(300))
    teacher_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=TeacherProfileStatus.ACTIVE, server_default="active", nullable=False
    )


class TeacherChildRelation(TimestampMixin, Base):
    """Auditable family-admin grant from one teacher to one child only."""

    __tablename__ = "teacher_child_relations"
    __table_args__ = (
        UniqueConstraint("teacher_id", "child_id", name="uq_teacher_child_relation"),
        CheckConstraint(
            "status IN ('active', 'revoked')", name="ck_teacher_child_relations_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teacher_profiles.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default=TeacherRelationStatus.ACTIVE, server_default="active", nullable=False
    )
    authorized_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    authorized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    permission_scope: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    permission_version: Mapped[str] = mapped_column(
        String(30), default="teacher-scope-v1", server_default="teacher-scope-v1", nullable=False
    )


class Classroom(TimestampMixin, Base):
    """A teacher-owned lightweight group, never a school organization."""

    __tablename__ = "classrooms"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived')", name="ck_classrooms_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teacher_profiles.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(300))
    class_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=ClassroomStatus.ACTIVE, server_default="active", nullable=False
    )


class ClassroomMembership(TimestampMixin, Base):
    """Parent-confirmed enrollment linked to the live teacher-child grant."""

    __tablename__ = "classroom_memberships"
    __table_args__ = (
        UniqueConstraint("classroom_id", "child_id", name="uq_classroom_membership_child"),
        CheckConstraint("status IN ('active', 'left')", name="ck_classroom_memberships_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    classroom_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("classrooms.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    relation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teacher_child_relations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=ClassroomMembershipStatus.ACTIVE,
        server_default="active",
        nullable=False,
    )
    joined_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TeacherAssignment(TimestampMixin, Base):
    """Small teacher-owned task whose evidence stays in canonical systems."""

    __tablename__ = "teacher_assignments"
    __table_args__ = (
        CheckConstraint(
            "assignment_type IN ('character_learning', 'character_review', "
            "'recognition_check', 'reading', 'freeform_instruction')",
            name="ck_teacher_assignments_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'published', 'closed', 'archived')",
            name="ck_teacher_assignments_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teacher_profiles.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    classroom_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("classrooms.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    assignment_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(
        String(20), default=TeacherAssignmentStatus.DRAFT, server_default="draft", nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TeacherAssignmentTarget(Base):
    """Published child target snapshot; active authorization is still checked per request."""

    __tablename__ = "teacher_assignment_targets"
    __table_args__ = (
        UniqueConstraint("assignment_id", "child_id", name="uq_teacher_assignment_target"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teacher_assignments.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    relation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teacher_child_relations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TeacherAssignmentKnowledgePoint(Base):
    """Ordered canonical character references for an assignment."""

    __tablename__ = "teacher_assignment_knowledge_points"
    __table_args__ = (
        UniqueConstraint("assignment_id", "knowledge_point_id", name="uq_teacher_assignment_point"),
        UniqueConstraint("assignment_id", "position", name="uq_teacher_assignment_position"),
        CheckConstraint("position >= 1", name="ck_teacher_assignment_point_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teacher_assignments.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class TeacherAssignmentProgress(TimestampMixin, Base):
    """Resumable workflow pointer linked to canonical evidence sessions."""

    __tablename__ = "teacher_assignment_progress"
    __table_args__ = (
        UniqueConstraint("assignment_id", "child_id", name="uq_teacher_assignment_progress"),
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed')",
            name="ck_teacher_assignment_progress_status",
        ),
        CheckConstraint("completed_item_count >= 0", name="ck_teacher_progress_count"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teacher_assignments.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default=TeacherProgressStatus.PENDING, server_default="pending", nullable=False
    )
    completed_item_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    learning_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("learning_sessions.id", ondelete="RESTRICT"), unique=True, index=True
    )
    assessment_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assessment_sessions.id", ondelete="RESTRICT"), unique=True, index=True
    )
    reading_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reading_sessions.id", ondelete="RESTRICT"), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TeacherObservation(Base):
    """Append-only exact teacher wording; never a mastery override."""

    __tablename__ = "teacher_observations"
    __table_args__ = (
        CheckConstraint(
            "category IN ('recognition', 'reading', 'expression', 'learning_habit', "
            "'participation', 'other')",
            name="ck_teacher_observations_category",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teacher_profiles.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    relation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teacher_child_relations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    classroom_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("classrooms.id", ondelete="RESTRICT"), index=True
    )
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teacher_assignments.id", ondelete="RESTRICT"), index=True
    )
    category: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TeacherObservationKnowledgePoint(Base):
    """Optional canonical character references for an observation."""

    __tablename__ = "teacher_observation_knowledge_points"
    __table_args__ = (
        UniqueConstraint(
            "observation_id", "knowledge_point_id", name="uq_teacher_observation_point"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    observation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teacher_observations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="RESTRICT"), index=True, nullable=False
    )
