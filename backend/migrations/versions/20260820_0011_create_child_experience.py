"""Create deterministic achievements and positive-only family rewards.

Revision ID: 20260820_0011
Revises: 20260820_0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0011"
down_revision: str | None = "20260820_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def _index(table: str, column: str, *, unique: bool = False) -> None:
    op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=unique)


def upgrade() -> None:
    op.create_table(
        "achievement_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("icon", sa.String(16), nullable=False),
        sa.Column("rule_type", sa.String(60), nullable=False),
        sa.Column("threshold", sa.Integer(), nullable=False),
        sa.Column("rule_version", sa.String(30), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("threshold >= 1", name="ck_achievement_definitions_threshold"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    _index("achievement_definitions", "key", unique=True)

    op.create_table(
        "family_reward_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("stars_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("family_id"),
    )
    _index("family_reward_settings", "family_id", unique=True)

    op.create_table(
        "family_reward_goals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("required_stars", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("required_stars > 0", name="ck_family_reward_goal_positive"),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    _index("family_reward_goals", "family_id")
    _index("family_reward_goals", "created_by_user_id")

    op.create_table(
        "child_achievements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("achievement_definition_id", sa.Uuid(), nullable=False),
        sa.Column("rule_version", sa.String(30), nullable=False),
        sa.Column("evidence_source_type", sa.String(50), nullable=False),
        sa.Column("evidence_source_id", sa.Uuid()),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "unlocked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["achievement_definition_id"], ["achievement_definitions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "child_id", "achievement_definition_id", name="uq_child_achievement_definition"
        ),
    )
    _index("child_achievements", "child_id")
    _index("child_achievements", "achievement_definition_id")
    _index("child_achievements", "evidence_source_id")

    op.create_table(
        "star_ledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason_type", sa.String(50), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("rule_version", sa.String(30), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        *_timestamps(),
        sa.CheckConstraint("amount > 0", name="ck_star_ledger_positive_amount"),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "child_id",
            "reason_type",
            "source_type",
            "source_id",
            "rule_version",
            name="uq_star_ledger_source_rule",
        ),
    )
    _index("star_ledger", "child_id")
    _index("star_ledger", "source_id")


def downgrade() -> None:
    for table in (
        "star_ledger",
        "child_achievements",
        "family_reward_goals",
        "family_reward_settings",
        "achievement_definitions",
    ):
        op.drop_table(table)
