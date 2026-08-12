"""Add independent system administrator role.

Revision ID: 20260812_0002
Revises: 20260812_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0002"
down_revision: str | None = "20260812_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("system_role", sa.String(length=20), server_default="user", nullable=False),
    )
    op.create_check_constraint("ck_users_system_role", "users", "system_role IN ('user', 'admin')")


def downgrade() -> None:
    op.drop_constraint("ck_users_system_role", "users", type_="check")
    op.drop_column("users", "system_role")
