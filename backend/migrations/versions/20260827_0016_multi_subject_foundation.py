"""Add the multi-subject knowledge, evidence, and mastery foundation.

Revision ID: 20260827_0016
Revises: 20260826_0015
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_0016"
down_revision: str | None = "20260826_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SUBJECTS = "'chinese', 'math', 'english', 'science'"
KNOWLEDGE_TYPES = (
    "'chinese_character', 'pinyin_initial', 'pinyin_final', 'pinyin_tone', "
    "'pinyin_syllable', 'math_skill', 'english_letter', 'english_word', "
    "'english_phonics', 'science_concept'"
)
ACTIVITY_TYPES = (
    "'knowledge_learning', 'guided_practice', 'independent_practice', "
    "'knowledge_review', 'knowledge_check', 'listening', 'speaking', "
    "'character_learning', 'character_review', 'recognition_check', 'reading', "
    "'science_reference', 'offline_instruction'"
)
EVIDENCE_TYPES = (
    "'introduced', 'relearned', 'parent_marked_seen', 'story_exposure', "
    "'science_experiment_exposure', 'guided_practice', 'independent_practice', "
    "'reviewed', 'applied'"
)


def upgrade() -> None:
    op.add_column(
        "knowledge_points",
        sa.Column("subject", sa.String(length=30), nullable=True),
    )
    op.execute("UPDATE knowledge_points SET subject = 'chinese' WHERE subject IS NULL")
    op.alter_column(
        "knowledge_points",
        "subject",
        existing_type=sa.String(length=30),
        nullable=False,
        server_default="chinese",
    )
    op.create_index(op.f("ix_knowledge_points_subject"), "knowledge_points", ["subject"])
    op.drop_constraint("ck_knowledge_points_type", "knowledge_points", type_="check")
    op.create_check_constraint(
        "ck_knowledge_points_type",
        "knowledge_points",
        f"type IN ({KNOWLEDGE_TYPES})",
    )
    op.create_check_constraint(
        "ck_knowledge_points_subject",
        "knowledge_points",
        f"subject IN ({SUBJECTS})",
    )
    op.create_check_constraint(
        "ck_knowledge_points_type_subject",
        "knowledge_points",
        "(type IN ('chinese_character', 'pinyin_initial', 'pinyin_final', "
        "'pinyin_tone', 'pinyin_syllable') AND subject = 'chinese') OR "
        "(type = 'math_skill' AND subject = 'math') OR "
        "(type IN ('english_letter', 'english_word', 'english_phonics') "
        "AND subject = 'english') OR "
        "(type = 'science_concept' AND subject = 'science')",
    )

    op.drop_constraint("ck_courses_subject", "courses", type_="check")
    op.create_check_constraint(
        "ck_courses_subject",
        "courses",
        f"subject IN ({SUBJECTS})",
    )
    op.drop_constraint("ck_learning_activities_type", "learning_activities", type_="check")
    op.create_check_constraint(
        "ck_learning_activities_type",
        "learning_activities",
        f"activity_type IN ({ACTIVITY_TYPES})",
    )
    op.drop_constraint("ck_learning_records_activity_type", "learning_records", type_="check")
    op.create_check_constraint(
        "ck_learning_records_activity_type",
        "learning_records",
        f"activity_type IN ({EVIDENCE_TYPES})",
    )

    op.add_column(
        "assessment_sessions",
        sa.Column(
            "assessment_kind",
            sa.String(length=30),
            server_default="recognition",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_assessment_sessions_kind",
        "assessment_sessions",
        "assessment_kind IN ('recognition', 'practice_check', 'listening_check', "
        "'oral_check', 'math_check')",
    )
    op.add_column(
        "assessment_items",
        sa.Column("skill_dimension", sa.String(length=60)),
    )
    op.add_column(
        "assessment_items",
        sa.Column(
            "evidence_metadata",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
    )

    op.add_column(
        "child_knowledge_states",
        sa.Column(
            "policy_key",
            sa.String(length=80),
            server_default="chinese-character-v1",
            nullable=False,
        ),
    )
    op.add_column(
        "child_knowledge_states",
        sa.Column(
            "state_code",
            sa.String(length=40),
            server_default="unlearned",
            nullable=False,
        ),
    )
    op.add_column(
        "child_knowledge_states",
        sa.Column(
            "dimensions_json",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
    )
    op.execute("UPDATE child_knowledge_states SET state_code = mastery_level")


def downgrade() -> None:
    op.drop_column("child_knowledge_states", "dimensions_json")
    op.drop_column("child_knowledge_states", "state_code")
    op.drop_column("child_knowledge_states", "policy_key")
    op.drop_column("assessment_items", "evidence_metadata")
    op.drop_column("assessment_items", "skill_dimension")
    op.drop_constraint("ck_assessment_sessions_kind", "assessment_sessions", type_="check")
    op.drop_column("assessment_sessions", "assessment_kind")

    op.drop_constraint("ck_learning_records_activity_type", "learning_records", type_="check")
    op.create_check_constraint(
        "ck_learning_records_activity_type",
        "learning_records",
        "activity_type IN ('introduced', 'relearned', 'parent_marked_seen', "
        "'story_exposure', 'science_experiment_exposure')",
    )
    op.drop_constraint("ck_learning_activities_type", "learning_activities", type_="check")
    op.create_check_constraint(
        "ck_learning_activities_type",
        "learning_activities",
        "activity_type IN ('character_learning', 'character_review', 'recognition_check', "
        "'reading', 'science_reference', 'offline_instruction')",
    )
    op.drop_constraint("ck_courses_subject", "courses", type_="check")
    op.create_check_constraint("ck_courses_subject", "courses", "subject IN ('chinese')")

    op.drop_constraint("ck_knowledge_points_type_subject", "knowledge_points", type_="check")
    op.drop_constraint("ck_knowledge_points_subject", "knowledge_points", type_="check")
    op.drop_constraint("ck_knowledge_points_type", "knowledge_points", type_="check")
    op.create_check_constraint(
        "ck_knowledge_points_type",
        "knowledge_points",
        "type IN ('chinese_character')",
    )
    op.drop_index(op.f("ix_knowledge_points_subject"), table_name="knowledge_points")
    op.drop_column("knowledge_points", "subject")
