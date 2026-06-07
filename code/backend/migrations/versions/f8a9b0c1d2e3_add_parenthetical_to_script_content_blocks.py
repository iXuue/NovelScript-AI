"""Add parenthetical to script_content_blocks.

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9c0d1e2
Create Date: 2026-06-07 19:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f8a9b0c1d2e3"
down_revision: str | Sequence[str] | None = "e7f8a9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "script_content_blocks",
        sa.Column("parenthetical", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("script_content_blocks", "parenthetical")
