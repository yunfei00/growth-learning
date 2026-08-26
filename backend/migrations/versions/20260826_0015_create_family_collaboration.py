"""Create family collaboration, adult-child relations, and child archival.

Revision ID: 20260826_0015
Revises: 20260826_0014
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260826_0015"
down_revision: str | None = "20260826_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "children",
        sa.Column("is_archived", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("children", sa.Column("archived_at", sa.DateTime(timezone=True)))
    op.create_index(op.f("ix_children_is_archived"), "children", ["is_archived"])

    op.create_table(
        "family_invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("code_hint", sa.String(length=20), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role_to_grant",
            sa.String(length=20),
            server_default="companion",
            nullable=False,
        ),
        sa.Column("email_constraint", sa.String(length=320)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_uses", sa.Integer(), server_default="1", nullable=False),
        sa.Column("used_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("accepted_by_user_id", sa.Uuid()),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "role_to_grant IN ('admin', 'companion')",
            name="ck_family_invitations_role",
        ),
        sa.CheckConstraint("max_uses = 1", name="ck_family_invitations_single_use"),
        sa.CheckConstraint(
            "used_count >= 0 AND used_count <= max_uses",
            name="ck_family_invitations_usage_bound",
        ),
        sa.CheckConstraint(
            "email_constraint IS NULL OR email_constraint = lower(email_constraint)",
            name="ck_family_invitations_email_normalized",
        ),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["accepted_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
    )
    for column in (
        "family_id",
        "created_by_user_id",
        "email_constraint",
        "expires_at",
        "accepted_by_user_id",
    ):
        op.create_index(
            op.f(f"ix_family_invitations_{column}"),
            "family_invitations",
            [column],
        )

    op.create_table(
        "adult_child_relations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("relation", sa.String(length=24), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "relation IN ('father', 'mother', 'grandfather', 'grandmother', 'guardian', 'other')",
            name="ck_adult_child_relations_relation",
        ),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "child_id", name="uq_adult_child_relation_user_child"),
    )
    for column in ("family_id", "user_id", "child_id"):
        op.create_index(
            op.f(f"ix_adult_child_relations_{column}"),
            "adult_child_relations",
            [column],
        )


def downgrade() -> None:
    for column in ("child_id", "user_id", "family_id"):
        op.drop_index(
            op.f(f"ix_adult_child_relations_{column}"),
            table_name="adult_child_relations",
        )
    op.drop_table("adult_child_relations")
    for column in (
        "accepted_by_user_id",
        "expires_at",
        "email_constraint",
        "created_by_user_id",
        "family_id",
    ):
        op.drop_index(
            op.f(f"ix_family_invitations_{column}"),
            table_name="family_invitations",
        )
    op.drop_table("family_invitations")
    op.drop_index(op.f("ix_children_is_archived"), table_name="children")
    op.drop_column("children", "archived_at")
    op.drop_column("children", "is_archived")
