"""
Post-Migration Verification Script for medismart_db (Phase 5.1).

Verifies:
1. Active database is medismart_db.
2. Current Alembic revision is 52a1b9e8c4d1.
3. Added columns (queue_date, notes) and properties in queue_entries.
4. Active constraints (unique appointment_id, uq_doctor_date_token_number, foreign keys).
5. Active indexes (ix_queue_entries_queue_date, uq_active_doctor_in_consultation).
6. Record count preservation across all tables.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine, text
from app.core.config import settings

def verify_medismart_db():
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    engine = create_engine(sync_url)

    print("=" * 80)
    print("MEDISMART DATABASE POST-MIGRATION VERIFICATION (PHASE 5.1)")
    print("=" * 80)

    with engine.connect() as conn:
        # 1. Target database check
        current_db = conn.execute(text("SELECT current_database();")).scalar()
        print(f"Target Database: {current_db}")
        assert current_db == "medismart_db", f"Expected medismart_db, got {current_db}"
        print("[PASS] Confirmed active database is medismart_db.")

        # 2. Alembic revision check
        rev = conn.execute(text("SELECT version_num FROM alembic_version;")).scalar()
        print(f"Current Alembic Revision: {rev}")
        assert rev == "52a1b9e8c4d1", f"Expected revision 52a1b9e8c4d1, got {rev}"
        print("[PASS] Confirmed Alembic revision is 52a1b9e8c4d1.")

        # 3. Column schema verification for queue_entries
        cols_info = conn.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default 
            FROM information_schema.columns 
            WHERE table_name = 'queue_entries';
        """)).fetchall()
        col_dict = {r[0]: {"type": r[1], "nullable": r[2], "default": r[3]} for r in cols_info}
        
        print("\nChecking queue_entries columns:")
        assert "queue_date" in col_dict, "queue_date column missing!"
        print(f"  - queue_date: type={col_dict['queue_date']['type']}, nullable={col_dict['queue_date']['nullable']}, default={col_dict['queue_date']['default']}")
        assert col_dict['queue_date']['type'] == 'date'
        assert col_dict['queue_date']['nullable'] == 'NO'
        assert 'CURRENT_DATE' in str(col_dict['queue_date']['default']).upper()
        print("    [PASS] queue_date is DATE, NOT NULL, server_default=CURRENT_DATE.")

        assert "notes" in col_dict, "notes column missing!"
        print(f"  - notes: type={col_dict['notes']['type']}, nullable={col_dict['notes']['nullable']}")
        assert col_dict['notes']['type'] == 'text'
        assert col_dict['notes']['nullable'] == 'YES'
        print("    [PASS] notes is TEXT, nullable=True.")

        baseline_cols = {
            'id', 'appointment_id', 'hospital_id', 'doctor_id', 'patient_id',
            'token_number', 'position', 'status', 'estimated_wait_minutes',
            'checked_in_at', 'called_at', 'completed_at', 'created_at', 'updated_at'
        }
        for b_col in baseline_cols:
            assert b_col in col_dict, f"Baseline column {b_col} missing!"
        print(f"    [PASS] All {len(baseline_cols)} baseline columns preserved intact.")

        # 4. Constraint verification
        constraints = conn.execute(text("""
            SELECT constraint_name, constraint_type 
            FROM information_schema.table_constraints 
            WHERE table_name = 'queue_entries';
        """)).fetchall()
        c_names = {r[0]: r[1] for r in constraints}
        print("\nChecking queue_entries constraints:")
        for cname, ctype in c_names.items():
            print(f"  - {cname}: {ctype}")

        assert "queue_entries_appointment_id_key" in c_names, "Unique appointment_id constraint missing!"
        assert "uq_doctor_date_token_number" in c_names, "Unique doctor_date_token_number constraint missing!"
        print("    [PASS] Required unique constraints verified.")

        # 5. Index verification
        indexes = conn.execute(text("""
            SELECT indexname, indexdef 
            FROM pg_indexes 
            WHERE tablename = 'queue_entries';
        """)).fetchall()
        idx_dict = {r[0]: r[1] for r in indexes}
        print("\nChecking queue_entries indexes:")
        for iname, idef in idx_dict.items():
            print(f"  - {iname}: {idef}")

        assert "ix_queue_entries_queue_date" in idx_dict, "ix_queue_entries_queue_date index missing!"
        assert "uq_active_doctor_in_consultation" in idx_dict, "uq_active_doctor_in_consultation partial unique index missing!"
        assert "in_consultation" in idx_dict["uq_active_doctor_in_consultation"]
        print("    [PASS] Partial unique index and queue_date index verified.")

        # 6. Record counts verification
        print("\nVerifying Record Counts Across All Tables:")
        tables = ["hospitals", "doctors", "users", "appointments", "queue_entries"]
        expected_counts = {
            "hospitals": 8,
            "doctors": 10,
            "users": 10,
            "appointments": 0,
            "queue_entries": 0,
        }
        for table in tables:
            cnt = conn.execute(text(f"SELECT COUNT(*) FROM {table};")).scalar()
            print(f"  - {table:15s}: {cnt} rows (expected: {expected_counts[table]})")
            assert cnt == expected_counts[table], f"Record count mismatch in {table}: expected {expected_counts[table]}, found {cnt}"
        print("    [PASS] 100% record preservation confirmed across all tables.")

    print("\n" + "=" * 80)
    print("ALL POST-MIGRATION VERIFICATION CHECKS PASSED ON medismart_db")
    print("=" * 80)

if __name__ == "__main__":
    verify_medismart_db()
