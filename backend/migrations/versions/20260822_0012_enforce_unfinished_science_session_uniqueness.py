"""Enforce one unfinished science session per child and experiment.

Revision ID: 20260822_0012
Revises: 20260820_0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260822_0012"
down_revision: str | None = "20260820_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_experiment_sessions_unfinished",
        "experiment_sessions",
        ["child_id", "experiment_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('planned', 'in_progress')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_experiment_sessions_unfinished",
        table_name="experiment_sessions",
    )
