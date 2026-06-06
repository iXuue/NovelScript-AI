"""create users auth sessions and project owner

Revision ID: c9a8b7d6e5f4
Revises: 04b44182e7f2
Create Date: 2026-06-06 12:24:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c9a8b7d6e5f4"
down_revision: str | Sequence[str] | None = "04b44182e7f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("login_id", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=128), nullable=False),
        sa.Column("password_salt", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("login_id", name="uq_users_login_id"),
    )
    op.create_index("ix_users_login_id", "users", ["login_id"], unique=False)

    op.create_table(
        "auth_sessions",
        sa.Column("session_id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id"),
        sa.UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
    )
    op.create_index("ix_auth_sessions_token_hash", "auth_sessions", ["token_hash"], unique=False)

    op.add_column("projects", sa.Column("user_id", sa.String(length=40), nullable=True))
    op.create_index("ix_projects_user_id", "projects", ["user_id"], unique=False)
    op.create_foreign_key(
        "fk_projects_user_id_users",
        "projects",
        "users",
        ["user_id"],
        ["user_id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_projects_user_id_users", "projects", type_="foreignkey")
    op.drop_index("ix_projects_user_id", table_name="projects")
    op.drop_column("projects", "user_id")
    op.drop_index("ix_auth_sessions_token_hash", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_users_login_id", table_name="users")
    op.drop_table("users")
