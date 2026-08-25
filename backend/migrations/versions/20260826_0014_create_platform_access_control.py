"""Create invite-only platform access control and account lifecycle data.

Revision ID: 20260826_0014
Revises: 20260823_0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260826_0014"
down_revision: str | None = "20260823_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("account_status", sa.String(length=20), server_default="active", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column(
            "registration_source", sa.String(length=30), server_default="legacy", nullable=False
        ),
    )
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True)))
    op.add_column(
        "users", sa.Column("session_version", sa.Integer(), server_default="0", nullable=False)
    )

    # Existing identities are explicitly grandfathered in. Invitations only gate new accounts.
    op.execute(
        "UPDATE users SET account_status = 'active', is_active = true, "
        "registration_source = 'legacy', session_version = 0"
    )
    op.create_check_constraint(
        "ck_users_account_status",
        "users",
        "account_status IN ('active', 'suspended', 'disabled')",
    )
    op.create_check_constraint(
        "ck_users_registration_source",
        "users",
        "registration_source IN ('legacy', 'platform_invitation', 'admin_created')",
    )
    op.create_check_constraint(
        "ck_users_active_status_consistent",
        "users",
        "is_active = (account_status = 'active')",
    )
    op.create_check_constraint("ck_users_session_version", "users", "session_version >= 0")

    op.create_table(
        "platform_invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("code_hint", sa.String(length=20), nullable=False),
        sa.Column("purpose", sa.String(length=30), server_default="create_account", nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_uses", sa.Integer(), server_default="1", nullable=False),
        sa.Column("used_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("email_constraint", sa.String(length=320)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("purpose IN ('create_account')", name="ck_platform_invitation_purpose"),
        sa.CheckConstraint(
            "status IN ('active', 'revoked', 'exhausted')",
            name="ck_platform_invitation_status",
        ),
        sa.CheckConstraint("max_uses > 0", name="ck_platform_invitation_max_uses"),
        sa.CheckConstraint("used_count >= 0", name="ck_platform_invitation_used_count"),
        sa.CheckConstraint("used_count <= max_uses", name="ck_platform_invitation_usage_bound"),
        sa.CheckConstraint(
            "email_constraint IS NULL OR email_constraint = lower(email_constraint)",
            name="ck_platform_invitation_email_normalized",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
    )
    op.create_index(
        op.f("ix_platform_invitations_code_hash"),
        "platform_invitations",
        ["code_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_platform_invitations_created_by_user_id"),
        "platform_invitations",
        ["created_by_user_id"],
    )
    op.create_index(
        op.f("ix_platform_invitations_email_constraint"),
        "platform_invitations",
        ["email_constraint"],
    )
    op.create_index(
        op.f("ix_platform_invitations_expires_at"), "platform_invitations", ["expires_at"]
    )

    op.add_column("users", sa.Column("registered_via_invitation_id", sa.Uuid()))
    op.create_foreign_key(
        "fk_users_registered_via_invitation_id",
        "users",
        "platform_invitations",
        ["registered_via_invitation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_users_registered_via_invitation_id"),
        "users",
        ["registered_via_invitation_id"],
    )

    op.create_table(
        "platform_audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid()),
        sa.Column("target_user_id", sa.Uuid()),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("actor_user_id", "target_user_id", "event_type", "created_at"):
        op.create_index(op.f(f"ix_platform_audit_logs_{column}"), "platform_audit_logs", [column])


def downgrade() -> None:
    for column in ("created_at", "event_type", "target_user_id", "actor_user_id"):
        op.drop_index(op.f(f"ix_platform_audit_logs_{column}"), table_name="platform_audit_logs")
    op.drop_table("platform_audit_logs")
    op.drop_index(op.f("ix_users_registered_via_invitation_id"), table_name="users")
    op.drop_constraint("fk_users_registered_via_invitation_id", "users", type_="foreignkey")
    op.drop_column("users", "registered_via_invitation_id")
    op.drop_index(op.f("ix_platform_invitations_expires_at"), table_name="platform_invitations")
    op.drop_index(
        op.f("ix_platform_invitations_email_constraint"), table_name="platform_invitations"
    )
    op.drop_index(
        op.f("ix_platform_invitations_created_by_user_id"), table_name="platform_invitations"
    )
    op.drop_index(op.f("ix_platform_invitations_code_hash"), table_name="platform_invitations")
    op.drop_table("platform_invitations")
    op.drop_constraint("ck_users_session_version", "users", type_="check")
    op.drop_constraint("ck_users_active_status_consistent", "users", type_="check")
    op.drop_constraint("ck_users_registration_source", "users", type_="check")
    op.drop_constraint("ck_users_account_status", "users", type_="check")
    op.drop_column("users", "session_version")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "registration_source")
    op.drop_column("users", "account_status")
