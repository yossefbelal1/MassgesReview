"""Add lease columns and worker heartbeats

Revision ID: 1aa1fe3b6c8c
Revises: d37b2af3b40f
Create Date: 2026-08-28 04:00:46.525099

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1aa1fe3b6c8c'
down_revision: Union[str, Sequence[str], None] = 'd37b2af3b40f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Add worker_heartbeats table and lease columns to jobs table."""
    # 1. Create worker_heartbeats table
    op.create_table(
        'worker_heartbeats',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('worker_id', sa.String(), nullable=False),
        sa.Column('hostname', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('last_heartbeat_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_worker_heartbeats_worker_id'), 'worker_heartbeats', ['worker_id'], unique=True)

    # 2. Add lease columns to jobs table using batch mode for SQLite compatibility
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('lease_owner', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('lease_expires_at', sa.DateTime(), nullable=True))
        batch_op.create_index('idx_job_lease', ['status', 'lease_expires_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema: Remove lease columns/index from jobs and drop worker_heartbeats table."""
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_index('idx_job_lease')
        batch_op.drop_column('lease_expires_at')
        batch_op.drop_column('lease_owner')

    op.drop_index(op.f('ix_worker_heartbeats_worker_id'), table_name='worker_heartbeats')
    op.drop_table('worker_heartbeats')
