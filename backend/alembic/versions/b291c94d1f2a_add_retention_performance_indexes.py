"""Add retention performance indexes and channel sync tracking

Revision ID: b291c94d1f2a
Revises: a82d91c73b0f
Create Date: 2026-09-22 21:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b291c94d1f2a'
down_revision: Union[str, Sequence[str], None] = 'a82d91c73b0f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add sync tracking columns to channels
    op.add_column('channels', sa.Column('last_admin_log_sync_at', sa.DateTime(), nullable=True))
    op.add_column('channels', sa.Column('sync_status', sa.String(length=32), server_default='ACTIVE', nullable=True))

    # 2. Add composite index on recovery_cases for high-frequency worker dispatch
    op.create_index(
        'idx_case_status_scheduled',
        'recovery_cases',
        ['status', 'scheduled_contact_at'],
        unique=False
    )


def downgrade() -> None:
    # 1. Drop composite index
    op.drop_index('idx_case_status_scheduled', table_name='recovery_cases')

    # 2. Drop sync tracking columns
    op.drop_column('channels', 'sync_status')
    op.drop_column('channels', 'last_admin_log_sync_at')
