"""Platform admission invitations and privacy-safe account audit events."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


class InvitationPurpose(StrEnum):
    CREATE_ACCOUNT = "create_account"


class InvitationStoredStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXHAUSTED = "exhausted"


class PlatformInvitation(TimestampMixin, Base):
    """A hashed, bounded platform admission capability."""

    __tablename__ = "platform_invitations"
    __table_args__ = (
        CheckConstraint("purpose IN ('create_account')", name="ck_platform_invitation_purpose"),
        CheckConstraint(
            "status IN ('active', 'revoked', 'exhausted')",
            name="ck_platform_invitation_status",
        ),
        CheckConstraint("max_uses > 0", name="ck_platform_invitation_max_uses"),
        CheckConstraint("used_count >= 0", name="ck_platform_invitation_used_count"),
        CheckConstraint("used_count <= max_uses", name="ck_platform_invitation_usage_bound"),
        CheckConstraint(
            "email_constraint IS NULL OR email_constraint = lower(email_constraint)",
            name="ck_platform_invitation_email_normalized",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    code_hint: Mapped[str] = mapped_column(String(20), nullable=False)
    purpose: Mapped[str] = mapped_column(
        String(30),
        default=InvitationPurpose.CREATE_ACCOUNT,
        server_default=InvitationPurpose.CREATE_ACCOUNT,
        nullable=False,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=InvitationStoredStatus.ACTIVE,
        server_default=InvitationStoredStatus.ACTIVE,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    max_uses: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    email_constraint: Mapped[str | None] = mapped_column(String(320), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlatformAuditLog(Base):
    """Append-only security audit data with secrets deliberately excluded."""

    __tablename__ = "platform_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
