"""Create the child-friendly Math Foundation V1 tables.

Revision ID: 20260828_0018
Revises: 20260828_0017
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260828_0018"
down_revision: str | None = "20260828_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def upgrade() -> None:
    op.create_table(
        "math_catalog_releases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("catalog_version", sa.String(length=80), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=False),
        sa.Column("source_reference", sa.String(length=500)),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("template_count", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("catalog_version"),
    )
    op.create_index(
        op.f("ix_math_catalog_releases_catalog_version"),
        "math_catalog_releases",
        ["catalog_version"],
    )

    op.create_table(
        "math_skills",
        sa.Column("knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column("domain", sa.String(length=40), nullable=False),
        sa.Column("skill_code", sa.String(length=120), nullable=False),
        sa.Column("difficulty_level", sa.Integer(), nullable=False),
        sa.Column("recommended_age_min", sa.Integer()),
        sa.Column("recommended_age_max", sa.Integer()),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("child_instruction", sa.Text(), nullable=False),
        sa.Column("parent_tip", sa.Text(), nullable=False),
        sa.Column(
            "representation_types", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False
        ),
        sa.Column("generator_key", sa.String(length=100)),
        sa.Column("settings_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("catalog_version", sa.String(length=80), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "domain IN ('classification', 'quantity', 'number_symbol', 'comparison', "
            "'sequence', 'composition', 'operation', 'pattern', 'geometry', 'spatial', "
            "'measurement')",
            name="ck_math_skills_domain",
        ),
        sa.CheckConstraint("difficulty_level >= 1", name="ck_math_skills_difficulty"),
        sa.CheckConstraint("order_index >= 0", name="ck_math_skills_order"),
        sa.CheckConstraint(
            "recommended_age_min IS NULL OR recommended_age_max IS NULL OR "
            "recommended_age_min <= recommended_age_max",
            name="ck_math_skills_age_range",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("knowledge_point_id"),
        sa.UniqueConstraint("skill_code"),
        sa.UniqueConstraint("order_index"),
    )
    for column in ("domain", "skill_code", "generator_key", "order_index", "catalog_version"):
        op.create_index(op.f(f"ix_math_skills_{column}"), "math_skills", [column])

    op.create_table(
        "math_problem_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column("template_key", sa.String(length=160), nullable=False),
        sa.Column("representation_type", sa.String(length=40), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("generator_version", sa.String(length=60), nullable=False),
        sa.Column("config_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("difficulty >= 1", name="ck_math_problem_templates_difficulty"),
        sa.CheckConstraint("order_index >= 0", name="ck_math_problem_templates_order"),
        sa.CheckConstraint(
            "status IN ('active', 'archived')", name="ck_math_problem_templates_status"
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_key"),
        sa.UniqueConstraint(
            "knowledge_point_id", "order_index", name="uq_math_problem_template_order"
        ),
    )
    for column in ("knowledge_point_id", "template_key", "representation_type"):
        op.create_index(
            op.f(f"ix_math_problem_templates_{column}"), "math_problem_templates", [column]
        )

    op.create_table(
        "math_exercise_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("template_key", sa.String(length=160), nullable=False),
        sa.Column("generator_version", sa.String(length=60), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("problem_snapshot", sa.JSON(), nullable=False),
        sa.Column("expected_answer", sa.JSON(), nullable=False),
        sa.Column("submitted_answer", sa.JSON()),
        sa.Column("first_answer", sa.JSON()),
        sa.Column("outcome", sa.String(length=24)),
        sa.Column("hint_used", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "evidence_dimension",
            sa.String(length=40),
            server_default="understanding",
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True)),
        sa.Column("response_time_ms", sa.Integer()),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("evaluator_user_id", sa.Uuid()),
        *_timestamps(),
        sa.CheckConstraint("mode IN ('practice', 'assessment')", name="ck_math_attempts_mode"),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('correct', 'hinted_correct', 'uncertain', 'incorrect')",
            name="ck_math_attempts_outcome",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_math_attempts_attempt_count"),
        sa.CheckConstraint(
            "response_time_ms IS NULL OR response_time_ms >= 0",
            name="ck_math_attempts_response_time",
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["template_id"], ["math_problem_templates.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evaluator_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "child_id",
        "knowledge_point_id",
        "session_id",
        "mode",
        "template_id",
        "actor_user_id",
        "evaluator_user_id",
    ):
        op.create_index(
            op.f(f"ix_math_exercise_attempts_{column}"), "math_exercise_attempts", [column]
        )

    op.create_table(
        "math_daily_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(length=64), server_default="Asia/Shanghai", nullable=False),
        sa.Column("new_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("review_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column(
            "algorithm_version", sa.String(length=30), server_default="math-plan-v1", nullable=False
        ),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed')", name="ck_math_daily_plans_status"
        ),
        sa.CheckConstraint(
            "new_count >= 0 AND review_count >= 0 AND completed_count >= 0",
            name="ck_math_daily_plans_counts",
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("child_id", "plan_date", name="uq_math_daily_plan_child_date"),
    )
    op.create_index(op.f("ix_math_daily_plans_child_id"), "math_daily_plans", ["child_id"])

    op.create_table(
        "math_daily_plan_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("math_daily_plan_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column("item_kind", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("problem_count", sa.Integer(), server_default="3", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.CheckConstraint("item_kind IN ('new', 'review')", name="ck_math_daily_plan_items_kind"),
        sa.CheckConstraint(
            "status IN ('pending', 'completed')", name="ck_math_daily_plan_items_status"
        ),
        sa.CheckConstraint("position >= 0", name="ck_math_daily_plan_items_position"),
        sa.ForeignKeyConstraint(
            ["math_daily_plan_id"], ["math_daily_plans.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "math_daily_plan_id", "knowledge_point_id", name="uq_math_daily_plan_item_point"
        ),
    )
    op.create_index(
        op.f("ix_math_daily_plan_items_math_daily_plan_id"),
        "math_daily_plan_items",
        ["math_daily_plan_id"],
    )
    op.create_index(
        op.f("ix_math_daily_plan_items_knowledge_point_id"),
        "math_daily_plan_items",
        ["knowledge_point_id"],
    )


def downgrade() -> None:
    op.drop_table("math_daily_plan_items")
    op.drop_table("math_daily_plans")
    op.drop_table("math_exercise_attempts")
    op.drop_table("math_problem_templates")
    op.drop_table("math_skills")
    op.drop_table("math_catalog_releases")
