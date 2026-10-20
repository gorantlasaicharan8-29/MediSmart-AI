---
phase: 5
plan: 5
wave: 4
depends_on: [1, 2, 3, 4]
gap_closure: true
---

# Plan 5.5: Security & Integrity Remediation

## Objective
Address the findings from the Phase 5 security and data-integrity audit:
1. **Patient Clinical-Notes Privacy Fix**: Ensure `GET /api/v1/queue/my` and check-in endpoints omit doctor consultation notes from patient-facing responses.
2. **Persistent Hospital-Admin Affiliation**: Add an additive nullable `users.hospital_id` foreign key referencing `hospitals.id`, define model relationships, and wire `auth.login`.
3. **Database-Validated Authorization**: Ensure `deps.get_current_user` and `_verify_doctor_access` validate hospital affiliation directly from active database records, ensuring immediate access revocation.
4. **Dedicated Test Database Isolation**: Configure `medismart_test_db` for pytest with a fail-safe assertion guard preventing tests from touching `medismart_db`.
5. **Comprehensive Remediation Tests**: Add targeted regression tests for notes privacy, hospital-admin login & revocation, cross-hospital access denial, and note input validation.

---

## Target Files & Database Objects

### 1. Database Objects
- **Table**: `users`
- **Additive Column**: `hospital_id UUID NULL`
- **Foreign Key**: `fk_users_hospital_id_hospitals FOREIGN KEY (hospital_id) REFERENCES hospitals(id) ON DELETE SET NULL`
- **Index**: `ix_users_hospital_id`
- **Alembic Migration**: `backend/alembic/versions/63b2c1f9d5e2_add_user_hospital_affiliation.py`
  - Reversible, additive-only migration.
  - Pre-checks: Verify `users` and `hospitals` tables exist before applying.

### 2. Backend Application Files
- `backend/app/models/user.py`: Add `hospital_id` mapped column and `hospital` relationship.
- `backend/app/models/hospital.py`: Add `hospital_admins` relationship.
- `backend/app/schemas/auth.py`: Add `hospital_id` to `UserResponse`.
- `backend/app/api/v1/auth.py`: In `login`, pass `hospital_id=user.hospital_id` to `create_access_token`.
- `backend/app/core/deps.py`: In `get_current_user`, assign `user.hospital_id` directly from `user.hospital_id` in database.
- `backend/app/schemas/queue.py`: Remove `notes` from `QueueEntryResponse` (patient-facing).
- `backend/app/api/v1/queue.py`: Omit `notes` from `get_my_queue_entry` and `check_in_appointment` responses. Retain `notes` in `DoctorQueueItemResponse`.

### 3. Test Configuration & Test Files
- `backend/tests/conftest.py`:
  - Enforce test database isolation (`TEST_DATABASE_URL` pointing to `medismart_test_db`).
  - Fail-safe guard: Assert database name contains `test` before any test runs.
  - Apply migrations to `medismart_test_db`.
- `backend/tests/test_remediation_phase5_5.py`:
  - Tests for clinical notes privacy, hospital-admin login flow, database revocation, and cross-hospital isolation.

---

## Strict Execution Protocol
1. **Safety Review**: Confirm `medismart_db` baseline (`hospitals=8, doctors=10, users=10, appointments=0, queue_entries=0`).
2. **Test Database Configuration**: Migrate and verify `medismart_test_db` in isolation.
3. **Approval Checkpoint**: Request approval before executing migration against `medismart_db`.
4. **Verification**: Run tests against `medismart_test_db`, run `npm run lint` and `npm run build`.
