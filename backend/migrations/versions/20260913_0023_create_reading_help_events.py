"""Add append-only reading help events.

Revision ID: 20260913_0023
Revises: 20260906_0022
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_0023"
down_revision: str | None = "20260906_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reading_help_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reading_session_id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("story_version_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_point_id", sa.Uuid()),
        sa.Column("character", sa.String(length=8), nullable=False),
        sa.Column("pinyin", sa.String(length=40)),
        sa.Column(
            "help_kind",
            sa.String(length=30),
            server_default="character_tap",
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["reading_session_id"], ["reading_sessions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["story_version_id"], ["story_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "reading_session_id",
        "child_id",
        "story_version_id",
        "knowledge_point_id",
    ):
        op.create_index(op.f(f"ix_reading_help_events_{column}"), "reading_help_events", [column])


def downgrade() -> None:
    for column in (
        "knowledge_point_id",
        "story_version_id",
        "child_id",
        "reading_session_id",
    ):
        op.drop_index(op.f(f"ix_reading_help_events_{column}"), table_name="reading_help_events")
    op.drop_table("reading_help_events")
