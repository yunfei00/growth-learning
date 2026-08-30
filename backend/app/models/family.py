"""Household membership and child profile models."""

import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.identity import TimestampMixin

if TYPE_CHECKING:
    from app.models.identity import User


class FamilyRole(StrEnum):
    """Adult roles supported by the Phase 2 authorization boundary."""

    ADMIN = "admin"
    COMPANION = "companion"


class AdultChildRelationType(StrEnum):
    """A family identity label that never grants authorization by itself."""

    FATHER = "father"
    MOTHER = "mother"
    GRANDFATHER = "grandfather"
    GRANDMOTHER = "grandmother"
    GUARDIAN = "guardian"
    OTHER = "other"


class Family(TimestampMixin, Base):
    """Top-level data boundary shared by adult members and child profiles."""

    __tablename__ = "families"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    members: Mapped[list["FamilyMember"]] = relationship(
        back_populates="family", passive_deletes=True
    )
    children: Mapped[list["Child"]] = relationship(back_populates="family", passive_deletes=True)


class FamilyMember(TimestampMixin, Base):
    """Adult membership grants a role within exactly one family."""

    __tablename__ = "family_members"
    __table_args__ = (
        UniqueConstraint("family_id", "user_id", name="uq_family_members_family_user"),
        CheckConstraint("role IN ('admin', 'companion')", name="ck_family_members_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    family: Mapped[Family] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="family_memberships")


class FamilyInvitation(TimestampMixin, Base):
    """A hashed, single-use capability to join one existing household."""

    __tablename__ = "family_invitations"
    __table_args__ = (
        CheckConstraint(
            "role_to_grant IN ('admin', 'companion')",
            name="ck_family_invitations_role",
        ),
        CheckConstraint("max_uses = 1", name="ck_family_invitations_single_use"),
        CheckConstraint(
            "used_count >= 0 AND used_count <= max_uses",
            name="ck_family_invitations_usage_bound",
        ),
        CheckConstraint(
            "email_constraint IS NULL OR email_constraint = lower(email_constraint)",
            name="ck_family_invitations_email_normalized",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    code_hint: Mapped[str] = mapped_column(String(20), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    role_to_grant: Mapped[str] = mapped_column(
        String(20), default=FamilyRole.COMPANION, server_default="companion", nullable=False
    )
    email_constraint: Mapped[str | None] = mapped_column(String(320), index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    max_uses: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdultChildRelation(TimestampMixin, Base):
    """Describe an adult's relationship to one child independently of permissions."""

    __tablename__ = "adult_child_relations"
    __table_args__ = (
        UniqueConstraint("user_id", "child_id", name="uq_adult_child_relation_user_child"),
        CheckConstraint(
            "relation IN ('father', 'mother', 'grandfather', 'grandmother', 'guardian', 'other')",
            name="ck_adult_child_relations_relation",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("children.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    relation: Mapped[str] = mapped_column(String(24), nullable=False)


class Child(TimestampMixin, Base):
    """A child profile belongs to a family and never authenticates as a user."""

    __tablename__ = "children"
    __table_args__ = (
        CheckConstraint(
            "gender IS NULL OR gender IN ('male', 'female', 'other')",
            name="ck_children_gender",
        ),
        CheckConstraint(
            "current_grade_level IS NULL OR current_grade_level BETWEEN 1 AND 9",
            name="ck_children_current_grade_level",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(80))
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[str | None] = mapped_column(String(20))
    avatar_key: Mapped[str | None] = mapped_column(String(255))
    current_grade_level: Mapped[int | None] = mapped_column(Integer, index=True)
    school_year: Mapped[str | None] = mapped_column(String(20))
    is_archived: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False, index=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    family: Mapped[Family] = relationship(back_populates="children")
