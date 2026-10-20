"""add_user_hospital_affiliation

Revision ID: 63b2c1f9d5e2
Revises: 52a1b9e8c4d1
Create Date: 2026-10-20 12:15:00.000000

Phase 5.5: Security & Integrity Remediation
- Add nullable foreign key 'hospital_id' on 'users' referencing 'hospitals.id' (ON DELETE SET NULL).
- Add index 'ix_users_hospital_id' on 'users.hospital_id'.
- Enables persistent, authoritative database affiliation for hospital administrators.
- Supports complete downgrade with clean drop of index, foreign key, and column.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '63b2c1f9d5e2'
down_revision: Union[str, Sequence[str], None] = '52a1b9e8c4d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add hospital_id column to users as nullable UUID
    op.add_column(
        'users',
        sa.Column('hospital_id', postgresql.UUID(as_uuid=True), nullable=True),
    )

    # 2. Add foreign key constraint referencing hospitals.id
    op.create_foreign_key(
        'fk_users_hospital_id_hospitals',
        'users',
        'hospitals',
        ['hospital_id'],
        ['id'],
        ondelete='SET NULL',
    )

    # 3. Add non-unique index on hospital_id for performant lookups
    op.create_index(
        'ix_users_hospital_id',
        'users',
        ['hospital_id'],
        unique=False,
    )


def downgrade() -> None:
    # 1. Drop index
    op.drop_index('ix_users_hospital_id', table_name='users')

    # 2. Drop foreign key constraint
    op.drop_constraint('fk_users_hospital_id_hospitals', 'users', type_='foreignkey')

    # 3. Drop column
    op.drop_column('users', 'hospital_id')
