"""create_notifications_table

Revision ID: a7c8e91f0d32
Revises: 63b2c1f9d5e2
Create Date: 2026-10-26 22:25:00.000000

Phase 6.2: Notification Data Layer
- Creates additive 'notifications' table for patient/provider in-app updates.
- Links to 'users.id' with ON DELETE CASCADE.
- Adds composite index 'ix_notifications_user_read_created' for efficient unread queries and pagination.
- Adds partial unique index 'uq_user_notification_idempotency' on (user_id, idempotency_key)
  preventing duplicate notifications when an idempotency key is supplied.
- Fully additive and cleanly reversible via downgrade().
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a7c8e91f0d32'
down_revision: Union[str, Sequence[str], None] = '63b2c1f9d5e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('category', sa.String(length=30), nullable=False, server_default='appointment'),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('urgency', sa.String(length=20), nullable=False, server_default='normal'),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('idempotency_key', sa.String(length=100), nullable=True),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # 2. Foreign key user_id single column index
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'])

    # 3. Composite index for user unread counts and chronological retrieval
    op.create_index(
        'ix_notifications_user_read_created',
        'notifications',
        ['user_id', 'is_read', 'created_at'],
    )

    # 4. Partial unique index for duplicate prevention when idempotency_key is provided
    op.create_index(
        'uq_user_notification_idempotency',
        'notifications',
        ['user_id', 'idempotency_key'],
        unique=True,
        postgresql_where=sa.text('idempotency_key IS NOT NULL'),
    )


def downgrade() -> None:
    # 1. Drop partial unique index
    op.drop_index(
        'uq_user_notification_idempotency',
        table_name='notifications',
        postgresql_where=sa.text('idempotency_key IS NOT NULL'),
    )

    # 2. Drop composite index
    op.drop_index('ix_notifications_user_read_created', table_name='notifications')

    # 3. Drop single column user_id index
    op.drop_index('ix_notifications_user_id', table_name='notifications')

    # 4. Drop table
    op.drop_table('notifications')
