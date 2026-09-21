"""Add channel_userbots and userbot_login_attempts tables

Revision ID: a82d91c73b0f
Revises: f59d4ce2b11e
Create Date: 2026-09-21 17:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a82d91c73b0f'
down_revision: Union[str, Sequence[str], None] = 'f59d4ce2b11e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. channel_userbots
    op.create_table(
        'channel_userbots',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('channel_id', sa.String(length=36), nullable=False),
        sa.Column('api_id', sa.Integer(), nullable=False),
        sa.Column('api_hash', sa.String(length=64), nullable=False),
        sa.Column('phone', sa.String(length=32), nullable=False),
        sa.Column('string_session', sa.Text(), nullable=False),
        sa.Column('telegram_user_id', sa.String(length=64), nullable=True),
        sa.Column('username', sa.String(length=128), nullable=True),
        sa.Column('first_name', sa.String(length=128), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=True),
        sa.Column('status', sa.String(length=32), server_default='CONNECTED', nullable=True),
        sa.Column('daily_contacts_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('last_contact_date', sa.Date(), nullable=True),
        sa.Column('cooldown_until', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.String(length=256), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('channel_id', name='uq_channel_userbot_channel')
    )
    op.create_index('idx_channel_userbot_tenant_chan', 'channel_userbots', ['tenant_id', 'channel_id'], unique=False)

    # 2. userbot_login_attempts
    op.create_table(
        'userbot_login_attempts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('channel_id', sa.String(length=36), nullable=False),
        sa.Column('api_id', sa.Integer(), nullable=False),
        sa.Column('api_hash', sa.String(length=64), nullable=False),
        sa.Column('phone', sa.String(length=32), nullable=False),
        sa.Column('phone_code_hash', sa.String(length=128), nullable=False),
        sa.Column('temp_session_str', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_login_attempt_chan_exp', 'userbot_login_attempts', ['channel_id', 'expires_at'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_login_attempt_chan_exp', table_name='userbot_login_attempts')
    op.drop_table('userbot_login_attempts')
    op.drop_index('idx_channel_userbot_tenant_chan', table_name='channel_userbots')
    op.drop_table('channel_userbots')
