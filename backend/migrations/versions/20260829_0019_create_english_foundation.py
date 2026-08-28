"""Create the child-friendly English Foundation V1 tables.

Revision ID: 20260829_0019
Revises: 20260828_0018
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260829_0019"
down_revision: str | None = "20260828_0018"
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


def _knowledge_type_constraint(*, include_phrase: bool) -> str:
    english = "'english_letter', 'english_word', 'english_phonics'"
    if include_phrase:
        english += ", 'english_phrase'"
    return (
        "type IN ('chinese_character', 'pinyin_initial', 'pinyin_final', "
        "'pinyin_tone', 'pinyin_syllable', 'math_skill', "
        f"{english}, 'science_concept')"
    )


def _knowledge_subject_constraint(*, include_phrase: bool) -> str:
    english = "'english_letter', 'english_word', 'english_phonics'"
    if include_phrase:
        english += ", 'english_phrase'"
    return (
        "(type IN ('chinese_character', 'pinyin_initial', 'pinyin_final', "
        "'pinyin_tone', 'pinyin_syllable') AND subject = 'chinese') OR "
        "(type = 'math_skill' AND subject = 'math') OR "
        f"(type IN ({english}) AND subject = 'english') OR "
        "(type = 'science_concept' AND subject = 'science')"
    )


def upgrade() -> None:
    op.drop_constraint("ck_knowledge_points_type_subject", "knowledge_points", type_="check")
    op.drop_constraint("ck_knowledge_points_type", "knowledge_points", type_="check")
    op.create_check_constraint(
        "ck_knowledge_points_type",
        "knowledge_points",
        _knowledge_type_constraint(include_phrase=True),
    )
    op.create_check_constraint(
        "ck_knowledge_points_type_subject",
        "knowledge_points",
        _knowledge_subject_constraint(include_phrase=True),
    )

    op.create_table(
        "english_catalog_releases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("catalog_version", sa.String(length=80), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=False),
        sa.Column("source_reference", sa.String(length=500)),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("practice_item_count", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("catalog_version"),
    )
    op.create_index(
        op.f("ix_english_catalog_releases_catalog_version"),
        "english_catalog_releases",
        ["catalog_version"],
    )

    op.create_table(
        "english_items",
        sa.Column("knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("text", sa.String(length=160), nullable=False),
        sa.Column("normalized_text", sa.String(length=160), nullable=False),
        sa.Column("meaning_zh", sa.String(length=240), nullable=False),
        sa.Column("child_hint_zh", sa.Text(), nullable=False),
        sa.Column("parent_tip", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("example_text", sa.String(length=240)),
        sa.Column("example_meaning_zh", sa.String(length=240)),
        sa.Column("image_key", sa.String(length=255)),
        sa.Column("visual_key", sa.String(length=160)),
        sa.Column(
            "visual_type", sa.String(length=30), server_default="emoji_fallback", nullable=False
        ),
        sa.Column("audio_key", sa.String(length=255)),
        sa.Column("audio_accent", sa.String(length=20), server_default="en-US", nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("catalog_version", sa.String(length=80), nullable=False),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "kind IN ('letter', 'word', 'phonics', 'phrase')",
            name="ck_english_items_kind",
        ),
        sa.CheckConstraint(
            "visual_type IN ('static_image', 'icon', 'color_swatch', 'shape', 'emoji_fallback')",
            name="ck_english_items_visual_type",
        ),
        sa.CheckConstraint("order_index >= 0", name="ck_english_items_order"),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("knowledge_point_id"),
        sa.UniqueConstraint("order_index"),
    )
    for column in ("kind", "text", "normalized_text", "category", "order_index", "catalog_version"):
        op.create_index(op.f(f"ix_english_items_{column}"), "english_items", [column])

    op.create_table(
        "english_practice_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column("template_key", sa.String(length=180), nullable=False),
        sa.Column("practice_kind", sa.String(length=40), nullable=False),
        sa.Column("generator_version", sa.String(length=60), nullable=False),
        sa.Column("config_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "practice_kind IN ('listen_choose_visual', 'visual_choose_audio', "
            "'letter_match', 'case_match', 'phonics_choose', 'blending', "
            "'phrase_listening')",
            name="ck_english_practice_items_kind",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived')", name="ck_english_practice_items_status"
        ),
        sa.CheckConstraint("order_index >= 0", name="ck_english_practice_items_order"),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_key"),
        sa.UniqueConstraint(
            "knowledge_point_id", "order_index", name="uq_english_practice_item_order"
        ),
    )
    for column in ("knowledge_point_id", "template_key", "practice_kind"):
        op.create_index(
            op.f(f"ix_english_practice_items_{column}"), "english_practice_items", [column]
        )

    op.create_table(
        "english_exercise_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("practice_item_id", sa.Uuid(), nullable=False),
        sa.Column("template_key", sa.String(length=180), nullable=False),
        sa.Column("practice_kind", sa.String(length=40), nullable=False),
        sa.Column("generator_version", sa.String(length=60), nullable=False),
        sa.Column("seed", sa.Integer()),
        sa.Column("prompt_snapshot", sa.JSON(), nullable=False),
        sa.Column("options_snapshot", sa.JSON(), nullable=False),
        sa.Column("expected_answer", sa.JSON(), nullable=False),
        sa.Column("submitted_answer", sa.JSON()),
        sa.Column("first_answer", sa.JSON()),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("hint_used", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("audio_replay_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("outcome", sa.String(length=24)),
        sa.Column("evidence_dimension", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True)),
        sa.Column("response_time_ms", sa.Integer()),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("evaluator_user_id", sa.Uuid()),
        *_timestamps(),
        sa.CheckConstraint("mode IN ('practice', 'assessment')", name="ck_english_attempts_mode"),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('correct', 'hinted_correct', 'uncertain', 'incorrect')",
            name="ck_english_attempts_outcome",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_english_attempts_count"),
        sa.CheckConstraint(
            "response_time_ms IS NULL OR response_time_ms >= 0",
            name="ck_english_attempts_response_time",
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["practice_item_id"], ["english_practice_items.id"], ondelete="RESTRICT"
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
        "practice_item_id",
        "actor_user_id",
        "evaluator_user_id",
    ):
        op.create_index(
            op.f(f"ix_english_exercise_attempts_{column}"),
            "english_exercise_attempts",
            [column],
        )

    op.create_table(
        "english_daily_plans",
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
            server_default="english-plan-v1",
            nullable=False,
        ),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed')",
            name="ck_english_daily_plans_status",
        ),
        sa.CheckConstraint(
            "new_count >= 0 AND review_count >= 0 AND completed_count >= 0",
            name="ck_english_daily_plans_counts",
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("child_id", "plan_date", name="uq_english_daily_plan_child_date"),
    )
    op.create_index(op.f("ix_english_daily_plans_child_id"), "english_daily_plans", ["child_id"])

    op.create_table(
        "english_daily_plan_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("english_daily_plan_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column("item_kind", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("exercise_count", sa.Integer(), server_default="3", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.CheckConstraint(
            "item_kind IN ('new', 'review')", name="ck_english_daily_plan_items_kind"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'completed')", name="ck_english_daily_plan_items_status"
        ),
        sa.CheckConstraint("position >= 0", name="ck_english_daily_plan_items_position"),
        sa.ForeignKeyConstraint(
            ["english_daily_plan_id"], ["english_daily_plans.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "english_daily_plan_id",
            "knowledge_point_id",
            name="uq_english_daily_plan_item_point",
        ),
    )
    op.create_index(
        op.f("ix_english_daily_plan_items_english_daily_plan_id"),
        "english_daily_plan_items",
        ["english_daily_plan_id"],
    )
    op.create_index(
        op.f("ix_english_daily_plan_items_knowledge_point_id"),
        "english_daily_plan_items",
        ["knowledge_point_id"],
    )


def downgrade() -> None:
    op.drop_table("english_daily_plan_items")
    op.drop_table("english_daily_plans")
    op.drop_table("english_exercise_attempts")
    op.drop_table("english_practice_items")
    op.drop_table("english_items")
    op.drop_table("english_catalog_releases")
    op.drop_constraint("ck_knowledge_points_type_subject", "knowledge_points", type_="check")
    op.drop_constraint("ck_knowledge_points_type", "knowledge_points", type_="check")
    op.create_check_constraint(
        "ck_knowledge_points_type",
        "knowledge_points",
        _knowledge_type_constraint(include_phrase=False),
    )
    op.create_check_constraint(
        "ck_knowledge_points_type_subject",
        "knowledge_points",
        _knowledge_subject_constraint(include_phrase=False),
    )
