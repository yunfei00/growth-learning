"""Household membership and child profile models."""

import uuid
from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.identity import TimestampMixin

if TYPE_CHECKING:
    from app.models.identity import User


class FamilyRole(StrEnum):
    """Adult roles supported by the Phase 2 authorization boundary."""

    ADMIN = "admin"
    COMPANION = "companion"


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


class Child(TimestampMixin, Base):
    """A child profile belongs to a family and never authenticates as a user."""

    __tablename__ = "children"
    __table_args__ = (
        CheckConstraint(
            "gender IS NULL OR gender IN ('male', 'female', 'other')",
            name="ck_children_gender",
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

    family: Mapped[Family] = relationship(back_populates="children")
