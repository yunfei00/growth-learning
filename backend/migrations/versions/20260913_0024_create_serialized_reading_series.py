"""Add child-private serialized reading series and ordered episodes.

Revision ID: 20260913_0024
Revises: 20260913_0023
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_0024"
down_revision: str | None = "20260913_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "story_series",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("season_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("total_episodes", sa.Integer(), nullable=False),
        sa.Column("content_version", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("season_number >= 1", name="ck_story_series_season_number"),
        sa.CheckConstraint("total_episodes >= 1", name="ck_story_series_total_episodes"),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("child_id", "slug", name="uq_story_series_child_slug"),
    )
    op.create_index(op.f("ix_story_series_child_id"), "story_series", ["child_id"])
    op.create_index(
        op.f("ix_story_series_created_by_user_id"), "story_series", ["created_by_user_id"]
    )

    op.create_table(
        "story_episodes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("series_id", sa.Uuid(), nullable=False),
        sa.Column("episode_number", sa.Integer(), nullable=False),
        sa.Column("chapter_title", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("paragraphs", sa.JSON(), nullable=False),
        sa.Column("focus_characters", sa.JSON(), nullable=False),
        sa.Column("story_version_id", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("episode_number >= 1", name="ck_story_episode_number"),
        sa.ForeignKeyConstraint(["series_id"], ["story_series.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["story_version_id"], ["story_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("series_id", "episode_number", name="uq_story_episode_series_number"),
        sa.UniqueConstraint("story_version_id", name="uq_story_episode_story_version"),
    )
    op.create_index(op.f("ix_story_episodes_series_id"), "story_episodes", ["series_id"])
    op.create_index(
        op.f("ix_story_episodes_story_version_id"), "story_episodes", ["story_version_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_story_episodes_story_version_id"), table_name="story_episodes")
    op.drop_index(op.f("ix_story_episodes_series_id"), table_name="story_episodes")
    op.drop_table("story_episodes")
    op.drop_index(op.f("ix_story_series_created_by_user_id"), table_name="story_series")
    op.drop_index(op.f("ix_story_series_child_id"), table_name="story_series")
    op.drop_table("story_series")
