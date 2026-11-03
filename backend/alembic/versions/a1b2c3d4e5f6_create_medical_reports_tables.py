"""create_medical_reports_tables

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-11-03 23:55:00.000000

Phase 12.0: AI Medical Report Analysis & Intelligent Health Document Understanding
- Creates medical_documents table
- Creates medical_report_analyses table
- Creates extracted_medical_parameters table
- Creates medical_parameter_corrections table
- Creates medical_report_reviews table
- Fully additive, idempotent, and reversible via downgrade().
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    # 1. medical_documents
    if "medical_documents" not in existing_tables:
        op.create_table(
            "medical_documents",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("original_filename", sa.String(255), nullable=False),
            sa.Column("stored_filename", sa.String(255), nullable=False, unique=True),
            sa.Column("mime_type", sa.String(100), nullable=False, server_default="application/pdf"),
            sa.Column("file_size_bytes", sa.Integer(), nullable=False),
            sa.Column("sha256_hash", sa.String(64), nullable=False),
            sa.Column("document_category", sa.String(100), nullable=False, server_default="Other Medical Reports"),
            sa.Column("confirmed_category", sa.String(100), nullable=True),
            sa.Column("report_date", sa.Date(), nullable=True),
            sa.Column("processing_status", sa.String(50), nullable=False, server_default="PENDING"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_medical_documents_patient_id", "medical_documents", ["patient_id"])
        op.create_index("ix_medical_documents_sha256_hash", "medical_documents", ["sha256_hash"])
        op.create_index("ix_medical_documents_processing_status", "medical_documents", ["processing_status"])
        op.create_index("ix_medical_documents_is_deleted", "medical_documents", ["is_deleted"])
        op.create_index("ix_med_docs_patient_created", "medical_documents", ["patient_id", "created_at"])
        op.create_index("ix_med_docs_patient_hash", "medical_documents", ["patient_id", "sha256_hash"])

    # 2. medical_report_analyses
    if "medical_report_analyses" not in existing_tables:
        op.create_table(
            "medical_report_analyses",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("medical_documents.id", ondelete="CASCADE"), nullable=False),
            sa.Column("extraction_engine_version", sa.String(50), nullable=False, server_default="12.0.0-pymupdf-rapidocr"),
            sa.Column("analysis_status", sa.String(50), nullable=False, server_default="SUCCESS"),
            sa.Column("total_pages", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("ocr_applied_pages", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("raw_text_preview", sa.Text(), nullable=True),
            sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("extraction_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_medical_report_analyses_document_id", "medical_report_analyses", ["document_id"])

    # 3. extracted_medical_parameters
    if "extracted_medical_parameters" not in existing_tables:
        op.create_table(
            "extracted_medical_parameters",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("analysis_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("medical_report_analyses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("parameter_name", sa.String(100), nullable=False),
            sa.Column("canonical_name", sa.String(100), nullable=False),
            sa.Column("category", sa.String(100), nullable=False, server_default="General"),
            sa.Column("extracted_value", sa.String(100), nullable=False),
            sa.Column("numeric_value", sa.Float(), nullable=True),
            sa.Column("original_unit", sa.String(50), nullable=True),
            sa.Column("canonical_unit", sa.String(50), nullable=True),
            sa.Column("reference_range_text", sa.String(150), nullable=True),
            sa.Column("reference_range_low", sa.Float(), nullable=True),
            sa.Column("reference_range_high", sa.Float(), nullable=True),
            sa.Column("range_status", sa.String(50), nullable=False, server_default="REFERENCE_RANGE_NOT_AVAILABLE"),
            sa.Column("is_critical", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("extraction_confidence", sa.Float(), nullable=False, server_default="0.85"),
            sa.Column("source_page", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("source_text_snippet", sa.String(500), nullable=True),
            sa.Column("verification_status", sa.String(50), nullable=False, server_default="UNVERIFIED"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_extracted_medical_parameters_analysis_id", "extracted_medical_parameters", ["analysis_id"])
        op.create_index("ix_extracted_medical_parameters_parameter_name", "extracted_medical_parameters", ["parameter_name"])
        op.create_index("ix_extracted_medical_parameters_canonical_name", "extracted_medical_parameters", ["canonical_name"])
        op.create_index("ix_extracted_medical_parameters_range_status", "extracted_medical_parameters", ["range_status"])

    # 4. medical_parameter_corrections
    if "medical_parameter_corrections" not in existing_tables:
        op.create_table(
            "medical_parameter_corrections",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("parameter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("extracted_medical_parameters.id", ondelete="CASCADE"), nullable=False),
            sa.Column("doctor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("doctors.id", ondelete="SET NULL"), nullable=True),
            sa.Column("doctor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("prior_value", sa.String(100), nullable=False),
            sa.Column("corrected_value", sa.String(100), nullable=False),
            sa.Column("prior_range_status", sa.String(50), nullable=False),
            sa.Column("corrected_range_status", sa.String(50), nullable=False),
            sa.Column("correction_reason", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_med_param_corrections_parameter_id", "medical_parameter_corrections", ["parameter_id"])

    # 5. medical_report_reviews
    if "medical_report_reviews" not in existing_tables:
        op.create_table(
            "medical_report_reviews",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("medical_documents.id", ondelete="CASCADE"), nullable=False),
            sa.Column("doctor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("doctors.id", ondelete="SET NULL"), nullable=True),
            sa.Column("doctor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("review_status", sa.String(50), nullable=False, server_default="REVIEWED"),
            sa.Column("clinical_notes", sa.Text(), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_medical_report_reviews_document_id", "medical_report_reviews", ["document_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    if "medical_report_reviews" in existing_tables:
        op.drop_table("medical_report_reviews")
    if "medical_parameter_corrections" in existing_tables:
        op.drop_table("medical_parameter_corrections")
    if "extracted_medical_parameters" in existing_tables:
        op.drop_table("extracted_medical_parameters")
    if "medical_report_analyses" in existing_tables:
        op.drop_table("medical_report_analyses")
    if "medical_documents" in existing_tables:
        op.drop_table("medical_documents")

