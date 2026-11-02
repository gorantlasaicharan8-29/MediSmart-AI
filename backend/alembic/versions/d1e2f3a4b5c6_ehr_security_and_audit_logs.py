"""ehr_security_and_audit_logs

Revision ID: d1e2f3a4b5c6
Revises: c1d2e3f4a5b6
Create Date: 2026-10-30 16:30:00.000000

Phase 10.1: EHR Security, Data Integrity, and Clinical Audit Trail
- Creates 'clinical_audit_logs' table for HIPAA/GDPR clinical audit logging.
- Adds 'superseded_by_id', 'amendment_reason', and 'version' columns to 'prescriptions' table for immutable prescription amendments.
- All foreign keys include ON DELETE SET NULL for audit retention.
- Fully additive and cleanly reversible via downgrade().
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    # 1. Add prescription amendment columns if prescriptions table exists
    if 'prescriptions' in existing_tables:
        rx_cols = {c['name'] for c in insp.get_columns('prescriptions')}
        if 'version' not in rx_cols:
            op.add_column('prescriptions', sa.Column('version', sa.Integer(), server_default='1', nullable=False))
        if 'amendment_reason' not in rx_cols:
            op.add_column('prescriptions', sa.Column('amendment_reason', sa.Text(), nullable=True))
        if 'superseded_by_id' not in rx_cols:
            op.add_column(
                'prescriptions',
                sa.Column(
                    'superseded_by_id',
                    postgresql.UUID(as_uuid=True),
                    sa.ForeignKey('prescriptions.id', ondelete='SET NULL'),
                    nullable=True,
                ),
            )

    # 2. Create clinical_audit_logs table if not exists
    if 'clinical_audit_logs' not in existing_tables:
        op.create_table(
            'clinical_audit_logs',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('actor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('actor_role', sa.String(length=50), nullable=False),
            sa.Column('actor_email', sa.String(length=255), nullable=True),
            sa.Column('action', sa.String(length=60), nullable=False),
            sa.Column('target_type', sa.String(length=50), nullable=False),
            sa.Column('target_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('doctor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('doctors.id', ondelete='SET NULL'), nullable=True),
            sa.Column('hospital_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('hospitals.id', ondelete='SET NULL'), nullable=True),
            sa.Column('ip_address', sa.String(length=45), nullable=True),
            sa.Column('user_agent', sa.String(length=255), nullable=True),
            sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        )
        op.create_index('ix_clinical_audit_actor_time', 'clinical_audit_logs', ['actor_id', 'created_at'])
        op.create_index('ix_clinical_audit_patient_time', 'clinical_audit_logs', ['patient_id', 'created_at'])
        op.create_index('ix_clinical_audit_action_time', 'clinical_audit_logs', ['action', 'created_at'])
        op.create_index('ix_clinical_audit_target', 'clinical_audit_logs', ['target_type', 'target_id'])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    if 'clinical_audit_logs' in existing_tables:
        op.drop_table('clinical_audit_logs')

    if 'prescriptions' in existing_tables:
        rx_cols = {c['name'] for c in insp.get_columns('prescriptions')}
        if 'superseded_by_id' in rx_cols:
            op.drop_column('prescriptions', 'superseded_by_id')
        if 'amendment_reason' in rx_cols:
            op.drop_column('prescriptions', 'amendment_reason')
        if 'version' in rx_cols:
            op.drop_column('prescriptions', 'version')

