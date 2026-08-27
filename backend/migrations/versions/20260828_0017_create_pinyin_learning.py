"""Create the versioned Pinyin learning catalog.

Revision ID: 20260828_0017
Revises: 20260827_0016
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260828_0017"
down_revision: str | None = "20260827_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pinyin_catalog_releases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("catalog_version", sa.String(length=80), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=False),
        sa.Column("source_reference", sa.String(length=500)),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("practice_item_count", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("catalog_version"),
    )
    op.create_index(
        op.f("ix_pinyin_catalog_releases_catalog_version"),
        "pinyin_catalog_releases",
        ["catalog_version"],
    )

    op.create_table(
        "pinyin_items",
        sa.Column("knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("subcategory", sa.String(length=40), nullable=False),
        sa.Column("display_text", sa.String(length=32), nullable=False),
        sa.Column("pronunciation_cue", sa.String(length=160)),
        sa.Column("example_text", sa.String(length=120)),
        sa.Column("example_pinyin", sa.String(length=160)),
        sa.Column("description", sa.Text()),
        sa.Column("parent_tip", sa.Text()),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("audio_key", sa.String(length=255)),
        sa.Column("catalog_version", sa.String(length=80), nullable=False),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "kind IN ('initial', 'final', 'tone', 'whole')",
            name="ck_pinyin_items_kind",
        ),
        sa.CheckConstraint("order_index >= 0", name="ck_pinyin_items_order"),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("knowledge_point_id"),
        sa.UniqueConstraint("order_index"),
        sa.UniqueConstraint("symbol"),
    )
    op.create_index(op.f("ix_pinyin_items_symbol"), "pinyin_items", ["symbol"])
    op.create_index(op.f("ix_pinyin_items_kind"), "pinyin_items", ["kind"])
    op.create_index(op.f("ix_pinyin_items_subcategory"), "pinyin_items", ["subcategory"])
    op.create_index(op.f("ix_pinyin_items_order_index"), "pinyin_items", ["order_index"])
    op.create_index(op.f("ix_pinyin_items_catalog_version"), "pinyin_items", ["catalog_version"])

    op.create_table(
        "pinyin_practice_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("practice_key", sa.String(length=120), nullable=False),
        sa.Column("initial_knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column("final_knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column("display_syllable", sa.String(length=32), nullable=False),
        sa.Column("underlying_final", sa.String(length=32), nullable=False),
        sa.Column("display_final", sa.String(length=32), nullable=False),
        sa.Column("pronunciation_cue", sa.String(length=160), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("catalog_version", sa.String(length=80), nullable=False),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("order_index >= 0", name="ck_pinyin_practice_items_order"),
        sa.ForeignKeyConstraint(
            ["initial_knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["final_knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "initial_knowledge_point_id",
            "final_knowledge_point_id",
            "display_syllable",
            name="uq_pinyin_practice_components",
        ),
        sa.UniqueConstraint("order_index"),
        sa.UniqueConstraint("practice_key"),
    )
    op.create_index(
        op.f("ix_pinyin_practice_items_practice_key"),
        "pinyin_practice_items",
        ["practice_key"],
    )
    op.create_index(
        op.f("ix_pinyin_practice_items_initial_knowledge_point_id"),
        "pinyin_practice_items",
        ["initial_knowledge_point_id"],
    )
    op.create_index(
        op.f("ix_pinyin_practice_items_final_knowledge_point_id"),
        "pinyin_practice_items",
        ["final_knowledge_point_id"],
    )
    op.create_index(
        op.f("ix_pinyin_practice_items_order_index"),
        "pinyin_practice_items",
        ["order_index"],
    )
    op.create_index(
        op.f("ix_pinyin_practice_items_catalog_version"),
        "pinyin_practice_items",
        ["catalog_version"],
    )

    op.create_table(
        "pinyin_daily_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(length=64), server_default="Asia/Shanghai", nullable=False),
        sa.Column("new_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("review_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column(
            "algorithm_version",
            sa.String(length=30),
            server_default="pinyin-plan-v1",
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed')",
            name="ck_pinyin_daily_plans_status",
        ),
        sa.CheckConstraint(
            "new_count >= 0 AND review_count >= 0 AND completed_count >= 0",
            name="ck_pinyin_daily_plans_counts",
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("child_id", "plan_date", name="uq_pinyin_daily_plan_child_date"),
    )
    op.create_index(op.f("ix_pinyin_daily_plans_child_id"), "pinyin_daily_plans", ["child_id"])

    op.create_table(
        "pinyin_daily_plan_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pinyin_daily_plan_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column("item_kind", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "item_kind IN ('new', 'review')", name="ck_pinyin_daily_plan_items_kind"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'completed')", name="ck_pinyin_daily_plan_items_status"
        ),
        sa.CheckConstraint("position >= 0", name="ck_pinyin_daily_plan_items_position"),
        sa.ForeignKeyConstraint(
            ["pinyin_daily_plan_id"], ["pinyin_daily_plans.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "pinyin_daily_plan_id",
            "knowledge_point_id",
            name="uq_pinyin_daily_plan_item_point",
        ),
    )
    op.create_index(
        op.f("ix_pinyin_daily_plan_items_pinyin_daily_plan_id"),
        "pinyin_daily_plan_items",
        ["pinyin_daily_plan_id"],
    )
    op.create_index(
        op.f("ix_pinyin_daily_plan_items_knowledge_point_id"),
        "pinyin_daily_plan_items",
        ["knowledge_point_id"],
    )


def downgrade() -> None:
    op.drop_table("pinyin_daily_plan_items")
    op.drop_table("pinyin_daily_plans")
    op.drop_table("pinyin_practice_items")
    op.drop_table("pinyin_items")
    op.drop_table("pinyin_catalog_releases")
