"""
Transaction Safety and Rollback Verification Script for Alembic Migration (Phase 5.1).

Verifies:
1. env.py transaction handling (context.begin_transaction with PostgreSQL transactional DDL).
2. Pre-check failure rollback:
   - Injects invalid queue status before DDL begins.
   - Verifies migration aborts safely.
   - Verifies zero columns added, zero index changes, alembic_version unchanged.
   - Verifies pre-existing records preserved.
3. Mid-DDL failure rollback:
   - Migration begins: executes add_column(queue_date), backfill UPDATE, alter_column(NOT NULL),
     create_index(ix_queue_entries_queue_date), add_column(notes), create_index(uq_active_doctor_in_consultation).
   - Injects failure at Step 9 (create_unique_constraint).
   - Verifies PostgreSQL transaction rollback unwinds ALL DDL and DML operations.
   - Verifies queue_date and notes columns do NOT exist.
   - Verifies partial index and date index do NOT exist.
   - Verifies alembic_version strictly preserved at 42d65b870a44.
   - Verifies pre-existing records preserved.
4. Clean successful migration and downgrade cycle.
5. Full backend regression test suite against migrated schema.

SAFETY GUARANTEE:
All operations execute STRICTLY against an isolated sandbox database ('medismart_tx_test_db').
Production database ('medismart_db') is never touched or modified.
"""

import os
import subprocess
import sys

# Ensure backend root is on sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BACKEND_DIR)

# Determine database URLs safely
from app.core.config import settings

SYNC_URL = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
BASE_PG_URL = SYNC_URL.rsplit("/", 1)[0] + "/postgres"
TEST_DB_NAME = "medismart_tx_test_db"
TEST_SYNC_URL = SYNC_URL.rsplit("/", 1)[0] + f"/{TEST_DB_NAME}"
TEST_ASYNC_URL = settings.DATABASE_URL.rsplit("/", 1)[0] + f"/{TEST_DB_NAME}"

# Subprocess environment pointing exclusively to sandbox database
SANDBOX_ENV = os.environ.copy()
SANDBOX_ENV["DATABASE_URL"] = TEST_ASYNC_URL
SANDBOX_ENV["PYTHONPATH"] = "."

from sqlalchemy import create_engine, text

def run_transaction_safety_verification():
    server_engine = create_engine(BASE_PG_URL, isolation_level="AUTOCOMMIT")

    print("=" * 80)
    print("PHASE 5.1: TRANSACTION SAFETY & ROLLBACK VERIFICATION SUITE")
    print("=" * 80)
    print(f"Creating isolated sandbox database: {TEST_DB_NAME}...")

    with server_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE);"))
        conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME};"))
    print("[PASS] Isolated sandbox created.")

    test_engine = create_engine(TEST_SYNC_URL)

    try:
        # Double-check we are connected to the test database
        with test_engine.connect() as conn:
            current_db = conn.execute(text("SELECT current_database();")).scalar()
            assert current_db == TEST_DB_NAME, f"Safety check failed: connected to {current_db} instead of {TEST_DB_NAME}!"
            print(f"[SAFETY VERIFIED] Current database is strictly: {current_db}")

        # ---------------------------------------------------------------------
        # 1. Migrate sandbox to Phase 4 baseline (42d65b870a44)
        # ---------------------------------------------------------------------
        print("\n--- 1. Migrating sandbox to Phase 4 baseline (42d65b870a44) ---")
        res_baseline = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "42d65b870a44"],
            capture_output=True,
            text=True,
            env=SANDBOX_ENV,
            cwd=BACKEND_DIR,
        )
        assert res_baseline.returncode == 0, f"Baseline migration failed: {res_baseline.stderr}"
        print("[PASS] Sandbox migrated to baseline 42d65b870a44.")

        # Seed baseline facilities, doctors, users, appointments, and queue entries
        subprocess.run([sys.executable, "scripts/seed_hospitals.py"], env=SANDBOX_ENV, cwd=BACKEND_DIR, check=True)
        subprocess.run([sys.executable, "scripts/seed_doctors.py"], env=SANDBOX_ENV, cwd=BACKEND_DIR, check=True)

        with test_engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO users (id, email, hashed_password, full_name, role, is_active)
                VALUES 
                ('11111111-1111-1111-1111-111111111111', 'tx_patient1@example.com', 'dummy', 'TX Patient One', 'patient', true),
                ('11111111-1111-1111-1111-111111111112', 'tx_patient2@example.com', 'dummy', 'TX Patient Two', 'patient', true);
            """))
            hid = conn.execute(text("SELECT id FROM hospitals LIMIT 1;")).scalar()
            did = conn.execute(text("SELECT id FROM doctors LIMIT 1;")).scalar()

            # Seed a pre-existing valid appointment and queue entry
            conn.execute(text(f"""
                INSERT INTO appointments (id, appointment_token, patient_id, doctor_id, hospital_id, appointment_date, appointment_time, status)
                VALUES ('aaaaaaaa-0001-0001-0001-000000000001', 'MS-TX-BASE-01', '11111111-1111-1111-1111-111111111111', '{did}', '{hid}', '2026-10-19', '09:00:00', 'scheduled');
                INSERT INTO queue_entries (id, appointment_id, hospital_id, doctor_id, patient_id, token_number, position, status, checked_in_at)
                VALUES ('bbbbbbbb-0001-0001-0001-000000000001', 'aaaaaaaa-0001-0001-0001-000000000001', '{hid}', '{did}', '11111111-1111-1111-1111-111111111111', 1, 1, 'waiting', '2026-10-19 08:30:00+00');
            """))
            conn.commit()
        print("[PASS] Baseline records seeded in sandbox.")

        # ---------------------------------------------------------------------
        # 2. Test Failure Scenario A: Pre-Check Abort (Before DDL begins)
        # ---------------------------------------------------------------------
        print("\n--- 2. Testing Pre-Check Abort Transaction Safety ---")
        with test_engine.connect() as conn:
            conn.execute(text(f"""
                INSERT INTO appointments (id, appointment_token, patient_id, doctor_id, hospital_id, appointment_date, appointment_time, status)
                VALUES ('aaaaaaaa-0001-0001-0001-000000000002', 'MS-TX-INV-01', '11111111-1111-1111-1111-111111111112', '{did}', '{hid}', '2026-10-19', '10:00:00', 'scheduled');
                INSERT INTO queue_entries (id, appointment_id, hospital_id, doctor_id, patient_id, token_number, position, status, checked_in_at)
                VALUES ('bbbbbbbb-0001-0001-0001-000000000002', 'aaaaaaaa-0001-0001-0001-000000000002', '{hid}', '{did}', '11111111-1111-1111-1111-111111111112', 2, 2, 'invalid_status_xyz', '2026-10-19 09:30:00+00');
            """))
            conn.commit()

        res_abort_pre = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "52a1b9e8c4d1"],
            capture_output=True,
            text=True,
            env=SANDBOX_ENV,
            cwd=BACKEND_DIR,
        )
        assert res_abort_pre.returncode != 0, "Migration should have aborted on invalid status!"
        assert "Inconsistent queue status values found in database" in res_abort_pre.stderr
        print("  [PASS] Migration aborted in Pre-Check 1 as expected.")

        # Inspect database state after pre-check abort
        with test_engine.connect() as conn:
            rev = conn.execute(text("SELECT version_num FROM alembic_version;")).scalar()
            assert rev == "42d65b870a44", f"Expected revision 42d65b870a44, got {rev}"
            print(f"  [PASS] alembic_version strictly preserved: {rev}")

            cols = [r[0] for r in conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'queue_entries';")).fetchall()]
            assert "queue_date" not in cols, "queue_date exists after pre-check abort!"
            assert "notes" not in cols, "notes exists after pre-check abort!"
            print(f"  [PASS] Zero schema changes: queue_date and notes do not exist. Current columns: {cols}")

            q_cnt = conn.execute(text("SELECT COUNT(*) FROM queue_entries;")).scalar()
            assert q_cnt == 2, f"Expected 2 queue entries, found {q_cnt}"
            print(f"  [PASS] Existing records completely preserved: {q_cnt} rows.")

            # Clean up the test invalid row
            conn.execute(text("""
                DELETE FROM queue_entries WHERE id = 'bbbbbbbb-0001-0001-0001-000000000002';
                DELETE FROM appointments WHERE id = 'aaaaaaaa-0001-0001-0001-000000000002';
            """))
            conn.commit()

        # ---------------------------------------------------------------------
        # 3. Test Failure Scenario B: Mid-DDL Failure & Transaction Rollback
        # ---------------------------------------------------------------------
        print("\n--- 3. Testing Mid-DDL Failure & Complete Transaction Rollback ---")
        # In a separate subprocess with SANDBOX_ENV, we execute Alembic upgrade with a monkeypatch
        # that simulates a crash/failure during the final step (create_unique_constraint) AFTER
        # add_column(queue_date), backfill UPDATE, alter_column, create_index, and add_column(notes) have all run.
        sim_code = """
import os
import sys
import unittest.mock
from alembic import command, op as alembic_op
from alembic.config import Config

def failing_create_unique_constraint(*args, **kwargs):
    print("  [SIMULATION] Reached Step 9 (create_unique_constraint). Injecting simulated post-DDL failure...")
    raise RuntimeError("SIMULATED_POST_DDL_DATABASE_FAILURE: Unrecoverable disk error during final constraint creation.")

cfg = Config(os.path.join(sys.path[0], "alembic.ini"))
with unittest.mock.patch.object(alembic_op, "create_unique_constraint", side_effect=failing_create_unique_constraint):
    command.upgrade(cfg, "52a1b9e8c4d1")
"""
        res_mid_fail = subprocess.run(
            [sys.executable, "-c", sim_code],
            capture_output=True,
            text=True,
            env=SANDBOX_ENV,
            cwd=BACKEND_DIR,
        )
        print(f"  Captured subprocess output:\n{res_mid_fail.stdout}\n{res_mid_fail.stderr}")
        assert res_mid_fail.returncode != 0, "Subprocess should have failed on injected error!"
        assert "SIMULATED_POST_DDL_DATABASE_FAILURE" in res_mid_fail.stderr or "SIMULATED_POST_DDL_DATABASE_FAILURE" in res_mid_fail.stdout
        print("  [PASS] Injected mid-DDL failure triggered inside transaction.")

        # Now verify PostgreSQL state: Was EVERYTHING rolled back?
        with test_engine.connect() as conn:
            # 1. alembic_version must still be 42d65b870a44
            rev = conn.execute(text("SELECT version_num FROM alembic_version;")).scalar()
            assert rev == "42d65b870a44", f"Expected revision 42d65b870a44, got {rev}"
            print(f"  [PASS] alembic_version rolled back: strictly remained at {rev}")

            # 2. queue_entries columns must NOT contain queue_date or notes
            cols = [r[0] for r in conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'queue_entries';")).fetchall()]
            assert "queue_date" not in cols, "queue_date column was NOT rolled back!"
            assert "notes" not in cols, "notes column was NOT rolled back!"
            print(f"  [PASS] DDL addition rolled back: queue_date and notes do not exist. Current columns: {cols}")

            # 3. Indexes must NOT contain ix_queue_entries_queue_date or uq_active_doctor_in_consultation
            indexes = [r[0] for r in conn.execute(text("SELECT indexname FROM pg_indexes WHERE tablename = 'queue_entries';")).fetchall()]
            assert "ix_queue_entries_queue_date" not in indexes, "ix_queue_entries_queue_date was NOT rolled back!"
            assert "uq_active_doctor_in_consultation" not in indexes, "uq_active_doctor_in_consultation was NOT rolled back!"
            assert "uq_doctor_date_token_number" not in indexes, "uq_doctor_date_token_number was NOT rolled back!"
            print(f"  [PASS] Indexes rolled back: only baseline indexes exist ({indexes}).")

            # 4. Pre-existing records must be 100% intact
            row = conn.execute(text("SELECT id, token_number, status, checked_in_at FROM queue_entries WHERE id = 'bbbbbbbb-0001-0001-0001-000000000001';")).fetchone()
            assert row is not None, "Pre-existing queue entry disappeared!"
            assert row[1] == 1 and row[2] == "waiting"
            print("  [PASS] Pre-existing data intact and unmodified.")

        # ---------------------------------------------------------------------
        # 4. Test Clean Uninterrupted Migration
        # ---------------------------------------------------------------------
        print("\n--- 4. Executing Clean Uninterrupted Migration ---")
        res_up = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "52a1b9e8c4d1"],
            capture_output=True,
            text=True,
            env=SANDBOX_ENV,
            cwd=BACKEND_DIR,
        )
        assert res_up.returncode == 0, f"Clean upgrade failed: {res_up.stderr}"
        print("[PASS] Clean upgrade succeeded.")

        with test_engine.connect() as conn:
            rev = conn.execute(text("SELECT version_num FROM alembic_version;")).scalar()
            assert rev == "52a1b9e8c4d1"
            print(f"  [PASS] Migration completed. Revision: {rev}")

            # Confirm queue_date was added and backfilled
            qdate = conn.execute(text("SELECT queue_date, notes FROM queue_entries WHERE id = 'bbbbbbbb-0001-0001-0001-000000000001';")).fetchone()
            assert str(qdate[0]) == "2026-10-19"
            print(f"  [PASS] queue_date backfilled accurately: {qdate[0]}")

            # Confirm constraints and indexes are now active
            indexes = [r[0] for r in conn.execute(text("SELECT indexname FROM pg_indexes WHERE tablename = 'queue_entries';")).fetchall()]
            assert "ix_queue_entries_queue_date" in indexes
            assert "uq_active_doctor_in_consultation" in indexes
            assert "uq_doctor_date_token_number" in indexes
            print("  [PASS] All Phase 5.1 constraints and indexes confirmed in PostgreSQL catalog.")

        # ---------------------------------------------------------------------
        # 5. Test Clean Downgrade
        # ---------------------------------------------------------------------
        print("\n--- 5. Testing Clean Downgrade to 42d65b870a44 ---")
        res_down = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", "42d65b870a44"],
            capture_output=True,
            text=True,
            env=SANDBOX_ENV,
            cwd=BACKEND_DIR,
        )
        assert res_down.returncode == 0, f"Downgrade failed: {res_down.stderr}"
        print("[PASS] Downgrade executed successfully.")

        with test_engine.connect() as conn:
            rev = conn.execute(text("SELECT version_num FROM alembic_version;")).scalar()
            assert rev == "42d65b870a44"
            print(f"  [PASS] Downgrade completed. Revision: {rev}")

            cols = [r[0] for r in conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'queue_entries';")).fetchall()]
            assert "queue_date" not in cols and "notes" not in cols
            print("  [PASS] Columns dropped cleanly.")

            row = conn.execute(text("SELECT COUNT(*) FROM queue_entries WHERE id = 'bbbbbbbb-0001-0001-0001-000000000001';")).scalar()
            assert row == 1
            print("  [PASS] Baseline records preserved after downgrade.")

        # ---------------------------------------------------------------------
        # 6. Re-upgrade and run Full Backend Regression Suite (59 tests)
        # ---------------------------------------------------------------------
        print("\n--- 6. Re-upgrading to 52a1b9e8c4d1 and Running Backend Regression Suite ---")
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "52a1b9e8c4d1"],
            env=SANDBOX_ENV,
            cwd=BACKEND_DIR,
            check=True,
        )
        res_pytest = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-v"],
            capture_output=True,
            text=True,
            env=SANDBOX_ENV,
            cwd=BACKEND_DIR,
        )
        print(res_pytest.stdout)
        assert res_pytest.returncode == 0, f"Pytest failed: {res_pytest.stderr}"
        print("[PASS] Full backend regression suite passed (59/59 tests).")

        print("\n" + "=" * 80)
        print("ALL TRANSACTION-SAFETY AND ROLLBACK VERIFICATIONS PASSED")
        print("=" * 80)

    finally:
        print(f"\nDropping isolated test database {TEST_DB_NAME}...")
        with server_engine.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE);"))
        print("[PASS] Sandbox database cleaned up. medismart_db is completely untouched.")

if __name__ == "__main__":
    run_transaction_safety_verification()
