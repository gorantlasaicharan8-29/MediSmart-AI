"""queue_enhancements_and_concurrency

Revision ID: 52a1b9e8c4d1
Revises: 42d65b870a44
Create Date: 2026-10-19 12:45:00.000000

Phase 5.1: Digital Queue & Real-Time Updates
- Pre-backfill validation: verify all existing queue entries have a valid date source
  (appointments.appointment_date or checked_in_at in clinic timezone Asia/Kolkata).
- Abort safely without modifying or deleting data if any record lacks a valid date source.
- Add queue_date as nullable without server default.
- Backfill existing rows using canonical clinic-date policy:
    1. Primary: appointments.appointment_date
    2. Fallback: (checked_in_at AT TIME ZONE 'Asia/Kolkata')::date
- Validate that no rows have queue_date IS NULL before altering to NOT NULL.
- Set server default to CURRENT_DATE after backfilling and validation.
- Add notes (Text, nullable) for clinical/reception annotations.
- Create partial unique index 'uq_active_doctor_in_consultation' enforcing at most one active consultation per doctor per clinic date.
- Create unique constraint 'uq_doctor_date_token_number' enforcing daily token uniqueness per doctor and clinic date.
- Embedded safety pre-checks verify valid statuses, duplicate active consultations, duplicate tokens, and foreign key integrity across appointments, doctors, hospitals, and patients (users).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '52a1b9e8c4d1'
down_revision: Union[str, Sequence[str], None] = '42d65b870a44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema with strict pre-checks and additive concurrency constraints."""
    bind = op.get_bind()

    # =========================================================================
    # Pre-Check 1: Verify allowed queue status values
    # =========================================================================
    status_check_sql = sa.text("SELECT DISTINCT status FROM queue_entries;")
    existing_statuses = [row[0] for row in bind.execute(status_check_sql).fetchall()]
    allowed_statuses = {"waiting", "in_consultation", "completed", "skipped", "cancelled"}
    invalid_statuses = set(existing_statuses) - allowed_statuses
    if invalid_statuses:
        raise RuntimeError(
            f"Migration halted safely: Inconsistent queue status values found in database: {invalid_statuses}. "
            f"Allowed statuses: {allowed_statuses}. Please normalize queue status values before proceeding."
        )

    # =========================================================================
    # Pre-Check 2: Check for existing duplicate active consultations per doctor/date
    # Clinic-Date Policy: Evaluated using appointment_date or checked_in_at in Asia/Kolkata
    # =========================================================================
    dup_consult_sql = sa.text("""
        SELECT q.doctor_id, 
               COALESCE(a.appointment_date, (q.checked_in_at AT TIME ZONE 'Asia/Kolkata')::date) AS clinic_date, 
               COUNT(*) as cnt
        FROM queue_entries q
        LEFT JOIN appointments a ON q.appointment_id = a.id
        WHERE q.status = 'in_consultation'
        GROUP BY q.doctor_id, clinic_date
        HAVING COUNT(*) > 1;
    """)
    duplicate_consults = bind.execute(dup_consult_sql).fetchall()
    if duplicate_consults:
        dup_details = "; ".join(
            [f"doctor_id={d[0]}, clinic_date={d[1]}, active_consultations={d[2]}" for d in duplicate_consults]
        )
        raise RuntimeError(
            f"Migration halted safely: Duplicate active consultations detected in queue_entries: [{dup_details}]. "
            "Cannot create partial unique index 'uq_active_doctor_in_consultation' without causing conflicts. "
            "Please resolve duplicate active consultations before proceeding."
        )

    # =========================================================================
    # Pre-Check 3: Check for duplicate doctor/date/token combinations
    # =========================================================================
    dup_tokens_sql = sa.text("""
        SELECT q.doctor_id, 
               COALESCE(a.appointment_date, (q.checked_in_at AT TIME ZONE 'Asia/Kolkata')::date) AS clinic_date, 
               q.token_number, 
               COUNT(*) as cnt
        FROM queue_entries q
        LEFT JOIN appointments a ON q.appointment_id = a.id
        GROUP BY q.doctor_id, clinic_date, q.token_number
        HAVING COUNT(*) > 1;
    """)
    duplicate_tokens = bind.execute(dup_tokens_sql).fetchall()
    if duplicate_tokens:
        dup_token_details = "; ".join(
            [f"doctor_id={d[0]}, clinic_date={d[1]}, token_number={d[2]}, count={d[3]}" for d in duplicate_tokens]
        )
        raise RuntimeError(
            f"Migration halted safely: Duplicate doctor/date/token combinations detected in queue_entries: [{dup_token_details}]. "
            "Cannot create unique constraint 'uq_doctor_date_token_number'. "
            "Please resolve duplicate tokens before proceeding."
        )

    # =========================================================================
    # Pre-Check 4: Foreign Key Integrity (Appointments, Doctors, Hospitals, Patients)
    # =========================================================================
    fk_checks = [
        ("appointments", "appointment_id", "id", "appointments"),
        ("doctors", "doctor_id", "id", "doctors"),
        ("hospitals", "hospital_id", "id", "hospitals"),
        ("patients (users)", "patient_id", "id", "users"),
    ]
    for label, fk_col, target_col, target_table in fk_checks:
        check_sql = sa.text(f"""
            SELECT COUNT(*) FROM queue_entries q
            LEFT JOIN {target_table} t ON q.{fk_col} = t.{target_col}
            WHERE t.{target_col} IS NULL;
        """)
        orphans = bind.execute(check_sql).scalar()
        if orphans and orphans > 0:
            raise RuntimeError(
                f"Migration halted safely: Found {orphans} orphaned queue_entries records "
                f"with invalid {label} reference ({fk_col} -> {target_table}.{target_col}). "
                "Aborting migration without modifying or deleting data."
            )

    # =========================================================================
    # Pre-Check 5: Historical Date Source Validity (Before Schema Modifications)
    # Ensure every existing record has at least one valid date source.
    # =========================================================================
    undated_records_sql = sa.text("""
        SELECT q.id, q.appointment_id 
        FROM queue_entries q
        LEFT JOIN appointments a ON q.appointment_id = a.id
        WHERE a.appointment_date IS NULL AND q.checked_in_at IS NULL;
    """)
    undated_records = bind.execute(undated_records_sql).fetchall()
    if undated_records:
        undated_details = "; ".join([f"id={r[0]}, appointment_id={r[1]}" for r in undated_records])
        raise RuntimeError(
            f"Migration halted safely: Detected {len(undated_records)} queue_entries records without a valid clinic date source "
            f"(both appointments.appointment_date and checked_in_at are NULL): [{undated_details}]. "
            "Cannot determine historical clinic date without inventing data. "
            "Aborting migration without modifying or deleting data."
        )

    # =========================================================================
    # Additive Schema Changes
    # =========================================================================
    # Step 1: Add queue_date as nullable without server default
    op.add_column(
        'queue_entries',
        sa.Column('queue_date', sa.Date(), nullable=True),
    )

    # Step 2: Backfill existing rows using documented clinic-date policy
    # 1. Primary: appointments.appointment_date
    # 2. Fallback: (checked_in_at AT TIME ZONE 'Asia/Kolkata')::date
    bind.execute(sa.text("""
        UPDATE queue_entries q
        SET queue_date = COALESCE(
            a.appointment_date, 
            (q.checked_in_at AT TIME ZONE 'Asia/Kolkata')::date
        )
        FROM appointments a
        WHERE q.appointment_id = a.id AND q.queue_date IS NULL;
    """))
    bind.execute(sa.text("""
        UPDATE queue_entries q
        SET queue_date = (q.checked_in_at AT TIME ZONE 'Asia/Kolkata')::date
        WHERE q.queue_date IS NULL AND q.checked_in_at IS NOT NULL;
    """))

    # Step 3: Verify that no rows remain with queue_date IS NULL
    null_count_sql = sa.text("SELECT COUNT(*) FROM queue_entries WHERE queue_date IS NULL;")
    unbackfilled_count = bind.execute(null_count_sql).scalar()
    if unbackfilled_count and unbackfilled_count > 0:
        raise RuntimeError(
            f"Migration halted safely: {unbackfilled_count} queue_entries rows still have NULL queue_date "
            "after backfill attempt. Cannot alter queue_date to NOT NULL without data loss."
        )

    # Step 4: Alter queue_date to NOT NULL
    op.alter_column('queue_entries', 'queue_date', nullable=False)

    # Step 5: Set server default to CURRENT_DATE only after backfilling and validation
    op.alter_column(
        'queue_entries',
        'queue_date',
        server_default=sa.text('CURRENT_DATE'),
    )

    # Step 6: Create index on queue_date for efficient date filtering
    op.create_index(op.f('ix_queue_entries_queue_date'), 'queue_entries', ['queue_date'], unique=False)

    # Step 7: Add notes column for consultation/reception notes
    op.add_column('queue_entries', sa.Column('notes', sa.Text(), nullable=True))

    # Step 8: Create partial unique index: at most one active consultation per doctor per clinic date
    op.create_index(
        'uq_active_doctor_in_consultation',
        'queue_entries',
        ['doctor_id', 'queue_date'],
        unique=True,
        postgresql_where=sa.text("status = 'in_consultation'"),
    )

    # Step 9: Create unique constraint: unique token number per doctor per clinic date
    op.create_unique_constraint(
        'uq_doctor_date_token_number',
        'queue_entries',
        ['doctor_id', 'queue_date', 'token_number'],
    )


def downgrade() -> None:
    """Downgrade schema safely, removing only objects introduced in this revision."""
    op.drop_constraint('uq_doctor_date_token_number', 'queue_entries', type_='unique')
    op.drop_index(
        'uq_active_doctor_in_consultation',
        table_name='queue_entries',
        postgresql_where=sa.text("status = 'in_consultation'"),
    )
    op.drop_index(op.f('ix_queue_entries_queue_date'), table_name='queue_entries')
    op.drop_column('queue_entries', 'notes')
    op.alter_column('queue_entries', 'queue_date', server_default=None)
    op.drop_column('queue_entries', 'queue_date')
