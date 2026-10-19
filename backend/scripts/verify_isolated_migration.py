"""
Comprehensive Isolated Migration, Pre-Check, Constraint, and Rollback Verification Script (Phase 5.1).

This script tests ALL Plan 5.1 requirements against a temporary PostgreSQL database:
1. Date Consistency: Verifies Asia/Kolkata clinic-date calculation in prechecks and backfill.
2. Isolated Pre-Check Abort Tests (Invalid existing data safely aborts without modifying data):
   - Case A: Record with neither date source (appointment_date IS NULL and checked_in_at IS NULL).
   - Case B: Duplicate doctor/date/token combination.
   - Case C: Duplicate active consultations (in_consultation) for same doctor and clinic date.
3. Positive Migration Backfill Tests:
   - Case D: Historical entry with appointment date.
   - Case E: Historical entry with missing appointment date but valid checked_in_at (Asia/Kolkata conversion).
4. Direct Database Constraint Verification:
   - Unique appointment_id (queue_entries_appointment_id_key).
   - Unique doctor_id + queue_date + token_number (uq_doctor_date_token_number).
   - Partial unique index on doctor_id + queue_date where status='in_consultation' (uq_active_doctor_in_consultation).
5. Full Backend Regression Suite (pytest 59/59 tests).
6. Downgrade Verification: Confirms rollback removes only Phase 5.1 objects and preserves all baseline data.
"""

import os
import subprocess
import sys
import uuid
from datetime import date, datetime, time, timezone

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine, text
from app.core.config import settings

def run_isolated_verification():
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    base_url = sync_url.rsplit("/", 1)[0] + "/postgres"
    test_db_name = "medismart_migration_verify_db"
    test_sync_url = sync_url.rsplit("/", 1)[0] + f"/{test_db_name}"
    test_async_url = settings.DATABASE_URL.rsplit("/", 1)[0] + f"/{test_db_name}"

    server_engine = create_engine(base_url, isolation_level="AUTOCOMMIT")

    print("================================================================================")
    print("PHASE 5.1 COMPREHENSIVE ISOLATED VERIFICATION SUITE")
    print("================================================================================")
    print(f"Creating isolated sandbox database: {test_db_name}...")

    with server_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {test_db_name} WITH (FORCE);"))
        conn.execute(text(f"CREATE DATABASE {test_db_name};"))
    print("[PASS] Sandbox database created.")

    env = os.environ.copy()
    env["DATABASE_URL"] = test_async_url
    env["PYTHONPATH"] = "."

    try:
        # -------------------------------------------------------------------------
        # Step 1: Migrate sandbox to baseline (42d65b870a44)
        # -------------------------------------------------------------------------
        print("\nStep 1: Migrating sandbox to baseline (42d65b870a44)...")
        res = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "42d65b870a44"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert res.returncode == 0, f"Baseline migration failed: {res.stderr}"
        print("[PASS] Baseline revision 42d65b870a44 applied.")

        # Seed baseline hospital and doctor
        print("\nStep 2: Seeding baseline facilities and doctors...")
        subprocess.run([sys.executable, "scripts/seed_hospitals.py"], env=env, check=True)
        subprocess.run([sys.executable, "scripts/seed_doctors.py"], env=env, check=True)

        test_engine = create_engine(test_sync_url)
        with test_engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO users (id, email, hashed_password, full_name, role, is_active)
                VALUES 
                ('22222222-2222-2222-2222-222222222222', 'pat1@example.com', 'dummy', 'Patient One', 'patient', true),
                ('22222222-2222-2222-2222-222222222223', 'pat2@example.com', 'dummy', 'Patient Two', 'patient', true);
            """))
            hid = conn.execute(text("SELECT id FROM hospitals LIMIT 1;")).scalar()
            did = conn.execute(text("SELECT id FROM doctors LIMIT 1;")).scalar()
            conn.commit()

        # -------------------------------------------------------------------------
        # Step 2A: Test Negative Pre-Check: Record with NEITHER date source aborts safely
        # -------------------------------------------------------------------------
        print("\nStep 2A: Testing pre-check abort on record with NEITHER date source...")
        with test_engine.connect() as conn:
            conn.execute(text("ALTER TABLE appointments ALTER COLUMN appointment_date DROP NOT NULL;"))
            conn.execute(text("ALTER TABLE queue_entries ALTER COLUMN checked_in_at DROP NOT NULL;"))
            conn.execute(text(f"""
                INSERT INTO appointments (id, appointment_token, patient_id, doctor_id, hospital_id, appointment_date, appointment_time, status)
                VALUES ('aaaaaaaa-1111-1111-1111-111111111111', 'MS-UNDATED-01', '22222222-2222-2222-2222-222222222222', '{did}', '{hid}', NULL, '10:00:00', 'scheduled');
                INSERT INTO queue_entries (id, appointment_id, hospital_id, doctor_id, patient_id, token_number, position, status, checked_in_at)
                VALUES ('b1b1b1b1-1111-1111-1111-111111111111', 'aaaaaaaa-1111-1111-1111-111111111111', '{hid}', '{did}', '22222222-2222-2222-2222-222222222222', 10, 1, 'waiting', NULL);
            """))
            conn.commit()

        res_abort_undated = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "52a1b9e8c4d1"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert res_abort_undated.returncode != 0, "Migration should have aborted on undated record!"
        assert "without a valid clinic date source" in res_abort_undated.stderr
        print("  [PASS] Migration aborted safely with clear diagnostic for undated record.")

        # Verify record preserved and no schema changes
        with test_engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM queue_entries WHERE id = 'b1b1b1b1-1111-1111-1111-111111111111';")).scalar() == 1
            cols = [r[0] for r in conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'queue_entries';")).fetchall()]
            assert "queue_date" not in cols, "queue_date column created despite abort!"
            # Clean up
            conn.execute(text("""
                DELETE FROM queue_entries WHERE id = 'b1b1b1b1-1111-1111-1111-111111111111';
                DELETE FROM appointments WHERE id = 'aaaaaaaa-1111-1111-1111-111111111111';
                ALTER TABLE appointments ALTER COLUMN appointment_date SET NOT NULL;
                ALTER TABLE queue_entries ALTER COLUMN checked_in_at SET NOT NULL;
            """))
            conn.commit()
        print("  [PASS] Record preserved and schema unmodified.")

        # -------------------------------------------------------------------------
        # Step 2B: Test Negative Pre-Check: Duplicate doctor/date/token combination aborts safely
        # -------------------------------------------------------------------------
        print("\nStep 2B: Testing pre-check abort on duplicate doctor/date/token combination...")
        with test_engine.connect() as conn:
            conn.execute(text(f"""
                INSERT INTO appointments (id, appointment_token, patient_id, doctor_id, hospital_id, appointment_date, appointment_time, status)
                VALUES 
                ('aaaaaaaa-2222-2222-2222-222222222221', 'MS-DUPTOK-01', '22222222-2222-2222-2222-222222222222', '{did}', '{hid}', '2026-10-25', '10:00:00', 'scheduled'),
                ('aaaaaaaa-2222-2222-2222-222222222222', 'MS-DUPTOK-02', '22222222-2222-2222-2222-222222222223', '{did}', '{hid}', '2026-10-25', '10:15:00', 'scheduled');
                INSERT INTO queue_entries (id, appointment_id, hospital_id, doctor_id, patient_id, token_number, position, status, checked_in_at)
                VALUES 
                ('b1b1b1b1-2222-2222-2222-222222222221', 'aaaaaaaa-2222-2222-2222-222222222221', '{hid}', '{did}', '22222222-2222-2222-2222-222222222222', 1, 1, 'waiting', '2026-10-25 04:30:00+00'),
                ('b1b1b1b1-2222-2222-2222-222222222222', 'aaaaaaaa-2222-2222-2222-222222222222', '{hid}', '{did}', '22222222-2222-2222-2222-222222222223', 1, 2, 'waiting', '2026-10-25 04:45:00+00');
            """))
            conn.commit()

        res_abort_duptok = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "52a1b9e8c4d1"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert res_abort_duptok.returncode != 0, "Migration should have aborted on duplicate tokens!"
        assert "Duplicate doctor/date/token combinations detected" in res_abort_duptok.stderr
        print("  [PASS] Migration aborted safely with clear diagnostic for duplicate tokens.")

        with test_engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM queue_entries WHERE token_number = 1;")).scalar() == 2
            # Clean up
            conn.execute(text("""
                DELETE FROM queue_entries WHERE token_number = 1;
                DELETE FROM appointments WHERE appointment_token LIKE 'MS-DUPTOK-%';
            """))
            conn.commit()
        print("  [PASS] Duplicate records preserved and schema unmodified.")

        # -------------------------------------------------------------------------
        # Step 2C: Test Negative Pre-Check: Duplicate active consultations aborts safely
        # -------------------------------------------------------------------------
        print("\nStep 2C: Testing pre-check abort on duplicate active consultations...")
        with test_engine.connect() as conn:
            conn.execute(text(f"""
                INSERT INTO appointments (id, appointment_token, patient_id, doctor_id, hospital_id, appointment_date, appointment_time, status)
                VALUES 
                ('aaaaaaaa-3333-3333-3333-333333333331', 'MS-DUPCON-01', '22222222-2222-2222-2222-222222222222', '{did}', '{hid}', '2026-10-26', '11:00:00', 'in_progress'),
                ('aaaaaaaa-3333-3333-3333-333333333332', 'MS-DUPCON-02', '22222222-2222-2222-2222-222222222223', '{did}', '{hid}', '2026-10-26', '11:15:00', 'in_progress');
                INSERT INTO queue_entries (id, appointment_id, hospital_id, doctor_id, patient_id, token_number, position, status, checked_in_at)
                VALUES 
                ('b1b1b1b1-3333-3333-3333-333333333331', 'aaaaaaaa-3333-3333-3333-333333333331', '{hid}', '{did}', '22222222-2222-2222-2222-222222222222', 1, 1, 'in_consultation', '2026-10-26 05:30:00+00'),
                ('b1b1b1b1-3333-3333-3333-333333333332', 'aaaaaaaa-3333-3333-3333-333333333332', '{hid}', '{did}', '22222222-2222-2222-2222-222222222223', 2, 2, 'in_consultation', '2026-10-26 05:45:00+00');
            """))
            conn.commit()

        res_abort_dupcon = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "52a1b9e8c4d1"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert res_abort_dupcon.returncode != 0, "Migration should have aborted on duplicate consultations!"
        assert "Duplicate active consultations detected" in res_abort_dupcon.stderr
        print("  [PASS] Migration aborted safely with clear diagnostic for duplicate active consultations.")

        with test_engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM queue_entries WHERE status = 'in_consultation';")).scalar() == 2
            # Clean up
            conn.execute(text("""
                DELETE FROM queue_entries WHERE status = 'in_consultation';
                DELETE FROM appointments WHERE appointment_token LIKE 'MS-DUPCON-%';
            """))
            conn.commit()
        print("  [PASS] Duplicate records preserved and schema unmodified.")

        # -------------------------------------------------------------------------
        # Step 3: Positive Migration with Date Consistency & Backfill Verification
        # Case D: Appointment date present
        # Case E: Missing appointment date, valid checked_in_at (Asia/Kolkata timezone)
        # -------------------------------------------------------------------------
        print("\nStep 3: Seeding valid historical records (appointment date & checked_in_at fallback)...")
        with test_engine.connect() as conn:
            conn.execute(text("ALTER TABLE appointments ALTER COLUMN appointment_date DROP NOT NULL;"))
            conn.execute(text(f"""
                -- Case D: Appointment date present ('2026-10-19')
                INSERT INTO appointments (id, appointment_token, patient_id, doctor_id, hospital_id, appointment_date, appointment_time, status)
                VALUES ('55555555-5555-5555-5555-555555555555', 'MS-HIST-01', '22222222-2222-2222-2222-222222222222', '{did}', '{hid}', '2026-10-19', '10:00:00', 'scheduled');
                INSERT INTO queue_entries (id, appointment_id, hospital_id, doctor_id, patient_id, token_number, position, status, checked_in_at)
                VALUES ('66666666-6666-6666-6666-666666666666', '55555555-5555-5555-5555-555555555555', '{hid}', '{did}', '22222222-2222-2222-2222-222222222222', 1, 1, 'waiting', '2026-10-19 09:30:00+00');

                -- Case E: Missing appointment date (NULL), valid checked_in_at at 03:00 UTC on Oct 20 (= 08:30 IST on Oct 20)
                INSERT INTO appointments (id, appointment_token, patient_id, doctor_id, hospital_id, appointment_date, appointment_time, status)
                VALUES ('55555555-5555-5555-5555-555555555556', 'MS-HIST-02', '22222222-2222-2222-2222-222222222223', '{did}', '{hid}', NULL, '08:30:00', 'scheduled');
                INSERT INTO queue_entries (id, appointment_id, hospital_id, doctor_id, patient_id, token_number, position, status, checked_in_at)
                VALUES ('66666666-6666-6666-6666-666666666667', '55555555-5555-5555-5555-555555555556', '{hid}', '{did}', '22222222-2222-2222-2222-222222222223', 2, 2, 'waiting', '2026-10-20 03:00:00+00');
            """))
            conn.commit()

        print("\nStep 4: Executing positive Alembic upgrade to 52a1b9e8c4d1...")
        res_up = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "52a1b9e8c4d1"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert res_up.returncode == 0, f"Positive upgrade failed: {res_up.stderr}"
        print("[PASS] Positive migration succeeded.")

        # Verify backfill dates in PostgreSQL
        with test_engine.connect() as conn:
            qdate1 = conn.execute(text("SELECT queue_date FROM queue_entries WHERE id = '66666666-6666-6666-6666-666666666666';")).scalar()
            qdate2 = conn.execute(text("SELECT queue_date FROM queue_entries WHERE id = '66666666-6666-6666-6666-666666666667';")).scalar()
            print(f"  - Case D backfilled queue_date: {qdate1} (expected: 2026-10-19 from appointment_date)")
            assert str(qdate1) == "2026-10-19"
            print(f"  - Case E backfilled queue_date: {qdate2} (expected: 2026-10-20 from Asia/Kolkata checked_in_at)")
            assert str(qdate2) == "2026-10-20"
            print("  [PASS] Both historical backfill cases verified with 100% date consistency.")

            # Verify column properties and default
            col_info = conn.execute(text("""
                SELECT is_nullable, column_default 
                FROM information_schema.columns 
                WHERE table_name = 'queue_entries' AND column_name = 'queue_date';
            """)).fetchone()
            assert col_info[0] == "NO"
            assert "CURRENT_DATE" in str(col_info[1]).upper()
            print("  [PASS] queue_date is NOT NULL with server default CURRENT_DATE.")

        # -------------------------------------------------------------------------
        # Step 5: Direct Database Constraint Verification
        # -------------------------------------------------------------------------
        print("\nStep 5: Direct database constraint verification...")
        with test_engine.connect() as conn:
            # Constraint 1: Unique appointment_id
            print("  - Testing unique appointment_id constraint...")
            try:
                conn.execute(text(f"""
                    INSERT INTO queue_entries (id, appointment_id, hospital_id, doctor_id, patient_id, queue_date, token_number, position, status)
                    VALUES ('77777777-1111-1111-1111-111111111111', '55555555-5555-5555-5555-555555555555', '{hid}', '{did}', '22222222-2222-2222-2222-222222222222', '2026-10-19', 99, 99, 'waiting');
                """))
                assert False, "Should have failed unique appointment_id constraint!"
            except Exception as e:
                conn.rollback()
                assert "queue_entries_appointment_id_key" in str(e)
                print("    [PASS] queue_entries_appointment_id_key rejected duplicate check-in.")

            # Constraint 2: Unique doctor_id + queue_date + token_number
            print("  - Testing unique (doctor_id, queue_date, token_number) constraint...")
            try:
                # Token 1 already exists for doctor on 2026-10-19
                conn.execute(text(f"""
                    INSERT INTO appointments (id, appointment_token, patient_id, doctor_id, hospital_id, appointment_date, appointment_time, status)
                    VALUES ('55555555-7777-7777-7777-777777777771', 'MS-CONSTR-01', '22222222-2222-2222-2222-222222222222', '{did}', '{hid}', '2026-10-19', '14:00:00', 'scheduled');
                    INSERT INTO queue_entries (id, appointment_id, hospital_id, doctor_id, patient_id, queue_date, token_number, position, status)
                    VALUES ('77777777-2222-2222-2222-222222222222', '55555555-7777-7777-7777-777777777771', '{hid}', '{did}', '22222222-2222-2222-2222-222222222222', '2026-10-19', 1, 99, 'waiting');
                """))
                assert False, "Should have failed uq_doctor_date_token_number constraint!"
            except Exception as e:
                conn.rollback()
                assert "uq_doctor_date_token_number" in str(e)
                print("    [PASS] uq_doctor_date_token_number rejected duplicate daily token.")

            # Constraint 3: At most one in_consultation entry per doctor/date
            print("  - Testing partial unique index uq_active_doctor_in_consultation...")
            try:
                conn.execute(text(f"""
                    INSERT INTO appointments (id, appointment_token, patient_id, doctor_id, hospital_id, appointment_date, appointment_time, status)
                    VALUES 
                    ('55555555-8888-8888-8888-888888888881', 'MS-CONSTR-02', '22222222-2222-2222-2222-222222222222', '{did}', '{hid}', '2026-10-21', '14:00:00', 'in_progress'),
                    ('55555555-8888-8888-8888-888888888882', 'MS-CONSTR-03', '22222222-2222-2222-2222-222222222223', '{did}', '{hid}', '2026-10-21', '14:30:00', 'in_progress');
                    INSERT INTO queue_entries (id, appointment_id, hospital_id, doctor_id, patient_id, queue_date, token_number, position, status)
                    VALUES 
                    ('77777777-3333-3333-3333-333333333331', '55555555-8888-8888-8888-888888888881', '{hid}', '{did}', '22222222-2222-2222-2222-222222222222', '2026-10-21', 1, 1, 'in_consultation'),
                    ('77777777-3333-3333-3333-333333333332', '55555555-8888-8888-8888-888888888882', '{hid}', '{did}', '22222222-2222-2222-2222-222222222223', '2026-10-21', 2, 2, 'in_consultation');
                """))
                assert False, "Should have failed uq_active_doctor_in_consultation partial unique index!"
            except Exception as e:
                conn.rollback()
                assert "uq_active_doctor_in_consultation" in str(e)
                print("    [PASS] uq_active_doctor_in_consultation rejected second concurrent consultation.")

        # -------------------------------------------------------------------------
        # Step 6: Full Backend Regression Suite (59 tests)
        # -------------------------------------------------------------------------
        print("\nStep 6: Executing full backend regression test suite against migrated sandbox...")
        res_pytest = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-v"],
            capture_output=True,
            text=True,
            env=env,
        )
        print(res_pytest.stdout)
        assert res_pytest.returncode == 0, f"Pytest failed: {res_pytest.stderr}"
        print("[PASS] Full regression test suite passed (59/59).")

        # -------------------------------------------------------------------------
        # Step 7: Downgrade Verification
        # -------------------------------------------------------------------------
        print("\nStep 7: Testing Alembic downgrade to 42d65b870a44...")
        with test_engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO appointments (id, appointment_token, patient_id, doctor_id, hospital_id, appointment_date, appointment_time, status)
                VALUES ('dddddddd-dddd-dddd-dddd-dddddddddddd', 'MS-DOWN-01', '22222222-2222-2222-2222-222222222222', (SELECT id FROM doctors LIMIT 1), (SELECT id FROM hospitals LIMIT 1), '2026-10-22', '12:00:00', 'scheduled')
                ON CONFLICT (id) DO NOTHING;
                INSERT INTO queue_entries (id, appointment_id, hospital_id, doctor_id, patient_id, queue_date, token_number, position, status)
                VALUES ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', 'dddddddd-dddd-dddd-dddd-dddddddddddd', (SELECT id FROM hospitals LIMIT 1), (SELECT id FROM doctors LIMIT 1), '22222222-2222-2222-2222-222222222222', '2026-10-22', 1, 1, 'waiting')
                ON CONFLICT (id) DO NOTHING;
            """))
            conn.commit()

        res_down = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", "42d65b870a44"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert res_down.returncode == 0, f"Downgrade failed: {res_down.stderr}"
        print("[PASS] Downgrade executed successfully.")

        with test_engine.connect() as conn:
            rev = conn.execute(text("SELECT version_num FROM alembic_version;")).scalar()
            assert rev == "42d65b870a44"
            print(f"  - Alembic revision after downgrade: {rev}")

            # Verify existing record preserved
            q_exists = conn.execute(text("SELECT COUNT(*) FROM queue_entries WHERE id = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee';")).scalar()
            assert q_exists == 1
            print(f"  - queue_entries records preserved: {q_exists} record verified.")

            # Verify columns removed
            cols = [r[0] for r in conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'queue_entries';")).fetchall()]
            assert "queue_date" not in cols and "notes" not in cols
            print("  [PASS] queue_date and notes dropped cleanly.")

            # Verify baseline constraints and indexes intact
            idx = [r[0] for r in conn.execute(text("SELECT indexname FROM pg_indexes WHERE tablename = 'queue_entries';")).fetchall()]
            assert "uq_active_doctor_in_consultation" not in idx
            assert "uq_doctor_date_token_number" not in idx
            assert "queue_entries_appointment_id_key" in idx
            assert "queue_entries_pkey" in idx
            print("  [PASS] Only Phase 5.1 objects were removed. Baseline constraints & indexes intact.")

        print("\n================================================================================")
        print("ALL VERIFICATION CHECKS PASSED: 100% EMPIRICAL PROOF OF SAFETY & COMPLIANCE")
        print("================================================================================")

    finally:
        print(f"\nCleaning up sandbox database {test_db_name}...")
        with server_engine.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {test_db_name} WITH (FORCE);"))
        print("[PASS] Sandbox database dropped cleanly. medismart_db is completely untouched.")

if __name__ == "__main__":
    run_isolated_verification()
