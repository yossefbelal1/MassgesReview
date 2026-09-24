"""Add membership_state projection and channel health tracking

Revision ID: c1928374d5ef
Revises: b291c94d1f2a
Create Date: 2026-09-24 03:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1928374d5ef'
down_revision: Union[str, Sequence[str], None] = 'b291c94d1f2a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add health tracking columns to channels
    op.add_column('channels', sa.Column('health_state', sa.String(length=32), server_default='HEALTHY', nullable=True))
    op.add_column('channels', sa.Column('consecutive_errors', sa.Integer(), server_default='0', nullable=True))
    op.add_column('channels', sa.Column('last_event_at', sa.DateTime(), nullable=True))
    op.add_column('channels', sa.Column('last_error_at', sa.DateTime(), nullable=True))
    op.add_column('channels', sa.Column('last_success_at', sa.DateTime(), nullable=True))

    # 2. Add via_join_request to membership_events
    op.add_column('membership_events', sa.Column('via_join_request', sa.Boolean(), server_default=sa.text('false'), nullable=True))
    try:
        op.create_unique_constraint(
            'uq_member_event_idempotent',
            'membership_events',
            ['channel_id', 'telegram_user_id', 'timestamp', 'event_type']
        )
    except Exception:
        pass

    # 3. Create membership_state table
    op.create_table(
        'membership_state',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('tenant_id', sa.String(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('channel_id', sa.String(), sa.ForeignKey('channels.id', ondelete='CASCADE'), nullable=False),
        sa.Column('telegram_user_id', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='member', nullable=True),
        sa.Column('first_join', sa.DateTime(), nullable=True),
        sa.Column('last_join', sa.DateTime(), nullable=True),
        sa.Column('last_leave', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('channel_id', 'telegram_user_id', name='uq_channel_tg_state')
    )
    op.create_index('idx_state_tg_user', 'membership_state', ['telegram_user_id'], unique=False)
    op.create_index('idx_state_tenant_channel_status', 'membership_state', ['tenant_id', 'channel_id', 'status'], unique=False)


def downgrade() -> None:
    # 3. Drop membership_state table
    op.drop_index('idx_state_tenant_channel_status', table_name='membership_state')
    op.drop_index('idx_state_tg_user', table_name='membership_state')
    op.drop_table('membership_state')

    # 2. Drop constraint and column from membership_events
    try:
        op.drop_constraint('uq_member_event_idempotent', 'membership_events', type_='unique')
    except Exception:
        pass
    op.drop_column('membership_events', 'via_join_request')

    # 1. Drop health columns from channels
    op.drop_column('channels', 'last_success_at')
    op.drop_column('channels', 'last_error_at')
    op.drop_column('channels', 'last_event_at')
    op.drop_column('channels', 'consecutive_errors')
    op.drop_column('channels', 'health_state')
