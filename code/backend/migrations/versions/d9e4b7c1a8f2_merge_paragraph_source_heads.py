"""merge paragraph source heads

Revision ID: d9e4b7c1a8f2
Revises: 7c8d9e0f1234, a7f4c9d2b381
Create Date: 2026-06-06
"""

from collections.abc import Sequence


revision: str = "d9e4b7c1a8f2"
down_revision: str | Sequence[str] | None = ("7c8d9e0f1234", "a7f4c9d2b381")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
