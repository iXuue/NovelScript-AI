"""create feedback plan cache entries

Revision ID: 1b9f6c4d2a31
Revises: d9e4b7c1a8f2
Create Date: 2026-06-07 12:32:33.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "1b9f6c4d2a31"
down_revision: str | Sequence[str] | None = "d9e4b7c1a8f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feedback_plan_cache_entries",
        sa.Column("feedback_plan_id", sa.String(length=40), nullable=False),
        sa.Column("project_id", sa.String(length=40), nullable=False),
        sa.Column("message_id", sa.String(length=40), nullable=True),
        sa.Column("stage", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=False),
        sa.Column("scope_id", sa.String(length=120), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("artifact_fingerprint", sa.String(length=240), nullable=False),
        sa.Column("user_feedback", sa.Text(), nullable=False),
        sa.Column("target", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("modification_plan", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("source_requests", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("cache_hit", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("feedback_plan_id"),
        sa.UniqueConstraint(
            "project_id",
            "stage",
            "target_type",
            "scope_id",
            "input_hash",
            "artifact_fingerprint",
            name="uq_feedback_plan_cache_context",
        ),
    )
    op.create_index(op.f("ix_feedback_plan_cache_entries_project_id"), "feedback_plan_cache_entries", ["project_id"], unique=False)
    op.create_index(op.f("ix_feedback_plan_cache_entries_stage"), "feedback_plan_cache_entries", ["stage"], unique=False)
    op.create_index(op.f("ix_feedback_plan_cache_entries_target_type"), "feedback_plan_cache_entries", ["target_type"], unique=False)
    op.create_index(op.f("ix_feedback_plan_cache_entries_scope_id"), "feedback_plan_cache_entries", ["scope_id"], unique=False)
    op.create_index(op.f("ix_feedback_plan_cache_entries_input_hash"), "feedback_plan_cache_entries", ["input_hash"], unique=False)
    op.create_index(
        op.f("ix_feedback_plan_cache_entries_artifact_fingerprint"),
        "feedback_plan_cache_entries",
        ["artifact_fingerprint"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_feedback_plan_cache_entries_artifact_fingerprint"), table_name="feedback_plan_cache_entries")
    op.drop_index(op.f("ix_feedback_plan_cache_entries_input_hash"), table_name="feedback_plan_cache_entries")
    op.drop_index(op.f("ix_feedback_plan_cache_entries_scope_id"), table_name="feedback_plan_cache_entries")
    op.drop_index(op.f("ix_feedback_plan_cache_entries_target_type"), table_name="feedback_plan_cache_entries")
    op.drop_index(op.f("ix_feedback_plan_cache_entries_stage"), table_name="feedback_plan_cache_entries")
    op.drop_index(op.f("ix_feedback_plan_cache_entries_project_id"), table_name="feedback_plan_cache_entries")
    op.drop_table("feedback_plan_cache_entries")
