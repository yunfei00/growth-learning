"""Create the Weekend Science Lab catalog and household evidence model.

Revision ID: 20260813_0007
Revises: 20260813_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0007"
down_revision: str | None = "20260813_0006"
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
    # Preserve every existing evidence row while adding the explicit science exposure kind.
    with op.batch_alter_table("learning_records") as batch:
        batch.drop_constraint("ck_learning_records_activity_type", type_="check")
        batch.create_check_constraint(
            "ck_learning_records_activity_type",
            "activity_type IN ('introduced', 'relearned', 'parent_marked_seen', "
            "'story_exposure', 'science_experiment_exposure')",
        )

    op.create_table(
        "science_experiments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("canonical_key", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("age_min", sa.Integer(), nullable=False),
        sa.Column("age_max", sa.Integer(), nullable=True),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("estimated_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("guiding_question", sa.Text(), nullable=False),
        sa.Column("expected_phenomenon", sa.Text(), nullable=False),
        sa.Column("child_friendly_explanation", sa.Text(), nullable=False),
        sa.Column("parent_scientific_explanation", sa.Text(), nullable=False),
        sa.Column("safety_notes", sa.JSON(), nullable=False),
        sa.Column("common_failure_reasons", sa.JSON(), nullable=False),
        sa.Column("follow_up_questions", sa.JSON(), nullable=False),
        sa.Column("likely_child_questions", sa.JSON(), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("source_type", sa.String(length=20), server_default="system", nullable=False),
        sa.Column("owner_family_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("content_version", sa.Integer(), server_default="1", nullable=False),
        *_timestamps(),
        sa.CheckConstraint("age_min >= 0", name="ck_science_experiments_age_min"),
        sa.CheckConstraint(
            "age_max IS NULL OR age_max >= age_min", name="ck_science_experiments_age_range"
        ),
        sa.CheckConstraint(
            "difficulty IN ('intro', 'explore', 'advanced')",
            name="ck_science_experiments_difficulty",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'enabled', 'archived')",
            name="ck_science_experiments_status",
        ),
        sa.CheckConstraint(
            "source_type IN ('system', 'family')", name="ck_science_experiments_source"
        ),
        sa.CheckConstraint(
            "estimated_duration_minutes > 0", name="ck_science_experiments_duration"
        ),
        sa.CheckConstraint("content_version >= 1", name="ck_science_experiments_version"),
        sa.ForeignKeyConstraint(["owner_family_id"], ["families.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_key"),
    )
    for column in (
        "canonical_key",
        "title",
        "difficulty",
        "status",
        "owner_family_id",
        "created_by_user_id",
    ):
        _index("science_experiments", column)

    op.create_table(
        "science_experiment_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("version_number >= 1", name="ck_science_experiment_versions_number"),
        sa.ForeignKeyConstraint(["experiment_id"], ["science_experiments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "experiment_id", "version_number", name="uq_science_experiment_version_number"
        ),
    )
    _index("science_experiment_versions", "experiment_id")
    _index("science_experiment_versions", "created_by_user_id")

    op.create_table(
        "experiment_materials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("canonical_key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("category", sa.String(length=60), nullable=True),
        sa.Column("safety_note", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_key"),
        sa.UniqueConstraint("name"),
    )
    for column in ("canonical_key", "name", "category"):
        _index("experiment_materials", column)

    op.create_table(
        "experiment_material_requirements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("material_id", sa.Uuid(), nullable=False),
        sa.Column("quantity_text", sa.String(length=120), nullable=True),
        sa.Column("is_required", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("substitution_notes", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        *_timestamps(),
        sa.CheckConstraint("position >= 0", name="ck_experiment_material_requirement_position"),
        sa.ForeignKeyConstraint(["experiment_id"], ["science_experiments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["material_id"], ["experiment_materials.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "experiment_id", "material_id", name="uq_experiment_material_requirement"
        ),
    )
    _index("experiment_material_requirements", "experiment_id")
    _index("experiment_material_requirements", "material_id")

    op.create_table(
        "family_materials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("material_id", sa.Uuid(), nullable=False),
        sa.Column("is_owned", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("quantity_text", sa.String(length=120), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["material_id"], ["experiment_materials.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("family_id", "material_id", name="uq_family_material_inventory"),
    )
    for column in ("family_id", "material_id", "updated_by_user_id"):
        _index("family_materials", column)

    op.create_table(
        "experiment_knowledge_points",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column("exposure_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["experiment_id"], ["science_experiments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "experiment_id", "knowledge_point_id", name="uq_experiment_knowledge_point"
        ),
    )
    _index("experiment_knowledge_points", "experiment_id")
    _index("experiment_knowledge_points", "knowledge_point_id")

    op.create_table(
        "experiment_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("experiment_version_id", sa.Uuid(), nullable=False),
        sa.Column("experiment_snapshot", sa.JSON(), nullable=False),
        sa.Column("accompanying_user_id", sa.Uuid(), nullable=False),
        sa.Column("request_key", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="in_progress", nullable=False),
        sa.Column("current_step", sa.String(length=24), server_default="question", nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parent_note", sa.Text(), nullable=True),
        sa.Column("exposure_learning_session_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('planned', 'in_progress', 'completed', 'abandoned')",
            name="ck_experiment_sessions_status",
        ),
        sa.CheckConstraint(
            "current_step IN ('question', 'prediction', 'materials', 'experiment', "
            "'observation', 'explanation', 'follow_up', 'summary', 'complete')",
            name="ck_experiment_sessions_step",
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["experiment_id"], ["science_experiments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["experiment_version_id"], ["science_experiment_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["accompanying_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["exposure_learning_session_id"], ["learning_sessions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exposure_learning_session_id"),
        sa.UniqueConstraint("child_id", "request_key", name="uq_experiment_session_request_key"),
    )
    for column in (
        "child_id",
        "experiment_id",
        "experiment_version_id",
        "accompanying_user_id",
        "exposure_learning_session_id",
    ):
        _index("experiment_sessions", column, unique=column == "exposure_learning_session_id")

    op.create_table(
        "experiment_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("experiment_session_id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("capability_tags", sa.JSON(), nullable=False),
        sa.Column("recorder_user_id", sa.Uuid(), nullable=False),
        sa.Column("client_key", sa.String(length=80), nullable=True),
        sa.Column(
            "captured_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("derived_summary", sa.Text(), nullable=True),
        sa.Column("derived_provider", sa.String(length=60), nullable=True),
        sa.Column("derived_model", sa.String(length=120), nullable=True),
        sa.Column("derived_version", sa.String(length=30), nullable=True),
        sa.CheckConstraint(
            "evidence_type IN ('prediction', 'observation', 'child_summary', "
            "'question_asked', 'child_original_words', 'parent_explanation')",
            name="ck_experiment_evidence_type",
        ),
        sa.ForeignKeyConstraint(
            ["experiment_session_id"], ["experiment_sessions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recorder_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "experiment_session_id", "client_key", name="uq_experiment_evidence_key"
        ),
    )
    for column in ("experiment_session_id", "child_id", "evidence_type", "recorder_user_id"):
        _index("experiment_evidence", column)

    op.create_table(
        "experiment_media_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("experiment_session_id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("media_kind", sa.String(length=16), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploader_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("size_bytes > 0", name="ck_experiment_media_size"),
        sa.CheckConstraint(
            "media_kind IN ('image', 'video', 'audio')", name="ck_experiment_media_kind"
        ),
        sa.ForeignKeyConstraint(
            ["experiment_session_id"], ["experiment_sessions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["uploader_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
    )
    for column in ("experiment_session_id", "family_id", "child_id", "uploader_user_id"):
        _index("experiment_media_assets", column)

    # A science-based story keeps a stable optional link to the actual household session.
    story_fk_names = {
        "stories": "fk_stories_science_session",
        "story_generation_runs": "fk_story_runs_science_session",
        "story_versions": "fk_story_versions_science_session",
    }
    for table, constraint_name in story_fk_names.items():
        op.add_column(table, sa.Column("source_experiment_session_id", sa.Uuid(), nullable=True))
        op.create_foreign_key(
            constraint_name,
            table,
            "experiment_sessions",
            ["source_experiment_session_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        _index(table, "source_experiment_session_id")


def downgrade() -> None:
    story_fk_names = {
        "story_versions": "fk_story_versions_science_session",
        "story_generation_runs": "fk_story_runs_science_session",
        "stories": "fk_stories_science_session",
    }
    for table, constraint_name in story_fk_names.items():
        op.drop_index(op.f(f"ix_{table}_source_experiment_session_id"), table_name=table)
        op.drop_constraint(
            constraint_name,
            table,
            type_="foreignkey",
        )
        op.drop_column(table, "source_experiment_session_id")

    op.drop_table("experiment_media_assets")
    op.drop_table("experiment_evidence")
    op.drop_table("experiment_sessions")
    op.drop_table("experiment_knowledge_points")
    op.drop_table("family_materials")
    op.drop_table("experiment_material_requirements")
    op.drop_table("experiment_materials")
    op.drop_table("science_experiment_versions")
    op.drop_table("science_experiments")

    with op.batch_alter_table("learning_records") as batch:
        batch.drop_constraint("ck_learning_records_activity_type", type_="check")
        batch.create_check_constraint(
            "ck_learning_records_activity_type",
            "activity_type IN ('introduced', 'relearned', 'parent_marked_seen', 'story_exposure')",
        )
