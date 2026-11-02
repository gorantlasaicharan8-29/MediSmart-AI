"""create_clinical_ehr_tables

Revision ID: c1d2e3f4a5b6
Revises: a7c8e91f0d32
Create Date: 2026-10-30 15:45:00.000000

Phase 10: Clinical Consultation Notes and Electronic Health Record (EHR) System
- Creates additive 'consultation_notes' table for physician clinical documentation.
- Creates additive 'diagnoses' table for clinician-entered diagnoses.
- Creates additive 'prescriptions' and 'prescription_items' tables for digital Rx management.
- All foreign keys link to existing 'appointments', 'users', 'doctors', and 'hospitals' tables with ON DELETE CASCADE.
- Fully additive and cleanly reversible via downgrade().
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'a7c8e91f0d32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    # 1. Create consultation_notes table
    if 'consultation_notes' not in existing_tables:
        op.create_table(
            'consultation_notes',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('appointment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('appointments.id', ondelete='CASCADE'), nullable=False, unique=True),
            sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('doctor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False),
            sa.Column('hospital_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('hospitals.id', ondelete='CASCADE'), nullable=False),
            sa.Column('consultation_date', sa.Date(), nullable=False),
            sa.Column('consultation_time', sa.Time(), nullable=False),
            sa.Column('chief_complaint', sa.Text(), nullable=False),
            sa.Column('symptoms', sa.Text(), nullable=True),
            sa.Column('clinical_observations', sa.Text(), nullable=True),
            sa.Column('examination_notes', sa.Text(), nullable=True),
            sa.Column('diagnosis_summary', sa.Text(), nullable=False),
            sa.Column('treatment_plan', sa.Text(), nullable=False),
            sa.Column('doctor_recommendations', sa.Text(), nullable=True),
            sa.Column('follow_up_recommended_date', sa.Date(), nullable=True),
            sa.Column('follow_up_instructions', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        )
        op.create_index('ix_consultation_notes_appointment_id', 'consultation_notes', ['appointment_id'])
        op.create_index('ix_consultation_notes_patient_id', 'consultation_notes', ['patient_id'])
        op.create_index('ix_consultation_notes_doctor_id', 'consultation_notes', ['doctor_id'])
        op.create_index('ix_consultation_notes_hospital_id', 'consultation_notes', ['hospital_id'])
        op.create_index('ix_consultation_notes_patient_date', 'consultation_notes', ['patient_id', 'consultation_date'])
        op.create_index('ix_consultation_notes_doctor_date', 'consultation_notes', ['doctor_id', 'consultation_date'])

    # 2. Create diagnoses table
    if 'diagnoses' not in existing_tables:
        op.create_table(
            'diagnoses',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('consultation_note_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('consultation_notes.id', ondelete='CASCADE'), nullable=False),
            sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('doctor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False),
            sa.Column('diagnosis_name', sa.String(length=255), nullable=False),
            sa.Column('clinical_description', sa.Text(), nullable=True),
            sa.Column('diagnosis_code', sa.String(length=50), nullable=True),
            sa.Column('diagnosis_date', sa.Date(), nullable=False),
            sa.Column('status', sa.String(length=30), server_default='active', nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        )
        op.create_index('ix_diagnoses_consultation_note_id', 'diagnoses', ['consultation_note_id'])
        op.create_index('ix_diagnoses_patient', 'diagnoses', ['patient_id'])
        op.create_index('ix_diagnoses_doctor', 'diagnoses', ['doctor_id'])

    # 3. Create prescriptions table
    if 'prescriptions' not in existing_tables:
        op.create_table(
            'prescriptions',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('prescription_number', sa.String(length=50), unique=True, nullable=False),
            sa.Column('consultation_note_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('consultation_notes.id', ondelete='CASCADE'), nullable=False),
            sa.Column('appointment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('appointments.id', ondelete='CASCADE'), nullable=False),
            sa.Column('patient_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('doctor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False),
            sa.Column('hospital_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('hospitals.id', ondelete='CASCADE'), nullable=False),
            sa.Column('prescription_date', sa.Date(), nullable=False),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        )
        op.create_index('ix_prescriptions_prescription_number', 'prescriptions', ['prescription_number'])
        op.create_index('ix_prescriptions_consultation_note_id', 'prescriptions', ['consultation_note_id'])
        op.create_index('ix_prescriptions_appointment_id', 'prescriptions', ['appointment_id'])
        op.create_index('ix_prescriptions_patient', 'prescriptions', ['patient_id'])
        op.create_index('ix_prescriptions_doctor', 'prescriptions', ['doctor_id'])
        op.create_index('ix_prescriptions_hospital', 'prescriptions', ['hospital_id'])

    # 4. Create prescription_items table
    if 'prescription_items' not in existing_tables:
        op.create_table(
            'prescription_items',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('prescription_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prescriptions.id', ondelete='CASCADE'), nullable=False),
            sa.Column('medication_name', sa.String(length=255), nullable=False),
            sa.Column('dosage', sa.String(length=100), nullable=False),
            sa.Column('frequency', sa.String(length=100), nullable=False),
            sa.Column('duration', sa.String(length=100), nullable=False),
            sa.Column('route', sa.String(length=50), server_default='Oral', nullable=False),
            sa.Column('instructions', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        )
        op.create_index('ix_prescription_items_prescription_id', 'prescription_items', ['prescription_id'])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    if 'prescription_items' in existing_tables:
        op.drop_table('prescription_items')
    if 'prescriptions' in existing_tables:
        op.drop_table('prescriptions')
    if 'diagnoses' in existing_tables:
        op.drop_table('diagnoses')
    if 'consultation_notes' in existing_tables:
        op.drop_table('consultation_notes')
