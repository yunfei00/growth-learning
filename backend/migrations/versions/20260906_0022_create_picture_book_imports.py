"""Add private picture-book source/page metadata.

Revision ID: 20260906_0022
Revises: 20260830_0021
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0022"
down_revision: str | None = "20260830_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "picture_book_imports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("story_version_id", sa.Uuid(), nullable=False),
        sa.Column("imported_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("source_provider", sa.String(length=32), nullable=False),
        sa.Column("source_book_id", sa.String(length=80), nullable=False),
        sa.Column("source_h5p_id", sa.String(length=80)),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("license_name", sa.String(length=80), nullable=False),
        sa.Column("reading_level", sa.String(length=40), nullable=False),
        sa.Column("attribution", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("pages", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
        sa.Column("cover_object_key", sa.String(length=500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["story_version_id"], ["story_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["imported_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "child_id", "source_provider", "source_book_id", name="uq_picture_book_child_source"
        ),
        sa.UniqueConstraint("story_version_id", name="uq_picture_book_story_version"),
    )
    for column in ("child_id", "story_version_id", "imported_by_user_id"):
        op.create_index(
            op.f(f"ix_picture_book_imports_{column}"), "picture_book_imports", [column]
        )


def downgrade() -> None:
    for column in ("imported_by_user_id", "story_version_id", "child_id"):
        op.drop_index(op.f(f"ix_picture_book_imports_{column}"), table_name="picture_book_imports")
    op.drop_table("picture_book_imports")
