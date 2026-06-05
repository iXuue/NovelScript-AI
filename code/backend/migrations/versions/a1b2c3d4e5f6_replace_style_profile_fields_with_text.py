"""replace structured style profile fields with profile_text

Revision ID: a1b2c3d4e5f6
Revises: d476da1604e5
Create Date: 2026-06-05 19:45:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: str | Sequence[str] | None = 'd476da1604e5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column('style_profiles', 'script_type')
    op.drop_column('style_profiles', 'dialogue_density')
    op.drop_column('style_profiles', 'scene_length')
    op.drop_column('style_profiles', 'pacing')
    op.drop_column('style_profiles', 'character_voice')
    op.drop_column('style_profiles', 'conflict_design')
    op.drop_column('style_profiles', 'narration_ratio')
    op.drop_column('style_profiles', 'action_ratio')
    op.drop_column('style_profiles', 'transitions')
    op.drop_column('style_profiles', 'user_preferences')
    op.add_column('style_profiles', sa.Column('profile_text', sa.Text(), nullable=False, server_default=''))


def downgrade() -> None:
    op.drop_column('style_profiles', 'profile_text')
    op.add_column('style_profiles', sa.Column('script_type', sa.String(length=120), nullable=False, server_default=''))
    op.add_column('style_profiles', sa.Column('dialogue_density', sa.String(length=80), nullable=False, server_default=''))
    op.add_column('style_profiles', sa.Column('scene_length', sa.String(length=80), nullable=False, server_default=''))
    op.add_column('style_profiles', sa.Column('pacing', sa.String(length=80), nullable=False, server_default=''))
    op.add_column('style_profiles', sa.Column('character_voice', sa.Text(), nullable=False, server_default=''))
    op.add_column('style_profiles', sa.Column('conflict_design', sa.Text(), nullable=False, server_default=''))
    op.add_column('style_profiles', sa.Column('narration_ratio', sa.String(length=80), nullable=False, server_default=''))
    op.add_column('style_profiles', sa.Column('action_ratio', sa.String(length=80), nullable=False, server_default=''))
    op.add_column('style_profiles', sa.Column('transitions', sa.JSON(), nullable=False, server_default='[]'))
    op.add_column('style_profiles', sa.Column('user_preferences', sa.JSON(), nullable=False, server_default='[]'))
