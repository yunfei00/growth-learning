"""Create the unified growth archive and portable export foundation.

Revision ID: 20260813_0008
Revises: 20260813_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0008"
down_revision: str | None = "20260813_0007"
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


def _index(table: str, column: str) -> None:
    op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def upgrade() -> None:
    op.create_table(
        "growth_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("category", sa.String(length=24), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("source_entity_type", sa.String(length=60), nullable=True),
        sa.Column("source_entity_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=180), nullable=True),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "policy_version", sa.String(length=30), server_default="growth-event-v1", nullable=False
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correction_of_event_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "event_type IN ('learning_milestone', 'assessment_milestone', 'reading_milestone', "
            "'science_milestone', 'original_words', 'manual_growth_note', "
            "'family_observation', 'achievement', 'report_marker')",
            name="ck_growth_events_type",
        ),
        sa.CheckConstraint(
            "category IN ('learning', 'assessment', 'reading', 'science', 'family', "
            "'original_words', 'achievement', 'report')",
            name="ck_growth_events_category",
        ),
        sa.CheckConstraint(
            "source_type IN ('system', 'parent', 'companion')", name="ck_growth_events_source"
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["correction_of_event_id"], ["growth_events.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("child_id", "idempotency_key", name="uq_growth_event_idempotency"),
    )
    for column in (
        "child_id",
        "event_type",
        "category",
        "occurred_at",
        "actor_user_id",
        "source_entity_type",
        "source_entity_id",
        "archived_at",
        "correction_of_event_id",
    ):
        _index("growth_events", column)

    op.create_table(
        "growth_media_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("growth_event_id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint("size_bytes > 0", name="ck_growth_media_size"),
        sa.CheckConstraint(
            "media_kind IN ('image', 'video', 'audio')", name="ck_growth_media_kind"
        ),
        sa.ForeignKeyConstraint(["growth_event_id"], ["growth_events.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["uploader_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
    )
    for column in ("growth_event_id", "family_id", "child_id", "uploader_user_id"):
        _index("growth_media_assets", column)

    op.create_table(
        "growth_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("period_type", sa.String(length=20), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "period_type IN ('monthly', 'yearly', 'custom')", name="ck_growth_report_period"
        ),
        sa.CheckConstraint("period_end >= period_start", name="ck_growth_report_range"),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "child_id", "period_type", "period_start", "period_end", name="uq_growth_report_period"
        ),
    )
    for column in ("child_id", "period_type", "created_by_user_id"):
        _index("growth_reports", column)

    op.create_table(
        "growth_report_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column(
            "generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("source_cutoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("policy_version", sa.String(length=30), nullable=False),
        sa.Column("metrics_snapshot", sa.JSON(), nullable=False),
        sa.Column("deterministic_sections", sa.JSON(), nullable=False),
        sa.Column("selected_event_ids", sa.JSON(), nullable=False),
        sa.Column("ai_narrative", sa.Text(), nullable=True),
        sa.Column("ai_provider", sa.String(length=60), nullable=True),
        sa.Column("ai_model", sa.String(length=120), nullable=True),
        sa.Column("ai_prompt_version", sa.String(length=30), nullable=True),
        sa.Column("ai_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("version_number >= 1", name="ck_growth_report_version_number"),
        sa.ForeignKeyConstraint(["report_id"], ["growth_reports.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_id", "version_number", name="uq_growth_report_version"),
    )
    _index("growth_report_versions", "report_id")

    op.create_table(
        "growth_books",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=False),
        sa.Column("edition_type", sa.String(length=20), nullable=False),
        sa.Column("edition_key", sa.String(length=40), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("edition_type IN ('yearly', 'age_year')", name="ck_growth_book_edition"),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "child_id", "edition_type", "edition_key", name="uq_growth_book_edition"
        ),
    )
    for column in ("child_id", "created_by_user_id"):
        _index("growth_books", column)

    op.create_table(
        "growth_book_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("growth_book_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("selected_event_ids", sa.JSON(), nullable=False),
        sa.Column("selected_media", sa.JSON(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("parent_message", sa.Text(), nullable=True),
        sa.Column("message_author_user_id", sa.Uuid(), nullable=True),
        sa.Column("message_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("version_number >= 1", name="ck_growth_book_version_number"),
        sa.ForeignKeyConstraint(["growth_book_id"], ["growth_books.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["message_author_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("growth_book_id", "version_number", name="uq_growth_book_version"),
    )
    for column in ("growth_book_id", "message_author_user_id"):
        _index("growth_book_versions", column)

    op.create_table(
        "export_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("child_id", sa.Uuid(), nullable=True),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column(
            "schema_version",
            sa.String(length=50),
            server_default="growth-learning-export-v1",
            nullable=False,
        ),
        sa.Column("object_key", sa.String(length=512), nullable=True),
        sa.Column("manifest_snapshot", sa.JSON(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("failure_reason", sa.String(length=240), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed', 'expired')",
            name="ck_export_jobs_status",
        ),
        sa.CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="ck_export_jobs_size"),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
    )
    for column in ("family_id", "child_id", "requested_by_user_id", "expires_at"):
        _index("export_jobs", column)


def downgrade() -> None:
    op.drop_table("export_jobs")
    op.drop_table("growth_book_versions")
    op.drop_table("growth_books")
    op.drop_table("growth_report_versions")
    op.drop_table("growth_reports")
    op.drop_table("growth_media_assets")
    op.drop_table("growth_events")
