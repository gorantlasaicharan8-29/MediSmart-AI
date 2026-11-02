"""cdss_safety_monitoring_and_feedback

Revision ID: e1f2a3b4c5d6
Revises: d1e2f3a4b5c6
Create Date: 2026-11-02 22:30:00.000000

Phase 11.2: Clinical Governance, Real-World Validation & Safety Monitoring
- Creates 'cdss_safety_events' table for tracking warning generation, severity, category, acknowledgement, and dismissal.
- Creates 'cdss_clinician_feedback' table for physician feedback on interaction rules, guidelines, and symptom extractions.
- Fully additive, idempotent, and reversible via downgrade().
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    # 1. Create cdss_safety_events table if not exists
    if 'cdss_safety_events' not in existing_tables:
        op.create_table(
            'cdss_safety_events',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('appointment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('appointments.id', ondelete='SET NULL'), nullable=True),
            sa.Column('doctor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('doctors.id', ondelete='SET NULL'), nullable=True),
            sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('hospital_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('hospitals.id', ondelete='SET NULL'), nullable=True),
            sa.Column('kb_version', sa.String(length=50), nullable=False),
            sa.Column('warning_category', sa.String(length=50), nullable=False),
            sa.Column('warning_severity', sa.String(length=30), nullable=False),
            sa.Column('rule_identifier', sa.String(length=100), nullable=True),
            sa.Column('alert_summary', sa.Text(), nullable=False),
            sa.Column('action_taken', sa.String(length=30), server_default='GENERATED', nullable=False),
            sa.Column('dismissal_reason', sa.Text(), nullable=True),
            sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        )
        op.create_index('ix_cdss_safety_doctor_time', 'cdss_safety_events', ['doctor_id', 'created_at'])
        op.create_index('ix_cdss_safety_appointment', 'cdss_safety_events', ['appointment_id'])
        op.create_index('ix_cdss_safety_severity', 'cdss_safety_events', ['warning_severity'])
        op.create_index('ix_cdss_safety_category', 'cdss_safety_events', ['warning_category'])
        op.create_index('ix_cdss_safety_rule', 'cdss_safety_events', ['rule_identifier'])

    # 2. Create cdss_clinician_feedback table if not exists
    if 'cdss_clinician_feedback' not in existing_tables:
        op.create_table(
            'cdss_clinician_feedback',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('doctor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False),
            sa.Column('appointment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('appointments.id', ondelete='SET NULL'), nullable=True),
            sa.Column('feedback_type', sa.String(length=60), nullable=False),
            sa.Column('target_type', sa.String(length=50), nullable=False),
            sa.Column('target_id', sa.String(length=100), nullable=True),
            sa.Column('kb_version', sa.String(length=50), nullable=False),
            sa.Column('clinician_comment', sa.Text(), nullable=False),
            sa.Column('review_status', sa.String(length=40), server_default='PENDING_REVIEW', nullable=False),
            sa.Column('reviewed_by', sa.String(length=255), nullable=True),
            sa.Column('resolution_notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        )
        op.create_index('ix_cdss_feedback_doctor_time', 'cdss_clinician_feedback', ['doctor_id', 'created_at'])
        op.create_index('ix_cdss_feedback_type', 'cdss_clinician_feedback', ['feedback_type'])
        op.create_index('ix_cdss_feedback_target', 'cdss_clinician_feedback', ['target_type', 'target_id'])
        op.create_index('ix_cdss_feedback_status', 'cdss_clinician_feedback', ['review_status'])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    if 'cdss_clinician_feedback' in existing_tables:
        op.drop_table('cdss_clinician_feedback')

    if 'cdss_safety_events' in existing_tables:
        op.drop_table('cdss_safety_events')

