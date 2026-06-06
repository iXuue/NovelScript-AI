"""agent framework persistence and budgets

Revision ID: c8a4d6f2b901
Revises: 9d3b0f4a1c2e
Create Date: 2026-06-06 15:10:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c8a4d6f2b901"
down_revision: str | Sequence[str] | None = "9d3b0f4a1c2e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("auth_sessions", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))
    op.add_column("auth_sessions", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("projects", sa.Column("style_locked", sa.Boolean(), nullable=False, server_default=sa.false()))

    with op.batch_alter_table("scene_plans") as batch:
        batch.drop_constraint("uq_scene_plans_project_status", type_="unique")
        batch.add_column(sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column("parent_scene_plan_id", sa.String(length=40), nullable=True))
        batch.add_column(sa.Column("stale_reason", sa.Text(), nullable=True))
        batch.create_unique_constraint("uq_scene_plans_project_version", ["project_id", "version_number"])

    with op.batch_alter_table("script_versions") as batch:
        batch.drop_constraint("uq_script_versions_project_status", type_="unique")
        batch.add_column(sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column("parent_script_version_id", sa.String(length=40), nullable=True))
        batch.add_column(sa.Column("stale_reason", sa.Text(), nullable=True))
        batch.create_unique_constraint("uq_script_versions_project_version", ["project_id", "version_number"])

    op.create_table(
        "agent_runs",
        sa.Column("run_id", sa.String(length=40), nullable=False),
        sa.Column("project_id", sa.String(length=40), nullable=False),
        sa.Column("trigger_type", sa.String(length=80), nullable=False),
        sa.Column("stage", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("current_step", sa.String(length=80), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("ix_agent_runs_project_id", "agent_runs", ["project_id"], unique=False)

    op.create_table(
        "agent_run_steps",
        sa.Column("run_step_id", sa.String(length=40), nullable=False),
        sa.Column("run_id", sa.String(length=40), nullable=False),
        sa.Column("project_id", sa.String(length=40), nullable=False),
        sa.Column("step_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("run_step_id"),
    )
    op.create_index("ix_agent_run_steps_project_id", "agent_run_steps", ["project_id"], unique=False)
    op.create_index("ix_agent_run_steps_run_id", "agent_run_steps", ["run_id"], unique=False)

    op.create_table(
        "conversation_messages",
        sa.Column("message_id", sa.String(length=40), nullable=False),
        sa.Column("project_id", sa.String(length=40), nullable=False),
        sa.Column("conversation_id", sa.String(length=40), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("message_id"),
    )
    op.create_index("ix_conversation_messages_project_id", "conversation_messages", ["project_id"], unique=False)
    op.create_index("ix_conversation_messages_conversation_id", "conversation_messages", ["conversation_id"], unique=False)

    op.create_table(
        "source_files",
        sa.Column("file_id", sa.String(length=40), nullable=False),
        sa.Column("project_id", sa.String(length=40), nullable=False),
        sa.Column("purpose", sa.String(length=80), nullable=False),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=True),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("file_id"),
    )
    op.create_index("ix_source_files_project_id", "source_files", ["project_id"], unique=False)

    op.create_table(
        "developer_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=40), nullable=True),
        sa.Column("project_id", sa.String(length=40), nullable=True),
        sa.Column("step_type", sa.String(length=80), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_developer_logs_run_id", "developer_logs", ["run_id"], unique=False)
    op.create_index("ix_developer_logs_project_id", "developer_logs", ["project_id"], unique=False)

    with op.batch_alter_table("auth_sessions") as batch:
        batch.alter_column("expires_at", server_default=None)
    with op.batch_alter_table("projects") as batch:
        batch.alter_column("style_locked", server_default=None)
    with op.batch_alter_table("scene_plans") as batch:
        batch.alter_column("version_number", server_default=None)
        batch.alter_column("is_current", server_default=None)
    with op.batch_alter_table("script_versions") as batch:
        batch.alter_column("version_number", server_default=None)
        batch.alter_column("is_current", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_developer_logs_project_id", table_name="developer_logs")
    op.drop_index("ix_developer_logs_run_id", table_name="developer_logs")
    op.drop_table("developer_logs")
    op.drop_index("ix_source_files_project_id", table_name="source_files")
    op.drop_table("source_files")
    op.drop_index("ix_conversation_messages_conversation_id", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_project_id", table_name="conversation_messages")
    op.drop_table("conversation_messages")
    op.drop_index("ix_agent_run_steps_run_id", table_name="agent_run_steps")
    op.drop_index("ix_agent_run_steps_project_id", table_name="agent_run_steps")
    op.drop_table("agent_run_steps")
    op.drop_index("ix_agent_runs_project_id", table_name="agent_runs")
    op.drop_table("agent_runs")

    with op.batch_alter_table("script_versions") as batch:
        batch.drop_constraint("uq_script_versions_project_version", type_="unique")
        batch.drop_column("stale_reason")
        batch.drop_column("parent_script_version_id")
        batch.drop_column("is_current")
        batch.drop_column("version_number")
        batch.create_unique_constraint("uq_script_versions_project_status", ["project_id", "status"])

    with op.batch_alter_table("scene_plans") as batch:
        batch.drop_constraint("uq_scene_plans_project_version", type_="unique")
        batch.drop_column("stale_reason")
        batch.drop_column("parent_scene_plan_id")
        batch.drop_column("is_current")
        batch.drop_column("version_number")
        batch.create_unique_constraint("uq_scene_plans_project_status", ["project_id", "status"])

    op.drop_column("projects", "style_locked")
    op.drop_column("auth_sessions", "revoked_at")
    op.drop_column("auth_sessions", "expires_at")
