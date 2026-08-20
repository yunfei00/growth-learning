"""Create parent-authorized teacher collaboration foundation.

Revision ID: 20260820_0009
Revises: 20260813_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0009"
down_revision: str | None = "20260813_0008"
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
    op.drop_constraint("ck_growth_events_source", "growth_events", type_="check")
    op.create_check_constraint(
        "ck_growth_events_source",
        "growth_events",
        "source_type IN ('system', 'parent', 'companion', 'teacher')",
    )

    op.create_table(
        "teacher_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("organization_name", sa.String(length=120), nullable=True),
        sa.Column("short_bio", sa.String(length=300), nullable=True),
        sa.Column("teacher_code", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        *_timestamps(),
        sa.CheckConstraint("status IN ('active', 'disabled')", name="ck_teacher_profiles_status"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("teacher_code"),
        sa.UniqueConstraint("user_id"),
    )
    _index("teacher_profiles", "user_id", unique=True)
    _index("teacher_profiles", "teacher_code", unique=True)

    op.create_table(
        "teacher_child_relations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("authorized_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "authorized_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("revoked_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("permission_scope", sa.JSON(), nullable=False),
        sa.Column(
            "permission_version",
            sa.String(length=30),
            server_default="teacher-scope-v1",
            nullable=False,
        ),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('active', 'revoked')", name="ck_teacher_child_relations_status"
        ),
        sa.ForeignKeyConstraint(["teacher_id"], ["teacher_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["authorized_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("teacher_id", "child_id", name="uq_teacher_child_relation"),
    )
    for column in (
        "teacher_id",
        "child_id",
        "family_id",
        "authorized_by_user_id",
        "revoked_by_user_id",
    ):
        _index("teacher_child_relations", column)

    op.create_table(
        "classrooms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column("class_code", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        *_timestamps(),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_classrooms_status"),
        sa.ForeignKeyConstraint(["teacher_id"], ["teacher_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("class_code"),
    )
    _index("classrooms", "teacher_id")
    _index("classrooms", "class_code", unique=True)

    op.create_table(
        "classroom_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("classroom_id", sa.Uuid(), nullable=False),
        sa.Column("relation_id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("joined_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("status IN ('active', 'left')", name="ck_classroom_memberships_status"),
        sa.ForeignKeyConstraint(["classroom_id"], ["classrooms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["relation_id"], ["teacher_child_relations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["joined_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("classroom_id", "child_id", name="uq_classroom_membership_child"),
    )
    for column in ("classroom_id", "relation_id", "child_id", "joined_by_user_id"):
        _index("classroom_memberships", column)

    op.create_table(
        "teacher_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column("classroom_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("assignment_type", sa.String(length=32), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "assignment_type IN ('character_learning', 'character_review', "
            "'recognition_check', 'reading', 'freeform_instruction')",
            name="ck_teacher_assignments_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'closed', 'archived')",
            name="ck_teacher_assignments_status",
        ),
        sa.ForeignKeyConstraint(["teacher_id"], ["teacher_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["classroom_id"], ["classrooms.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("teacher_id", "classroom_id", "assignment_type", "due_at"):
        _index("teacher_assignments", column)

    op.create_table(
        "teacher_assignment_targets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("relation_id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["assignment_id"], ["teacher_assignments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["relation_id"], ["teacher_child_relations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assignment_id", "child_id", name="uq_teacher_assignment_target"),
    )
    for column in ("assignment_id", "relation_id", "child_id"):
        _index("teacher_assignment_targets", column)

    op.create_table(
        "teacher_assignment_knowledge_points",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_point_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("position >= 1", name="ck_teacher_assignment_point_position"),
        sa.ForeignKeyConstraint(["assignment_id"], ["teacher_assignments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assignment_id", "knowledge_point_id", name="uq_teacher_assignment_point"
        ),
        sa.UniqueConstraint("assignment_id", "position", name="uq_teacher_assignment_position"),
    )
    _index("teacher_assignment_knowledge_points", "assignment_id")
    _index("teacher_assignment_knowledge_points", "knowledge_point_id")

    op.create_table(
        "teacher_assignment_progress",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("completed_item_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("learning_session_id", sa.Uuid(), nullable=True),
        sa.Column("assessment_session_id", sa.Uuid(), nullable=True),
        sa.Column("reading_session_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed')",
            name="ck_teacher_assignment_progress_status",
        ),
        sa.CheckConstraint("completed_item_count >= 0", name="ck_teacher_progress_count"),
        sa.ForeignKeyConstraint(["assignment_id"], ["teacher_assignments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["learning_session_id"], ["learning_sessions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["assessment_session_id"], ["assessment_sessions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reading_session_id"], ["reading_sessions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assignment_id", "child_id", name="uq_teacher_assignment_progress"),
        sa.UniqueConstraint("learning_session_id"),
        sa.UniqueConstraint("assessment_session_id"),
    )
    for column in (
        "assignment_id",
        "child_id",
        "learning_session_id",
        "assessment_session_id",
        "reading_session_id",
    ):
        _index("teacher_assignment_progress", column)

    op.create_table(
        "teacher_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column("relation_id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("classroom_id", sa.Uuid(), nullable=True),
        sa.Column("assignment_id", sa.Uuid(), nullable=True),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "category IN ('recognition', 'reading', 'expression', 'learning_habit', "
            "'participation', 'other')",
            name="ck_teacher_observations_category",
        ),
        sa.ForeignKeyConstraint(["teacher_id"], ["teacher_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["relation_id"], ["teacher_child_relations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["classroom_id"], ["classrooms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assignment_id"], ["teacher_assignments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "teacher_id",
        "relation_id",
        "child_id",
        "classroom_id",
        "assignment_id",
        "category",
    ):
        _index("teacher_observations", column)

    op.create_table(
        "teacher_observation_knowledge_points",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("observation_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_point_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["observation_id"], ["teacher_observations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "observation_id", "knowledge_point_id", name="uq_teacher_observation_point"
        ),
    )
    _index("teacher_observation_knowledge_points", "observation_id")
    _index("teacher_observation_knowledge_points", "knowledge_point_id")


def downgrade() -> None:
    op.drop_table("teacher_observation_knowledge_points")
    op.drop_table("teacher_observations")
    op.drop_table("teacher_assignment_progress")
    op.drop_table("teacher_assignment_knowledge_points")
    op.drop_table("teacher_assignment_targets")
    op.drop_table("teacher_assignments")
    op.drop_table("classroom_memberships")
    op.drop_table("classrooms")
    op.drop_table("teacher_child_relations")
    op.drop_table("teacher_profiles")
    op.drop_constraint("ck_growth_events_source", "growth_events", type_="check")
    op.create_check_constraint(
        "ck_growth_events_source",
        "growth_events",
        "source_type IN ('system', 'parent', 'companion')",
    )
