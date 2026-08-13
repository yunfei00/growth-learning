"""Create immutable stories, reading evidence, and daily reading tasks.

Revision ID: 20260813_0006
Revises: 20260813_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0006"
down_revision: str | None = "20260813_0005"
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


def _index(table: str, column: str, *, unique: bool = False) -> None:
    op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=unique)


def upgrade() -> None:
    # Extend append-only learning evidence without rewriting any existing row.
    with op.batch_alter_table("learning_records") as batch:
        batch.drop_constraint("ck_learning_records_activity_type", type_="check")
        batch.create_check_constraint(
            "ck_learning_records_activity_type",
            "activity_type IN ('introduced', 'relearned', 'parent_marked_seen', 'story_exposure')",
        )

    op.create_table(
        "stories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("theme", sa.String(length=40), nullable=False),
        sa.Column("custom_theme", sa.String(length=80), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    _index("stories", "child_id")
    _index("stories", "created_by_user_id")

    op.create_table(
        "story_generation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("story_id", sa.Uuid(), nullable=True),
        sa.Column("story_version_id", sa.Uuid(), nullable=True),
        sa.Column("request_key", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("theme", sa.String(length=40), nullable=False),
        sa.Column("target_knowledge_point_ids", sa.JSON(), nullable=False),
        sa.Column("provider", sa.String(length=60), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=30), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("failure_category", sa.String(length=60), nullable=True),
        sa.Column("failure_message", sa.String(length=240), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed')",
            name="ck_story_generation_runs_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= 3", name="ck_story_runs_attempts"
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("child_id", "request_key", name="uq_story_run_child_request_key"),
    )
    for column in ("child_id", "requested_by_user_id", "story_id", "story_version_id"):
        _index("story_generation_runs", column)

    op.create_table(
        "story_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("story_id", sa.Uuid(), nullable=False),
        sa.Column("generation_run_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("paragraphs", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("theme", sa.String(length=40), nullable=False),
        sa.Column("custom_theme", sa.String(length=80), nullable=True),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("requested_known_coverage", sa.Float(), nullable=False),
        sa.Column("actual_strong_known_coverage", sa.Float(), nullable=False),
        sa.Column("actual_usable_known_coverage", sa.Float(), nullable=False),
        sa.Column("actual_target_coverage", sa.Float(), nullable=False),
        sa.Column("actual_unexpected_coverage", sa.Float(), nullable=False),
        sa.Column("unique_known_coverage", sa.Float(), nullable=False),
        sa.Column("total_han_occurrences", sa.Integer(), nullable=False),
        sa.Column("unique_han_count", sa.Integer(), nullable=False),
        sa.Column("unexpected_characters", sa.JSON(), nullable=False),
        sa.Column("target_characters", sa.JSON(), nullable=False),
        sa.Column("mastery_snapshot", sa.JSON(), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("coverage_policy_version", sa.String(length=30), nullable=False),
        sa.Column("analyzer_version", sa.String(length=30), nullable=False),
        sa.Column("prompt_version", sa.String(length=30), nullable=False),
        sa.Column("provider", sa.String(length=60), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("version_number >= 1", name="ck_story_versions_number"),
        sa.CheckConstraint(
            "difficulty IN ('beginner', 'normal', 'challenge')",
            name="ck_story_versions_difficulty",
        ),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["generation_run_id"], ["story_generation_runs.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("generation_run_id"),
        sa.UniqueConstraint("story_id", "version_number", name="uq_story_versions_story_number"),
    )
    _index("story_versions", "story_id")
    _index("story_versions", "generation_run_id", unique=True)

    op.create_table(
        "story_knowledge_points",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("story_version_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False),
        sa.Column("mastery_level_at_generation", sa.String(length=20), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "role IN ('strong_known', 'usable_recognizing', 'target', 'unexpected')",
            name="ck_story_knowledge_points_role",
        ),
        sa.CheckConstraint("occurrence_count >= 0", name="ck_story_knowledge_occurrences"),
        sa.ForeignKeyConstraint(["story_version_id"], ["story_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "story_version_id", "knowledge_point_id", name="uq_story_knowledge_version_point"
        ),
    )
    _index("story_knowledge_points", "story_version_id")
    _index("story_knowledge_points", "knowledge_point_id")

    op.create_table(
        "reading_questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("story_version_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("question", sa.String(length=240), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("correct_option_index", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("position >= 0", name="ck_reading_questions_position"),
        sa.CheckConstraint("correct_option_index >= 0", name="ck_reading_questions_answer"),
        sa.ForeignKeyConstraint(["story_version_id"], ["story_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("story_version_id", "position", name="uq_reading_questions_position"),
    )
    _index("reading_questions", "story_version_id")

    op.create_table(
        "reading_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("story_version_id", sa.Uuid(), nullable=False),
        sa.Column("evaluator_user_id", sa.Uuid(), nullable=False),
        sa.Column("reading_mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="in_progress", nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("parent_note", sa.Text(), nullable=True),
        sa.Column("exposure_learning_session_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('in_progress', 'completed', 'abandoned')",
            name="ck_reading_sessions_status",
        ),
        sa.CheckConstraint(
            "reading_mode IN ('independent', 'with_help')", name="ck_reading_sessions_mode"
        ),
        sa.CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_reading_sessions_duration",
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["story_version_id"], ["story_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evaluator_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["exposure_learning_session_id"], ["learning_sessions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exposure_learning_session_id"),
        sa.UniqueConstraint(
            "child_id", "story_version_id", name="uq_reading_session_child_version"
        ),
    )
    for column in ("child_id", "story_version_id", "evaluator_user_id"):
        _index("reading_sessions", column)

    op.create_table(
        "reading_answers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reading_session_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("evaluator_user_id", sa.Uuid(), nullable=False),
        sa.Column("selected_option_index", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column(
            "answered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        *_timestamps(),
        sa.CheckConstraint(
            "outcome IN ('correct', 'with_help', 'partial', 'incorrect')",
            name="ck_reading_answers_outcome",
        ),
        sa.CheckConstraint("selected_option_index >= 0", name="ck_reading_answers_selected"),
        sa.ForeignKeyConstraint(
            ["reading_session_id"], ["reading_sessions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["question_id"], ["reading_questions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evaluator_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reading_session_id", "question_id", name="uq_reading_answer_session_q"
        ),
    )
    for column in ("reading_session_id", "question_id", "evaluator_user_id"):
        _index("reading_answers", column)

    op.create_table(
        "daily_reading_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("daily_plan_id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("task_date", sa.Date(), nullable=False),
        sa.Column("story_version_id", sa.Uuid(), nullable=True),
        sa.Column("reading_session_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="needs_story", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('needs_story', 'pending', 'in_progress', 'completed')",
            name="ck_daily_reading_tasks_status",
        ),
        sa.ForeignKeyConstraint(
            ["daily_plan_id"], ["daily_learning_plans.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["story_version_id"], ["story_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["reading_session_id"], ["reading_sessions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("daily_plan_id", name="uq_daily_reading_task_plan"),
    )
    _index("daily_reading_tasks", "daily_plan_id", unique=True)
    for column in ("child_id", "story_version_id", "reading_session_id"):
        _index("daily_reading_tasks", column)


def downgrade() -> None:
    op.drop_table("daily_reading_tasks")
    op.drop_table("reading_answers")
    op.drop_table("reading_sessions")
    op.drop_table("reading_questions")
    op.drop_table("story_knowledge_points")
    op.drop_table("story_versions")
    op.drop_table("story_generation_runs")
    op.drop_table("stories")
    with op.batch_alter_table("learning_records") as batch:
        batch.drop_constraint("ck_learning_records_activity_type", type_="check")
        batch.create_check_constraint(
            "ck_learning_records_activity_type",
            "activity_type IN ('introduced', 'relearned', 'parent_marked_seen')",
        )
