"""Create canonical knowledge catalog.

Revision ID: 20260812_0003
Revises: 20260812_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0003"
down_revision: str | None = "20260812_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_points",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("canonical_key", sa.String(length=160), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_reference", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("type IN ('chinese_character')", name="ck_knowledge_points_type"),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_knowledge_points_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_knowledge_points_type"), "knowledge_points", ["type"])
    op.create_index(
        op.f("ix_knowledge_points_canonical_key"),
        "knowledge_points",
        ["canonical_key"],
        unique=True,
    )

    op.create_table(
        "chinese_characters",
        sa.Column("knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column("character", sa.String(length=8), nullable=False),
        sa.Column("pinyin", sa.String(length=120), nullable=False),
        sa.Column("stroke_count", sa.Integer(), nullable=True),
        sa.Column("radical", sa.String(length=16), nullable=True),
        sa.Column("frequency_rank", sa.Integer(), nullable=True),
        sa.Column("difficulty_level", sa.Integer(), nullable=True),
        sa.Column("simple_meaning", sa.Text(), nullable=True),
        sa.Column("example_sentence", sa.Text(), nullable=True),
        sa.Column("common_words", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "stroke_count IS NULL OR stroke_count > 0", name="ck_chinese_characters_strokes"
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("knowledge_point_id"),
    )
    op.create_index(
        op.f("ix_chinese_characters_character"), "chinese_characters", ["character"], unique=True
    )
    op.create_index(op.f("ix_chinese_characters_pinyin"), "chinese_characters", ["pinyin"])

    op.create_table(
        "knowledge_relations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("relation_type", sa.String(length=24), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("source_id <> target_id", name="ck_knowledge_relations_not_self"),
        sa.CheckConstraint(
            "relation_type IN ('related', 'prerequisite', 'confusing', 'derived')",
            name="ck_knowledge_relations_type",
        ),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_points.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["target_id"], ["knowledge_points.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id", "target_id", "relation_type", name="uq_knowledge_relation_edge"
        ),
    )
    op.create_index(op.f("ix_knowledge_relations_source_id"), "knowledge_relations", ["source_id"])
    op.create_index(op.f("ix_knowledge_relations_target_id"), "knowledge_relations", ["target_id"])


def downgrade() -> None:
    op.drop_table("knowledge_relations")
    op.drop_table("chinese_characters")
    op.drop_table("knowledge_points")
