"""Create adaptive review, daily plan, periodic assessment, and literacy tables.

Revision ID: 20260813_0005
Revises: 20260812_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0005"
down_revision: str | None = "20260812_0004"
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


def upgrade() -> None:
    op.create_table(
        "child_learning_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("max_new_characters_per_day", sa.Integer(), server_default="5", nullable=False),
        sa.Column("daily_review_capacity", sa.Integer(), server_default="15", nullable=False),
        sa.Column(
            "weekly_assessment_enabled", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.Column(
            "monthly_assessment_enabled", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.Column("timezone", sa.String(length=64), server_default="Asia/Shanghai", nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "max_new_characters_per_day >= 0 AND max_new_characters_per_day <= 20",
            name="ck_child_learning_settings_max_new",
        ),
        sa.CheckConstraint(
            "daily_review_capacity >= 1 AND daily_review_capacity <= 100",
            name="ck_child_learning_settings_review_capacity",
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("child_id", name="uq_child_learning_settings_child"),
    )
    op.create_index(
        op.f("ix_child_learning_settings_child_id"),
        "child_learning_settings",
        ["child_id"],
        unique=True,
    )

    op.create_table(
        "child_review_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column("last_review_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("interval_stage", sa.Integer(), nullable=False),
        sa.Column("last_outcome", sa.String(length=32), nullable=False),
        sa.Column("scheduling_reason", sa.String(length=80), nullable=False),
        sa.Column(
            "algorithm_version", sa.String(length=20), server_default="review-v1", nullable=False
        ),
        *_timestamps(),
        sa.CheckConstraint("interval_days >= 1", name="ck_child_review_schedules_interval_days"),
        sa.CheckConstraint("interval_stage >= 0", name="ck_child_review_schedules_interval_stage"),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "child_id", "knowledge_point_id", name="uq_child_review_schedule_child_point"
        ),
    )
    for column in ("child_id", "knowledge_point_id", "next_review_at"):
        op.create_index(
            op.f(f"ix_child_review_schedules_{column}"), "child_review_schedules", [column]
        )

    op.create_table(
        "daily_learning_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("recommended_new_count", sa.Integer(), nullable=False),
        sa.Column("review_count", sa.Integer(), nullable=False),
        sa.Column("due_count", sa.Integer(), nullable=False),
        sa.Column("estimated_backlog_days", sa.Integer(), nullable=False),
        sa.Column("recommendation_reason", sa.Text(), nullable=False),
        sa.Column("new_completed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("review_completed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column(
            "algorithm_version", sa.String(length=20), server_default="plan-v1", nullable=False
        ),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed')",
            name="ck_daily_learning_plans_status",
        ),
        sa.CheckConstraint(
            "recommended_new_count >= 0 AND review_count >= 0 AND due_count >= 0",
            name="ck_daily_learning_plans_counts",
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("child_id", "plan_date", name="uq_daily_learning_plan_child_date"),
    )
    op.create_index(op.f("ix_daily_learning_plans_child_id"), "daily_learning_plans", ["child_id"])

    op.create_table(
        "daily_plan_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("daily_plan_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column("item_kind", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("selection_reason", sa.String(length=80), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("item_kind IN ('new', 'review')", name="ck_daily_plan_items_kind"),
        sa.CheckConstraint("status IN ('pending', 'completed')", name="ck_daily_plan_items_status"),
        sa.CheckConstraint("position >= 0", name="ck_daily_plan_items_position"),
        sa.ForeignKeyConstraint(
            ["daily_plan_id"], ["daily_learning_plans.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "daily_plan_id", "knowledge_point_id", "item_kind", name="uq_daily_plan_item_point_kind"
        ),
    )
    op.create_index(
        op.f("ix_daily_plan_items_daily_plan_id"), "daily_plan_items", ["daily_plan_id"]
    )
    op.create_index(
        op.f("ix_daily_plan_items_knowledge_point_id"), "daily_plan_items", ["knowledge_point_id"]
    )

    op.create_table(
        "assessment_session_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assessment_session_id", sa.Uuid(), nullable=False),
        sa.Column("daily_plan_id", sa.Uuid(), nullable=True),
        sa.Column("sampling_method", sa.String(length=60), nullable=False),
        sa.Column("sampling_version", sa.String(length=20), nullable=False),
        sa.Column("eligible_catalog_size", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["assessment_session_id"], ["assessment_sessions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["daily_plan_id"], ["daily_learning_plans.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_session_id", name="uq_assessment_session_plan_session"),
    )
    op.create_index(
        op.f("ix_assessment_session_plans_assessment_session_id"),
        "assessment_session_plans",
        ["assessment_session_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_assessment_session_plans_daily_plan_id"),
        "assessment_session_plans",
        ["daily_plan_id"],
    )

    op.create_table(
        "assessment_session_targets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assessment_session_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("sampling_class", sa.String(length=40), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("position >= 0", name="ck_assessment_session_targets_position"),
        sa.ForeignKeyConstraint(
            ["assessment_session_id"], ["assessment_sessions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assessment_session_id",
            "knowledge_point_id",
            name="uq_assessment_session_target_point",
        ),
    )
    op.create_index(
        op.f("ix_assessment_session_targets_assessment_session_id"),
        "assessment_session_targets",
        ["assessment_session_id"],
    )
    op.create_index(
        op.f("ix_assessment_session_targets_knowledge_point_id"),
        "assessment_session_targets",
        ["knowledge_point_id"],
    )

    op.create_table(
        "literacy_estimates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_session_id", sa.Uuid(), nullable=False),
        sa.Column("catalog_size", sa.Integer(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("known_count", sa.Integer(), nullable=False),
        sa.Column("unknown_count", sa.Integer(), nullable=False),
        sa.Column("sampling_method", sa.String(length=60), nullable=False),
        sa.Column("sampling_version", sa.String(length=20), nullable=False),
        sa.Column("estimate", sa.Float(), nullable=True),
        sa.Column("lower_bound", sa.Float(), nullable=True),
        sa.Column("upper_bound", sa.Float(), nullable=True),
        sa.Column("is_sufficient", sa.Boolean(), nullable=False),
        sa.Column(
            "estimation_version", sa.String(length=20), server_default="literacy-v1", nullable=False
        ),
        *_timestamps(),
        sa.CheckConstraint(
            "catalog_size >= 0 AND sample_size >= 0 AND known_count >= 0 AND unknown_count >= 0",
            name="ck_literacy_estimates_counts",
        ),
        sa.CheckConstraint(
            "estimate IS NULL OR (estimate >= 0 AND estimate <= catalog_size)",
            name="ck_literacy_estimates_value",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_session_id"], ["assessment_sessions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_session_id", name="uq_literacy_estimate_session"),
    )
    op.create_index(op.f("ix_literacy_estimates_child_id"), "literacy_estimates", ["child_id"])
    op.create_index(
        op.f("ix_literacy_estimates_assessment_session_id"),
        "literacy_estimates",
        ["assessment_session_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("literacy_estimates")
    op.drop_table("assessment_session_targets")
    op.drop_table("assessment_session_plans")
    op.drop_table("daily_plan_items")
    op.drop_table("daily_learning_plans")
    op.drop_table("child_review_schedules")
    op.drop_table("child_learning_settings")
