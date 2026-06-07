"""Add narrative_function, dialogue_candidates, visual_elements, emotional_beats to chapter_summaries.

Revision ID: e7f8a9c0d1e2
Revises: 1b9f6c4d2a31
Create Date: 2026-06-07 18:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e7f8a9c0d1e2"
down_revision: str | Sequence[str] | None = "1b9f6c4d2a31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


json_list_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.add_column(
        "chapter_summaries",
        sa.Column("narrative_function", sa.Text(), nullable=False, server_default=sa.text("''")),
    )
    op.add_column(
        "chapter_summaries",
        sa.Column("dialogue_candidates", json_list_type, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "chapter_summaries",
        sa.Column("visual_elements", json_list_type, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "chapter_summaries",
        sa.Column("emotional_beats", json_list_type, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("chapter_summaries", "emotional_beats")
    op.drop_column("chapter_summaries", "visual_elements")
    op.drop_column("chapter_summaries", "dialogue_candidates")
    op.drop_column("chapter_summaries", "narrative_function")
