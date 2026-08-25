"""Authenticated adult identity model."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.family import FamilyMember


class TimestampMixin:
    """UTC audit timestamps shared by mutable business entities."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SystemRole(StrEnum):
    """Platform authority, deliberately independent from household roles."""

    USER = "user"
    ADMIN = "admin"


class AccountStatus(StrEnum):
    """Authoritative platform account lifecycle state."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DISABLED = "disabled"


class RegistrationSource(StrEnum):
    """How a platform identity was originally admitted."""

    LEGACY = "legacy"
    PLATFORM_INVITATION = "platform_invitation"
    ADMIN_CREATED = "admin_created"


class User(TimestampMixin, Base):
    """An authenticated adult; child profiles are deliberately separate."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="ck_users_email_normalized"),
        CheckConstraint("system_role IN ('user', 'admin')", name="ck_users_system_role"),
        CheckConstraint(
            "account_status IN ('active', 'suspended', 'disabled')",
            name="ck_users_account_status",
        ),
        CheckConstraint(
            "registration_source IN ('legacy', 'platform_invitation', 'admin_created')",
            name="ck_users_registration_source",
        ),
        CheckConstraint(
            "is_active = (account_status = 'active')",
            name="ck_users_active_status_consistent",
        ),
        CheckConstraint("session_version >= 0", name="ck_users_session_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    account_status: Mapped[str] = mapped_column(
        String(20),
        default=AccountStatus.ACTIVE,
        server_default=AccountStatus.ACTIVE,
        nullable=False,
    )
    system_role: Mapped[str] = mapped_column(
        String(20), default=SystemRole.USER, server_default=SystemRole.USER, nullable=False
    )
    registration_source: Mapped[str] = mapped_column(
        String(30),
        default=RegistrationSource.LEGACY,
        server_default=RegistrationSource.LEGACY,
        nullable=False,
    )
    registered_via_invitation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "platform_invitations.id",
            name="fk_users_registered_via_invitation_id",
            ondelete="SET NULL",
            use_alter=True,
        ),
        index=True,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session_version: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

    family_memberships: Mapped[list["FamilyMember"]] = relationship(
        back_populates="user", passive_deletes=True
    )
