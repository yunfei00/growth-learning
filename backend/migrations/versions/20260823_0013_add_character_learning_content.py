"""Add parent-maintained character learning guidance.

Revision ID: 20260823_0013
Revises: 20260822_0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260823_0013"
down_revision: str | None = "20260822_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chinese_characters", sa.Column("parent_tip", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("chinese_characters", "parent_tip")
