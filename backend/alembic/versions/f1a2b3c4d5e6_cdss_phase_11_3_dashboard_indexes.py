"""cdss_phase_11_3_dashboard_indexes

Revision ID: f1a2b3c4d5e6
Revises: e1f2a3b4c5d6
Create Date: 2026-11-02 23:35:00.000000

Phase 11.3: Clinical Intelligence Validation, Explainable AI & Advanced Safety Monitoring
- Adds composite index 'ix_cdss_safety_hospital_action' on cdss_safety_events (hospital_id, action_taken)
- Adds index 'ix_cdss_safety_created_at' on cdss_safety_events (created_at)
- Adds index 'ix_cdss_feedback_created_at' on cdss_clinician_feedback (created_at)
- Fully additive, idempotent, and reversible via downgrade().
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    if "cdss_safety_events" in existing_tables:
        existing_indexes = {ix["name"] for ix in insp.get_indexes("cdss_safety_events")}
        if "ix_cdss_safety_hospital_action" not in existing_indexes:
            op.create_index(
                "ix_cdss_safety_hospital_action",
                "cdss_safety_events",
                ["hospital_id", "action_taken"],
            )
        if "ix_cdss_safety_created_at" not in existing_indexes:
            op.create_index(
                "ix_cdss_safety_created_at",
                "cdss_safety_events",
                ["created_at"],
            )

    if "cdss_clinician_feedback" in existing_tables:
        existing_indexes = {ix["name"] for ix in insp.get_indexes("cdss_clinician_feedback")}
        if "ix_cdss_feedback_created_at" not in existing_indexes:
            op.create_index(
                "ix_cdss_feedback_created_at",
                "cdss_clinician_feedback",
                ["created_at"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())

    if "cdss_safety_events" in existing_tables:
        existing_indexes = {ix["name"] for ix in insp.get_indexes("cdss_safety_events")}
        if "ix_cdss_safety_hospital_action" in existing_indexes:
            op.drop_index("ix_cdss_safety_hospital_action", table_name="cdss_safety_events")
        if "ix_cdss_safety_created_at" in existing_indexes:
            op.drop_index("ix_cdss_safety_created_at", table_name="cdss_safety_events")

    if "cdss_clinician_feedback" in existing_tables:
        existing_indexes = {ix["name"] for ix in insp.get_indexes("cdss_clinician_feedback")}
        if "ix_cdss_feedback_created_at" in existing_indexes:
            op.drop_index("ix_cdss_feedback_created_at", table_name="cdss_clinician_feedback")

