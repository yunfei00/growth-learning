"""Create additive Curriculum Platform V1 structures.

Revision ID: 20260830_0020
Revises: 20260829_0019
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_0020"
down_revision: str | None = "20260829_0019"
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
    op.create_table(
        "curriculum_releases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("curriculum_key", sa.String(180), nullable=False),
        sa.Column("release_version", sa.String(80), nullable=False),
        sa.Column("education_stage", sa.String(30), nullable=False),
        sa.Column("grade_level", sa.Integer()),
        sa.Column("semester", sa.String(20), nullable=False),
        sa.Column("subject", sa.String(30), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("source_type", sa.String(40), server_default="project_curated", nullable=False),
        sa.Column("source_name", sa.String(160), nullable=False),
        sa.Column("source_reference", sa.String(500)),
        sa.Column("license", sa.String(120)),
        sa.Column("copyright_notice", sa.Text()),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Uuid()),
        sa.Column("published_by_user_id", sa.Uuid()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("change_summary", sa.Text()),
        sa.Column(
            "validation_snapshot", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False
        ),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('draft', 'in_review', 'published', 'archived')",
            name="ck_curriculum_releases_status",
        ),
        sa.CheckConstraint(
            "education_stage IN ('foundation', 'primary', 'junior_middle')",
            name="ck_curriculum_releases_stage",
        ),
        sa.CheckConstraint(
            "semester IN ('full_year', 'semester_1', 'semester_2')",
            name="ck_curriculum_releases_semester",
        ),
        sa.CheckConstraint(
            "(education_stage = 'foundation' AND grade_level IS NULL) OR "
            "(education_stage = 'primary' AND grade_level BETWEEN 1 AND 6) OR "
            "(education_stage = 'junior_middle' AND grade_level BETWEEN 7 AND 9)",
            name="ck_curriculum_releases_stage_grade",
        ),
        sa.CheckConstraint(
            "subject IN ('chinese', 'math', 'english', 'science')",
            name="ck_curriculum_releases_subject",
        ),
        sa.CheckConstraint(
            "source_type IN ('project_curated', 'curriculum_standard_reference', "
            "'textbook_reference', 'teacher_curated')",
            name="ck_curriculum_releases_source_type",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "curriculum_key", "release_version", name="uq_curriculum_release_identity"
        ),
    )
    for column in (
        "curriculum_key",
        "release_version",
        "education_stage",
        "grade_level",
        "semester",
        "subject",
        "created_by_user_id",
        "reviewed_by_user_id",
        "published_by_user_id",
    ):
        _index("curriculum_releases", column)

    op.add_column(
        "courses",
        sa.Column("education_stage", sa.String(30), server_default="foundation", nullable=False),
    )
    op.add_column("courses", sa.Column("grade_level", sa.Integer()))
    op.add_column(
        "courses", sa.Column("semester", sa.String(20), server_default="full_year", nullable=False)
    )
    op.add_column("courses", sa.Column("curriculum_key", sa.String(180)))
    op.add_column("courses", sa.Column("curriculum_version", sa.String(80)))
    op.add_column("courses", sa.Column("curriculum_release_id", sa.Uuid()))
    op.create_check_constraint(
        "ck_courses_education_stage",
        "courses",
        "education_stage IN ('foundation', 'primary', 'junior_middle')",
    )
    op.create_check_constraint(
        "ck_courses_semester",
        "courses",
        "semester IN ('full_year', 'semester_1', 'semester_2')",
    )
    op.create_check_constraint(
        "ck_courses_stage_grade",
        "courses",
        "(education_stage = 'foundation' AND grade_level IS NULL) OR "
        "(education_stage = 'primary' AND grade_level BETWEEN 1 AND 6) OR "
        "(education_stage = 'junior_middle' AND grade_level BETWEEN 7 AND 9)",
    )
    op.create_unique_constraint(
        "uq_courses_curriculum_version", "courses", ["curriculum_key", "curriculum_version"]
    )
    op.create_foreign_key(
        "fk_courses_curriculum_release_id",
        "courses",
        "curriculum_releases",
        ["curriculum_release_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    for column in (
        "grade_level",
        "curriculum_key",
        "curriculum_version",
        "curriculum_release_id",
    ):
        _index("courses", column, unique=column == "curriculum_release_id")

    op.create_table(
        "course_lessons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("course_unit_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer()),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("order_index >= 0", name="ck_course_lessons_order"),
        sa.CheckConstraint(
            "status IN ('draft', 'enabled', 'archived')", name="ck_course_lessons_status"
        ),
        sa.CheckConstraint(
            "estimated_minutes IS NULL OR estimated_minutes > 0",
            name="ck_course_lessons_estimated_minutes",
        ),
        sa.ForeignKeyConstraint(["course_unit_id"], ["course_units.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("course_unit_id", "order_index", name="uq_course_lesson_order"),
    )
    _index("course_lessons", "course_unit_id")

    op.add_column("learning_activities", sa.Column("lesson_id", sa.Uuid()))
    op.create_foreign_key(
        "fk_learning_activities_lesson_id",
        "learning_activities",
        "course_lessons",
        ["lesson_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    _index("learning_activities", "lesson_id")

    op.add_column("activity_knowledge_points", sa.Column("reference_code", sa.String(160)))
    op.add_column(
        "activity_knowledge_points",
        sa.Column(
            "curriculum_metadata",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
    )

    op.add_column("child_course_enrollments", sa.Column("curriculum_release_id", sa.Uuid()))
    op.create_foreign_key(
        "fk_child_course_enrollments_curriculum_release_id",
        "child_course_enrollments",
        "curriculum_releases",
        ["curriculum_release_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    _index("child_course_enrollments", "curriculum_release_id")

    op.add_column("children", sa.Column("current_grade_level", sa.Integer()))
    op.add_column("children", sa.Column("school_year", sa.String(20)))
    op.create_check_constraint(
        "ck_children_current_grade_level",
        "children",
        "current_grade_level IS NULL OR current_grade_level BETWEEN 1 AND 9",
    )
    _index("children", "current_grade_level")

    op.create_table(
        "course_platform_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("enrollment_id", sa.Uuid()),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("is_first_party", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('course_started', 'lesson_started', 'lesson_completed', "
            "'activity_completed', 'course_returned')",
            name="ck_course_platform_events_type",
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["enrollment_id"], ["child_course_enrollments.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("child_id", "enrollment_id", "event_type", "occurred_at"):
        _index("course_platform_events", column)


def downgrade() -> None:
    op.drop_table("course_platform_events")
    op.drop_index(op.f("ix_children_current_grade_level"), table_name="children")
    op.drop_constraint("ck_children_current_grade_level", "children", type_="check")
    op.drop_column("children", "school_year")
    op.drop_column("children", "current_grade_level")
    op.drop_index(
        op.f("ix_child_course_enrollments_curriculum_release_id"),
        table_name="child_course_enrollments",
    )
    op.drop_constraint(
        "fk_child_course_enrollments_curriculum_release_id",
        "child_course_enrollments",
        type_="foreignkey",
    )
    op.drop_column("child_course_enrollments", "curriculum_release_id")
    op.drop_column("activity_knowledge_points", "curriculum_metadata")
    op.drop_column("activity_knowledge_points", "reference_code")
    op.drop_index(op.f("ix_learning_activities_lesson_id"), table_name="learning_activities")
    op.drop_constraint(
        "fk_learning_activities_lesson_id", "learning_activities", type_="foreignkey"
    )
    op.drop_column("learning_activities", "lesson_id")
    op.drop_table("course_lessons")
    for column in (
        "curriculum_release_id",
        "curriculum_version",
        "curriculum_key",
        "grade_level",
    ):
        op.drop_index(op.f(f"ix_courses_{column}"), table_name="courses")
    op.drop_constraint("fk_courses_curriculum_release_id", "courses", type_="foreignkey")
    op.drop_constraint("uq_courses_curriculum_version", "courses", type_="unique")
    op.drop_constraint("ck_courses_stage_grade", "courses", type_="check")
    op.drop_constraint("ck_courses_semester", "courses", type_="check")
    op.drop_constraint("ck_courses_education_stage", "courses", type_="check")
    op.drop_column("courses", "curriculum_release_id")
    op.drop_column("courses", "curriculum_version")
    op.drop_column("courses", "curriculum_key")
    op.drop_column("courses", "semester")
    op.drop_column("courses", "grade_level")
    op.drop_column("courses", "education_stage")
    op.drop_table("curriculum_releases")
