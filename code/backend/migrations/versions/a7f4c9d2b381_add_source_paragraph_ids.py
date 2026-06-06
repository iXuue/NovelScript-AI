"""Add source paragraph ids to scene plans and script blocks.

Revision ID: a7f4c9d2b381
Revises: c8a4d6f2b901
Create Date: 2026-06-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a7f4c9d2b381"
down_revision: str | Sequence[str] | None = "c8a4d6f2b901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


json_list_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.add_column(
        "scene_plan_scenes",
        sa.Column("source_paragraph_ids", json_list_type, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "script_content_blocks",
        sa.Column("source_paragraph_ids", json_list_type, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("script_content_blocks", "source_paragraph_ids")
    op.drop_column("scene_plan_scenes", "source_paragraph_ids")
