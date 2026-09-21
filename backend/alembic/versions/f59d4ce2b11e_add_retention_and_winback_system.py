"""Add retention and winback system models and tables

Revision ID: f59d4ce2b11e
Revises: e48c3bf1a99d
Create Date: 2026-09-21 15:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f59d4ce2b11e'
down_revision: Union[str, Sequence[str], None] = 'e48c3bf1a99d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add last_seen_admin_log_id to channels
    with op.batch_alter_table('channels', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_seen_admin_log_id', sa.String(length=64), nullable=True))

    # 2. retention_settings
    op.create_table(
        'retention_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('channel_id', sa.Integer(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), server_default=sa.text('true'), nullable=True),
        sa.Column('outreach_delay_seconds', sa.Integer(), server_default='300', nullable=True),
        sa.Column('mistake_template', sa.Text(), nullable=True),
        sa.Column('too_many_template', sa.Text(), nullable=True),
        sa.Column('content_template', sa.Text(), nullable=True),
        sa.Column('default_template', sa.Text(), nullable=True),
        sa.Column('welcome_enabled', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('welcome_template', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('channel_id')
    )
    op.create_index(op.f('ix_retention_settings_channel_id'), 'retention_settings', ['channel_id'], unique=True)
    op.create_index(op.f('ix_retention_settings_id'), 'retention_settings', ['id'], unique=False)
    op.create_index(op.f('ix_retention_settings_tenant_id'), 'retention_settings', ['tenant_id'], unique=False)

    # 3. audience_members
    op.create_table(
        'audience_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('channel_id', sa.Integer(), nullable=False),
        sa.Column('telegram_user_id', sa.BigInteger(), nullable=False),
        sa.Column('username', sa.String(length=128), nullable=True),
        sa.Column('first_name', sa.String(length=128), nullable=True),
        sa.Column('last_name', sa.String(length=128), nullable=True),
        sa.Column('is_bot', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('status', sa.String(length=32), server_default='ACTIVE', nullable=True),
        sa.Column('first_joined_at', sa.DateTime(), nullable=True),
        sa.Column('last_left_at', sa.DateTime(), nullable=True),
        sa.Column('rejoined_at', sa.DateTime(), nullable=True),
        sa.Column('leave_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('is_contactable', sa.Boolean(), server_default=sa.text('true'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audience_members_channel_id'), 'audience_members', ['channel_id'], unique=False)
    op.create_index(op.f('ix_audience_members_id'), 'audience_members', ['id'], unique=False)
    op.create_index(op.f('ix_audience_members_status'), 'audience_members', ['status'], unique=False)
    op.create_index(op.f('ix_audience_members_telegram_user_id'), 'audience_members', ['telegram_user_id'], unique=False)
    op.create_index(op.f('ix_audience_members_tenant_id'), 'audience_members', ['tenant_id'], unique=False)

    # 4. recovery_cases
    op.create_table(
        'recovery_cases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('channel_id', sa.Integer(), nullable=False),
        sa.Column('audience_member_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='PENDING', nullable=True),
        sa.Column('assigned_userbot', sa.String(length=64), nullable=True),
        sa.Column('left_at', sa.DateTime(), nullable=True),
        sa.Column('scheduled_contact_at', sa.DateTime(), nullable=True),
        sa.Column('first_contact_at', sa.DateTime(), nullable=True),
        sa.Column('recovered_at', sa.DateTime(), nullable=True),
        sa.Column('time_to_rejoin_seconds', sa.Integer(), nullable=True),
        sa.Column('classified_intent', sa.String(length=64), nullable=True),
        sa.Column('intent_confidence', sa.Float(), nullable=True),
        sa.Column('sentiment', sa.String(length=32), nullable=True),
        sa.Column('invite_link_sent', sa.String(length=256), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['audience_member_id'], ['audience_members.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recovery_cases_channel_id'), 'recovery_cases', ['channel_id'], unique=False)
    op.create_index(op.f('ix_recovery_cases_id'), 'recovery_cases', ['id'], unique=False)
    op.create_index(op.f('ix_recovery_cases_status'), 'recovery_cases', ['status'], unique=False)
    op.create_index(op.f('ix_recovery_cases_tenant_id'), 'recovery_cases', ['tenant_id'], unique=False)

    # 5. recovery_messages
    op.create_table(
        'recovery_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recovery_case_id', sa.Integer(), nullable=False),
        sa.Column('direction', sa.String(length=16), nullable=False),
        sa.Column('sender_name', sa.String(length=64), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('telegram_message_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['recovery_case_id'], ['recovery_cases.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recovery_messages_id'), 'recovery_messages', ['id'], unique=False)
    op.create_index(op.f('ix_recovery_messages_recovery_case_id'), 'recovery_messages', ['recovery_case_id'], unique=False)


def downgrade() -> None:
    op.drop_table('recovery_messages')
    op.drop_table('recovery_cases')
    op.drop_table('audience_members')
    op.drop_table('retention_settings')
    with op.batch_alter_table('channels', schema=None) as batch_op:
        batch_op.drop_column('last_seen_admin_log_id')
