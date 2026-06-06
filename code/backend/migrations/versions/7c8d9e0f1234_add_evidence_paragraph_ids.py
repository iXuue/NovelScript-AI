"""add evidence paragraph ids

Revision ID: 7c8d9e0f1234
Revises: c8a4d6f2b901
Create Date: 2026-06-06 15:20:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "7c8d9e0f1234"
down_revision: str | Sequence[str] | None = "c8a4d6f2b901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evidence_items",
        sa.Column(
            "paragraph_ids",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.execute("UPDATE evidence_items SET paragraph_ids = jsonb_build_array(paragraph_id) WHERE paragraph_id IS NOT NULL")
    op.alter_column("evidence_items", "paragraph_ids", server_default=None)
    op.alter_column("evidence_items", "paragraph_id", existing_type=sa.String(length=60), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE evidence_items SET paragraph_id = paragraph_ids->>0 WHERE paragraph_id IS NULL")
    op.alter_column("evidence_items", "paragraph_id", existing_type=sa.String(length=60), nullable=False)
    op.drop_column("evidence_items", "paragraph_ids")
