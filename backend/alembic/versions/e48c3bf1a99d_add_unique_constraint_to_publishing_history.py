"""Add unique constraint to publishing_history

Revision ID: e48c3bf1a99d
Revises: 1aa1fe3b6c8c
Create Date: 2026-08-28 05:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e48c3bf1a99d'
down_revision: Union[str, Sequence[str], None] = '1aa1fe3b6c8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Add unique constraint on (job_id, step_number) in publishing_history."""
    with op.batch_alter_table('publishing_history', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_publishing_history_job_step', ['job_id', 'step_number'])


def downgrade() -> None:
    """Downgrade schema: Drop unique constraint on (job_id, step_number)."""
    with op.batch_alter_table('publishing_history', schema=None) as batch_op:
        batch_op.drop_constraint('uq_publishing_history_job_step', type_='unique')
