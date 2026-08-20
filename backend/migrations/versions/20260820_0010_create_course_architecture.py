"""Create reusable course architecture and versioned catalog provenance.

Revision ID: 20260820_0010
Revises: 20260820_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0010"
down_revision: str | None = "20260820_0009"
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
    op.add_column(
        "assessment_session_plans",
        sa.Column(
            "catalog_version",
            sa.String(80),
            server_default="growth-starter-v1",
            nullable=False,
        ),
    )
    op.create_table(
        "catalog_releases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("catalog_version", sa.String(80), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_name", sa.String(160), nullable=False),
        sa.Column("source_reference", sa.String(500)),
        sa.Column("license", sa.String(120)),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("catalog_version"),
    )
    _index("catalog_releases", "catalog_version", unique=True)

    op.create_table(
        "character_catalog_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("catalog_release_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("source_reference", sa.String(500)),
        *_timestamps(),
        sa.CheckConstraint("order_index >= 0", name="ck_catalog_entry_order"),
        sa.ForeignKeyConstraint(
            ["catalog_release_id"], ["catalog_releases.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "catalog_release_id", "knowledge_point_id", name="uq_catalog_entry_point"
        ),
        sa.UniqueConstraint("catalog_release_id", "order_index", name="uq_catalog_entry_order"),
    )
    _index("character_catalog_entries", "catalog_release_id")
    _index("character_catalog_entries", "knowledge_point_id")

    op.create_table(
        "courses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(30), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("family_id", sa.Uuid()),
        sa.Column("teacher_id", sa.Uuid()),
        sa.Column("created_by_user_id", sa.Uuid()),
        sa.Column("recommended_age_min", sa.Integer()),
        sa.Column("recommended_age_max", sa.Integer()),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("system_key", sa.String(100)),
        sa.Column("reference_metadata", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("subject IN ('chinese')", name="ck_courses_subject"),
        sa.CheckConstraint(
            "source_type IN ('system', 'family', 'teacher', 'textbook_reference')",
            name="ck_courses_source",
        ),
        sa.CheckConstraint("status IN ('draft', 'enabled', 'archived')", name="ck_courses_status"),
        sa.CheckConstraint("version >= 1", name="ck_courses_version"),
        sa.CheckConstraint(
            "(source_type = 'system' AND family_id IS NULL AND teacher_id IS NULL) OR "
            "(source_type IN ('family', 'textbook_reference') AND family_id IS NOT NULL "
            "AND teacher_id IS NULL) OR "
            "(source_type = 'teacher' AND family_id IS NULL AND teacher_id IS NOT NULL)",
            name="ck_courses_owner",
        ),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["teacher_id"], ["teacher_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("system_key"),
    )
    _index("courses", "source_type")
    _index("courses", "family_id")
    _index("courses", "teacher_id")
    _index("courses", "created_by_user_id")

    op.create_table(
        "course_units",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), server_default="enabled", nullable=False),
        *_timestamps(),
        sa.CheckConstraint("order_index >= 0", name="ck_course_units_order"),
        sa.CheckConstraint(
            "status IN ('draft', 'enabled', 'archived')", name="ck_course_units_status"
        ),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("course_id", "order_index", name="uq_course_unit_order"),
    )
    _index("course_units", "course_id")

    op.create_table(
        "learning_activities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("course_unit_id", sa.Uuid(), nullable=False),
        sa.Column("activity_type", sa.String(40), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("instructions", sa.Text()),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), server_default="enabled", nullable=False),
        sa.Column("content_metadata", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("order_index >= 0", name="ck_learning_activities_order"),
        sa.CheckConstraint(
            "activity_type IN ('character_learning', 'character_review', "
            "'recognition_check', 'reading', 'science_reference', 'offline_instruction')",
            name="ck_learning_activities_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'enabled', 'archived')",
            name="ck_learning_activities_status",
        ),
        sa.ForeignKeyConstraint(["course_unit_id"], ["course_units.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("course_unit_id", "order_index", name="uq_learning_activity_order"),
    )
    _index("learning_activities", "course_unit_id")

    op.create_table(
        "activity_knowledge_points",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("activity_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(24), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("order_index >= 0", name="ck_activity_knowledge_points_order"),
        sa.CheckConstraint(
            "role IN ('primary', 'review', 'optional', 'prerequisite')",
            name="ck_activity_knowledge_points_role",
        ),
        sa.ForeignKeyConstraint(["activity_id"], ["learning_activities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "activity_id", "knowledge_point_id", name="uq_activity_knowledge_point"
        ),
    )
    _index("activity_knowledge_points", "activity_id")
    _index("activity_knowledge_points", "knowledge_point_id")

    op.create_table(
        "child_course_enrollments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("course_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), server_default="planned", nullable=False),
        sa.Column("path_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("current_unit_id", sa.Uuid()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("settings", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("path_order >= 0", name="ck_child_course_enrollments_order"),
        sa.CheckConstraint(
            "status IN ('planned', 'active', 'paused', 'completed', 'archived')",
            name="ck_child_course_enrollments_status",
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["current_unit_id"], ["course_units.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("child_id", "course_id", name="uq_child_course_enrollment"),
    )
    _index("child_course_enrollments", "child_id")
    _index("child_course_enrollments", "course_id")

    op.create_table(
        "course_activity_progress",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("enrollment_id", sa.Uuid(), nullable=False),
        sa.Column("activity_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("learning_session_id", sa.Uuid()),
        sa.Column("assessment_session_id", sa.Uuid()),
        sa.Column("reading_session_id", sa.Uuid()),
        sa.Column("experiment_session_id", sa.Uuid()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed')",
            name="ck_course_activity_progress_status",
        ),
        sa.ForeignKeyConstraint(
            ["enrollment_id"], ["child_course_enrollments.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["activity_id"], ["learning_activities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["learning_session_id"], ["learning_sessions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["assessment_session_id"], ["assessment_sessions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reading_session_id"], ["reading_sessions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["experiment_session_id"], ["experiment_sessions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("enrollment_id", "activity_id", name="uq_course_activity_progress"),
    )
    _index("course_activity_progress", "enrollment_id")
    _index("course_activity_progress", "activity_id")

    op.add_column(
        "literacy_estimates",
        sa.Column(
            "catalog_version",
            sa.String(80),
            server_default="growth-starter-v1",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("literacy_estimates", "catalog_version")
    for table in (
        "course_activity_progress",
        "child_course_enrollments",
        "activity_knowledge_points",
        "learning_activities",
        "course_units",
        "courses",
        "character_catalog_entries",
        "catalog_releases",
    ):
        op.drop_table(table)
    op.drop_column("assessment_session_plans", "catalog_version")
