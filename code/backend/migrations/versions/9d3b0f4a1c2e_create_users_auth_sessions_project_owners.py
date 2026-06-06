"""create users auth sessions project owners

Revision ID: 9d3b0f4a1c2e
Revises: bda0f715280e
Create Date: 2026-06-06 14:30:00.000000

"""
from collections.abc import Sequence
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision: str = "9d3b0f4a1c2e"
down_revision: str | Sequence[str] | None = "bda0f715280e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_USER_ID = "user_legacy"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("login_id", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("password_salt", sa.String(length=255), nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], name="fk_auth_sessions_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id"),
        sa.UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"], unique=False)

    op.add_column("projects", sa.Column("user_id", sa.String(length=40), nullable=True))
    users_table = sa.table(
        "users",
        sa.column("user_id", sa.String(length=40)),
        sa.column("login_id", sa.String(length=255)),
        sa.column("password_hash", sa.String(length=255)),
        sa.column("password_salt", sa.String(length=255)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(
        users_table,
        [
            {
                "user_id": LEGACY_USER_ID,
                "login_id": "legacy",
                "password_hash": "legacy-disabled",
                "password_salt": "legacy-disabled",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    op.execute(sa.text("UPDATE projects SET user_id = :user_id WHERE user_id IS NULL").bindparams(user_id=LEGACY_USER_ID))
    op.alter_column("projects", "user_id", existing_type=sa.String(length=40), nullable=False)
    op.create_index("ix_projects_user_id", "projects", ["user_id"], unique=False)
    op.create_foreign_key("fk_projects_user_id_users", "projects", "users", ["user_id"], ["user_id"], ondelete="CASCADE")


def downgrade() -> None:
    op.drop_constraint("fk_projects_user_id_users", "projects", type_="foreignkey")
    op.drop_index("ix_projects_user_id", table_name="projects")
    op.drop_column("projects", "user_id")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_users_login_id", table_name="users")
    op.drop_table("users")
