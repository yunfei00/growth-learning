"""Add privacy-minimal speech review evidence and parent overrides.

Revision ID: 20260830_0021
Revises: 20260830_0020
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_0021"
down_revision: str | None = "20260830_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chinese_characters",
        sa.Column(
            "accepted_readings", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False
        ),
    )
    # These are deliberately curated context readings, not every dictionary reading.
    op.execute(
        "UPDATE chinese_characters SET accepted_readings='[\"hang2\"]'::json WHERE character='行'"
    )
    op.execute(
        "UPDATE chinese_characters SET accepted_readings='[\"zhang3\"]'::json WHERE character='长'"
    )
    op.execute(
        "UPDATE chinese_characters SET accepted_readings='[\"yue4\"]'::json WHERE character='乐'"
    )
    op.execute(
        "UPDATE chinese_characters SET accepted_readings='[\"chong2\"]'::json WHERE character='重'"
    )

    op.add_column(
        "child_learning_settings",
        sa.Column(
            "character_review_mode",
            sa.String(24),
            server_default="parent_manual",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_child_learning_settings_character_review_mode",
        "child_learning_settings",
        "character_review_mode IN ('parent_manual', 'speech_auto')",
    )

    op.add_column(
        "assessment_session_targets",
        sa.Column("hint_requested_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "character_speech_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_session_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_index", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("transcript", sa.Text()),
        sa.Column(
            "alternatives_json", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False
        ),
        sa.Column("confidence", sa.Float()),
        sa.Column("confidence_available", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "normalized_readings_json",
            sa.JSON(),
            server_default=sa.text("'[]'::json"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("syllable_match", sa.Boolean()),
        sa.Column("tone_match", sa.Boolean()),
        sa.Column("tone_evaluation", sa.String(20), server_default="unavailable", nullable=False),
        sa.Column("explicit_unknown", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("hint_used", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column(
            "provider_metadata", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("attempt_index >= 1", name="ck_character_speech_attempts_index"),
        sa.CheckConstraint(
            "decision IN ('match', 'partial_match', 'uncertain', 'no_match', "
            "'no_speech', 'recognition_error')",
            name="ck_character_speech_attempts_decision",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_character_speech_attempts_duration",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_character_speech_attempts_confidence",
        ),
        sa.CheckConstraint(
            "tone_evaluation IN ('matched', 'mismatched', 'unavailable')",
            name="ck_character_speech_attempts_tone_evaluation",
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
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
            "attempt_index",
            name="uq_character_speech_attempt_session_point_index",
        ),
    )
    for column in ("child_id", "assessment_session_id", "knowledge_point_id"):
        op.create_index(
            op.f(f"ix_character_speech_attempts_{column}"),
            "character_speech_attempts",
            [column],
        )

    op.create_table(
        "assessment_overrides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assessment_item_id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("original_outcome", sa.String(24), nullable=False),
        sa.Column("override_outcome", sa.String(24), nullable=False),
        sa.Column("overridden_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("override_reason", sa.String(500), nullable=False),
        sa.Column(
            "overridden_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "original_outcome IN ('correct', 'hinted_correct', 'uncertain', 'incorrect')",
            name="ck_assessment_overrides_original",
        ),
        sa.CheckConstraint(
            "override_outcome IN ('correct', 'hinted_correct', 'uncertain', 'incorrect')",
            name="ck_assessment_overrides_override",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_item_id"], ["assessment_items.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["overridden_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("assessment_item_id", "child_id", "overridden_by_user_id"):
        op.create_index(op.f(f"ix_assessment_overrides_{column}"), "assessment_overrides", [column])


def downgrade() -> None:
    op.drop_index(
        op.f("ix_assessment_overrides_overridden_by_user_id"), table_name="assessment_overrides"
    )
    op.drop_index(op.f("ix_assessment_overrides_child_id"), table_name="assessment_overrides")
    op.drop_index(
        op.f("ix_assessment_overrides_assessment_item_id"), table_name="assessment_overrides"
    )
    op.drop_table("assessment_overrides")
    op.drop_index(
        op.f("ix_character_speech_attempts_knowledge_point_id"),
        table_name="character_speech_attempts",
    )
    op.drop_index(
        op.f("ix_character_speech_attempts_assessment_session_id"),
        table_name="character_speech_attempts",
    )
    op.drop_index(
        op.f("ix_character_speech_attempts_child_id"), table_name="character_speech_attempts"
    )
    op.drop_table("character_speech_attempts")
    op.drop_column("assessment_session_targets", "hint_requested_at")
    op.drop_constraint(
        "ck_child_learning_settings_character_review_mode",
        "child_learning_settings",
        type_="check",
    )
    op.drop_column("child_learning_settings", "character_review_mode")
    op.drop_column("chinese_characters", "accepted_readings")
