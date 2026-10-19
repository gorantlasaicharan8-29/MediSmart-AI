"""
Pre-application Safety Check Script for Phase 5.1 Queue Migration.

This script connects to the target database (medismart_db) and runs comprehensive
diagnostic assertions BEFORE the Alembic migration is executed:
1. Row count of queue_entries and appointments.
2. Status validity check (allowed statuses: waiting, in_consultation, completed, skipped, cancelled).
3. Active consultation check (no doctor has >1 active consultation per date).
4. Token uniqueness check (no doctor has duplicate token numbers per date).
5. Foreign key integrity checks (no orphaned queue records).
6. Presence of existing unique constraint on appointment_id.
7. Verification of queue_date backfill readiness.
"""

import os
import sys

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine, text
from app.core.config import settings

def run_prechecks():
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    engine = create_engine(sync_url)

    print("================================================================================")
    print("MEDISMART DATABASE PRE-MIGRATION SAFETY CHECK REPORT (PHASE 5.1)")
    print("================================================================================")
    safe_db_url = sync_url.split("@")[-1] if "@" in sync_url else sync_url
    print(f"Target Database: {safe_db_url}")

    with engine.connect() as conn:
        # Check 0: Current Alembic Version
        ver_res = conn.execute(text("SELECT version_num FROM alembic_version;")).scalar()
        print(f"Current Alembic Revision: {ver_res}")
        if ver_res != "42d65b870a44":
            print(f"[FAIL] Expected Alembic version 42d65b870a44, but found {ver_res}")
            sys.exit(1)
        print("[PASS] Alembic revision verified: 42d65b870a44")

        # Check 1: Record counts
        queue_count = conn.execute(text("SELECT COUNT(*) FROM queue_entries;")).scalar()
        appt_count = conn.execute(text("SELECT COUNT(*) FROM appointments;")).scalar()
        doc_count = conn.execute(text("SELECT COUNT(*) FROM doctors;")).scalar()
        hosp_count = conn.execute(text("SELECT COUNT(*) FROM hospitals;")).scalar()
        user_count = conn.execute(text("SELECT COUNT(*) FROM users;")).scalar()

        print(f"\nCurrent Database Record Counts:")
        print(f"  - queue_entries : {queue_count}")
        print(f"  - appointments  : {appt_count}")
        print(f"  - doctors       : {doc_count}")
        print(f"  - hospitals     : {hosp_count}")
        print(f"  - users         : {user_count}")

        # Check 2: Status validity
        allowed_statuses = {"waiting", "in_consultation", "completed", "skipped", "cancelled"}
        status_rows = conn.execute(text("SELECT DISTINCT status FROM queue_entries;")).fetchall()
        existing_statuses = {r[0] for r in status_rows}
        invalid_statuses = existing_statuses - allowed_statuses
        if invalid_statuses:
            print(f"[FAIL] Invalid queue status values found: {invalid_statuses}")
            sys.exit(1)
        print(f"[PASS] Status validity check passed. Existing statuses: {existing_statuses or 'None (0 rows)'}")

        # Check 3: Duplicate active consultations per doctor/date
        dup_consult_sql = text("""
            SELECT q.doctor_id, 
                   COALESCE(a.appointment_date, (q.checked_in_at AT TIME ZONE 'UTC')::date) AS clinic_date, 
                   COUNT(*) as cnt
            FROM queue_entries q
            LEFT JOIN appointments a ON q.appointment_id = a.id
            WHERE q.status = 'in_consultation'
            GROUP BY q.doctor_id, clinic_date
            HAVING COUNT(*) > 1;
        """)
        dup_consults = conn.execute(dup_consult_sql).fetchall()
        if dup_consults:
            print(f"[FAIL] Duplicate active consultations detected: {dup_consults}")
            sys.exit(1)
        print("[PASS] No duplicate active consultations detected.")

        # Check 4: Duplicate tokens per doctor/date
        dup_tokens_sql = text("""
            SELECT q.doctor_id, 
                   COALESCE(a.appointment_date, (q.checked_in_at AT TIME ZONE 'UTC')::date) AS clinic_date, 
                   q.token_number, 
                   COUNT(*) as cnt
            FROM queue_entries q
            LEFT JOIN appointments a ON q.appointment_id = a.id
            GROUP BY q.doctor_id, clinic_date, q.token_number
            HAVING COUNT(*) > 1;
        """)
        dup_tokens = conn.execute(dup_tokens_sql).fetchall()
        if dup_tokens:
            print(f"[FAIL] Duplicate token numbers detected: {dup_tokens}")
            sys.exit(1)
        print("[PASS] No duplicate doctor/date/token combinations detected.")

        # Check 5: Orphaned foreign keys
        orphan_appts = conn.execute(text("""
            SELECT COUNT(*) FROM queue_entries q 
            LEFT JOIN appointments a ON q.appointment_id = a.id 
            WHERE a.id IS NULL;
        """)).scalar()
        orphan_docs = conn.execute(text("""
            SELECT COUNT(*) FROM queue_entries q 
            LEFT JOIN doctors d ON q.doctor_id = d.id 
            WHERE d.id IS NULL;
        """)).scalar()
        orphan_hosps = conn.execute(text("""
            SELECT COUNT(*) FROM queue_entries q 
            LEFT JOIN hospitals h ON q.hospital_id = h.id 
            WHERE h.id IS NULL;
        """)).scalar()
        orphan_users = conn.execute(text("""
            SELECT COUNT(*) FROM queue_entries q 
            LEFT JOIN users u ON q.patient_id = u.id 
            WHERE u.id IS NULL;
        """)).scalar()

        if any([orphan_appts, orphan_docs, orphan_hosps, orphan_users]):
            print(f"[FAIL] Orphaned foreign keys found: appts={orphan_appts}, docs={orphan_docs}, hosps={orphan_hosps}, users={orphan_users}")
            sys.exit(1)
        print("[PASS] Foreign key integrity verified. Zero orphaned records.")

        # Check 6: Preserved unique constraint on appointment_id
        uq_appt_res = conn.execute(text("""
            SELECT conname FROM pg_constraint 
            WHERE conrelid = 'queue_entries'::regclass 
            AND conname = 'queue_entries_appointment_id_key';
        """)).scalar()
        if not uq_appt_res:
            print("[FAIL] Required unique constraint 'queue_entries_appointment_id_key' missing!")
            sys.exit(1)
        print(f"[PASS] Unique constraint verified: {uq_appt_res}")

        # Check 7: Existing indexes
        idx_rows = conn.execute(text("""
            SELECT indexname FROM pg_indexes WHERE tablename = 'queue_entries';
        """)).fetchall()
        existing_indices = [r[0] for r in idx_rows]
        print(f"[PASS] Current queue_entries indexes: {existing_indices}")

        # Check 8: Historical Date Source Validity (appointments.appointment_date or checked_in_at)
        undated_records_sql = text("""
            SELECT q.id, q.appointment_id 
            FROM queue_entries q
            LEFT JOIN appointments a ON q.appointment_id = a.id
            WHERE a.appointment_date IS NULL AND q.checked_in_at IS NULL;
        """)
        undated_records = conn.execute(undated_records_sql).fetchall()
        if undated_records:
            print(f"[FAIL] Records without a valid date source detected: {undated_records}")
            sys.exit(1)
        print("[PASS] Date source check passed. Zero undated queue records.")

    print("================================================================================")
    print("ALL PRE-MIGRATION SAFETY CHECKS PASSED SUCCESSFULLY (READY FOR MIGRATION)")
    print("================================================================================")

if __name__ == "__main__":
    run_prechecks()
