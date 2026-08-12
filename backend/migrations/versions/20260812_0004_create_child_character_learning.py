"""Create append-oriented child character learning tables.

Revision ID: 20260812_0004
Revises: 20260812_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0004"
down_revision: str | None = "20260812_0003"
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
        "learning_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="in_progress", nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('in_progress', 'completed', 'abandoned')",
            name="ck_learning_sessions_status",
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_learning_sessions_actor_user_id"), "learning_sessions", ["actor_user_id"]
    )
    op.create_index(op.f("ix_learning_sessions_child_id"), "learning_sessions", ["child_id"])

    op.create_table(
        "learning_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("activity_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column(
            "learned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        *_timestamps(),
        sa.CheckConstraint(
            "activity_type IN ('introduced', 'relearned', 'parent_marked_seen')",
            name="ck_learning_records_activity_type",
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["session_id"], ["learning_sessions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id", "knowledge_point_id", name="uq_learning_record_session_point"
        ),
    )
    for column in ("actor_user_id", "child_id", "knowledge_point_id", "session_id"):
        op.create_index(op.f(f"ix_learning_records_{column}"), "learning_records", [column])

    op.create_table(
        "assessment_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("evaluator_user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="in_progress", nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('in_progress', 'completed', 'abandoned')",
            name="ck_assessment_sessions_status",
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evaluator_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_assessment_sessions_child_id"), "assessment_sessions", ["child_id"])
    op.create_index(
        op.f("ix_assessment_sessions_evaluator_user_id"),
        "assessment_sessions",
        ["evaluator_user_id"],
    )

    op.create_table(
        "assessment_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column("evaluator_user_id", sa.Uuid(), nullable=False),
        sa.Column("outcome", sa.String(length=24), nullable=False),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("hint_used", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "assessed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        *_timestamps(),
        sa.CheckConstraint(
            "outcome IN ('correct', 'hinted_correct', 'uncertain', 'incorrect')",
            name="ck_assessment_items_outcome",
        ),
        sa.CheckConstraint(
            "response_time_ms IS NULL OR response_time_ms >= 0",
            name="ck_assessment_items_response_time",
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evaluator_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["session_id"], ["assessment_sessions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id", "knowledge_point_id", name="uq_assessment_item_session_point"
        ),
    )
    for column in ("child_id", "evaluator_user_id", "knowledge_point_id", "session_id"):
        op.create_index(op.f(f"ix_assessment_items_{column}"), "assessment_items", [column])

    op.create_table(
        "child_knowledge_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column(
            "mastery_level", sa.String(length=20), server_default="unlearned", nullable=False
        ),
        sa.Column("mastery_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("first_introduced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_learning_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_assessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correct_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("hinted_correct_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("uncertain_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("incorrect_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("consecutive_correct", sa.Integer(), server_default="0", nullable=False),
        sa.Column("consecutive_incorrect", sa.Integer(), server_default="0", nullable=False),
        sa.Column("average_response_time_ms", sa.Float(), nullable=True),
        sa.Column("is_priority", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("algorithm_version", sa.String(length=20), server_default="v1", nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "mastery_level IN ('unlearned', 'introduced', 'recognizing', 'proficient', 'stable')",
            name="ck_child_knowledge_states_level",
        ),
        sa.CheckConstraint(
            "mastery_score >= 0 AND mastery_score <= 1",
            name="ck_child_knowledge_states_score",
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "child_id", "knowledge_point_id", name="uq_child_knowledge_state_child_point"
        ),
    )
    op.create_index(
        op.f("ix_child_knowledge_states_child_id"), "child_knowledge_states", ["child_id"]
    )
    op.create_index(
        op.f("ix_child_knowledge_states_knowledge_point_id"),
        "child_knowledge_states",
        ["knowledge_point_id"],
    )


def downgrade() -> None:
    op.drop_table("child_knowledge_states")
    op.drop_table("assessment_items")
    op.drop_table("assessment_sessions")
    op.drop_table("learning_records")
    op.drop_table("learning_sessions")
