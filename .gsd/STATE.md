# STATE.md — Project Memory

> Last updated: 2026-10-22 10:15 IST

## Current Position

- **Phase**: 7 — End-to-End Application Verification
- **Status**: Phase 7 successfully executed and verified across all 12 core workflows. Frontend build clean (3.18s), oxlint 0 warnings/0 errors on 36 files. 171/171 backend tests passed against `medismart_test_db`. Multi-workflow integration test verified all 12 workflows end-to-end (Auth, RBAC, Geo/Hospitals, Doctors/Slots, Partial Index Concurrency, Token Allocation, Advisory Locks, Privacy/Zero-Notes, Doctor Queue Lifecycle, XGBoost wait time, Logistic Regression no-show with 0.50 threshold, Cancellation and slot release). Development database `medismart_db` verified 100% untouched and pristine at Alembic revision `63b2c1f9d5e2` (8 hospitals, 10 doctors, 10 users, 0 appointments, 0 queue entries).
- **Next Up**: Awaiting review and approval before proceeding to next roadmap milestone.



## Phase 4 Verification Summary

- **Database-Enforced Concurrency (Partial Unique Index)**:
  - PostgreSQL Partial Unique Index:
    `CREATE UNIQUE INDEX uq_active_doctor_slot ON appointments (doctor_id, appointment_date, appointment_time) WHERE status != 'cancelled';`
  - Engine-level race condition protection. Two simultaneous requests for the same slot serialize at the database engine; the second is rejected with a unique constraint violation translated by FastAPI to **`409 Conflict`**.
  - Cancelling an appointment immediately releases the partial unique index slot for re-booking without any manual cleanup.
- **Unique Appointment Tracking Tokens**:
  - `appointment_token VARCHAR(50) UNIQUE NOT NULL` with dedicated index in PostgreSQL.
  - Generated via `MS-YYYYMMDD-XXXX` with bounded entropy retry loop (up to 5 attempts).
  - Safe error handling: database exceptions are caught and never exposed raw to clients.
- **Credential Provenance Tracking**:
  - Added `credential_status VARCHAR(50) DEFAULT 'pending_verification'` on `doctors`.
  - Distinguishes verified specialists (`verified`), demonstration profiles (`sample`), and unverified accounts (`pending_verification`).
  - Seeded demonstration doctors explicitly marked as `credential_status="sample"`.
  - Frontend displays distinct visual status badges (`✓ Verified Specialist`, `⚠️ Demo Profile`, `⏳ Verification Pending`).
- **Backend Boundary & Schedule Validation**:
  - Rejects past appointment dates with 400 Bad Request.
  - Strict slot boundaries: standard half-hour intervals (09:00 - 16:30, excluding lunch 13:00 - 14:00). Rejects irregular times (e.g. 10:17) with 400 Bad Request.
  - Validates doctor working days (`available_days`) and availability.
- **Patient Isolation & Transactional Cancellation**:
  - Patients can only view and cancel their own appointments (`403 Forbidden` on cross-patient access).
  - Cancellation acquires row lock (`with_for_update()`).
  - Patients are strictly barred from mutating appointments to `completed` or `in_progress`.
- **Database Status**:
  - Additive Alembic migration applied (`42d65b870a44`) with pre-checks for status consistency and duplicate active bookings.
  - Zero tables dropped or reset; all 5 core tables intact.
  - 8 seeded hospitals, 10 seeded doctors, 0 leftover test records.
- **Automated Tests**:
  - 54/54 pytest tests passing in 3.05s (12 Phase 1 + 15 Phase 2 + 13 Phase 3 + 14 Phase 4).
- **Frontend Status**:
  - `oxlint`: 0 errors, 0 warnings across 29 files.
  - Vite production build: clean build in 522ms.

## Context Dump

### Decisions Made
- Decision 21: Use PostgreSQL partial unique index `uq_active_doctor_slot` (`WHERE status != 'cancelled'`) for true database-enforced booking concurrency safety.
- Decision 22: Structure unique appointment tracking tokens as `MS-YYYYMMDD-XXXX` with bounded retry loop and PostgreSQL unique index.
- Decision 23: Default doctor credential status to `pending_verification` to ensure no doctor is marked verified without an authentic credential check.
- Decision 24: Pessimistic row locking (`with_for_update()`) on cancellation to guarantee safe atomic status transitions.

### Files of Interest
- `backend/app/models/appointment.py`: Appointment model with partial unique index and tracking token.
- `backend/app/models/doctor.py`: Doctor model with credential provenance, bio, and working days.
- `backend/app/api/v1/doctors.py`: Public doctor search and dynamic 30-min slot calculation.
- `backend/app/api/v1/appointments.py`: Transactional booking with 409 Conflict handling and patient isolation.
- `frontend/src/components/appointments/BookingModal.jsx`: Dynamic slot calendar with 409 conflict handling.
- `frontend/src/pages/Appointments.jsx`: Patient dashboard with cancellation workflow.
- `backend/tests/test_appointments.py`: 14-test concurrency, token uniqueness, and RBAC suite.

## Phase 5.1 Verification Summary
- **Additive Migration Applied to `medismart_db`**: `52a1b9e8c4d1`
  - Added `queue_date` (Date, NOT NULL, server_default=CURRENT_DATE) with index `ix_queue_entries_queue_date`.
  - Added `notes` (Text, nullable) for consultation/reception notes.
  - Added unique constraint `uq_doctor_date_token_number` on `(doctor_id, queue_date, token_number)`.
  - Added partial unique index `uq_active_doctor_in_consultation` on `(doctor_id, queue_date)` WHERE `status = 'in_consultation'`.
  - Preserved unique constraint on `appointment_id` (`queue_entries_appointment_id_key`).
  - Pre-checks embedded in migration: status validation, duplicate consultations, duplicate tokens, 4-way FK integrity, and historical date source validity.
  - Backfill policy: primary `appointments.appointment_date`, fallback `(checked_in_at AT TIME ZONE 'Asia/Kolkata')::date`.
  - Zero tables dropped or reset; all 5 core tables intact.
  - Record counts: 8 hospitals, 10 doctors, 10 users, 0 appointments, 0 queue entries.
- **Automated Tests**:
  - 59/59 pytest tests passing in 3.73s (54 baseline + 5 Phase 5.1 queue model and constraint tests).
- **Frontend Status**:
  - Vite production build: clean build in 633ms.

## Phase 5.2 Verification Summary
- **Backend Queue REST APIs & WebSocket Manager Implemented**:
  - `POST /api/v1/queue/check-in`: Concurrency-safe daily token allocation using PostgreSQL two-argument transaction-level advisory locking (`pg_advisory_xact_lock(hashtext(:doc_id), hashtext(:clinic_date))`). Generates immutable `token_number` (`Q-001`, `Q-002`), dynamic initial position, and baseline wait time.
  - `GET /api/v1/queue/my`: Patient queue status with dynamic position recalculation.
  - `GET /api/v1/queue/doctor/{id}/public-board`: Zero-PII public waiting room monitor view.
  - `GET /api/v1/queue/doctor/{id}`: Clinical queue view for assigned doctor/admin.
  - `POST /api/v1/queue/{id}/call`: Row-locked call action (`with_for_update()`), active consultation serialization, 409 Conflict protection, atomic appointment synchronization to `in_progress`.
  - `POST /api/v1/queue/{id}/complete`: Row-locked completion, appointment synchronized to `completed`.
  - `POST /api/v1/queue/{id}/skip`: Row-locked skip, appointment synchronized to `no_show`.
  - `POST /api/v1/queue/{id}/recall`: Row-locked recall, restores appointment to `scheduled`.
  - `DELETE /api/v1/queue/{id}`: Row-locked cancel, marks queue and appointment `cancelled`.
  - `WebSocket /api/v1/queue/ws/{id}`: Scoped WebSocket with handshake auth, origin validation, event isolation per doctor, and clean disconnect handling.
- **Automated Tests**:
  - 85/85 pytest tests passing in 5.46s (59 baseline + 26 Phase 5.2 queue engine tests).
  - Verified concurrent HTTP check-ins and simultaneous call-next requests against PostgreSQL.
- **Database Status**:
  - `medismart_db` intact: 8 hospitals, 10 doctors, 10 users, 0 appointments, 0 queue entries.
- **Frontend Status**:
  - `oxlint`: 0 errors, 0 warnings across 29 files.
  - Vite production build: clean build in 1.74s.

## Phase 5.3 Verification Summary
- **Scope A — Patient Live Queue Tracker**:
  - Live token badge, dynamic position countdown, and consultation progress stepper (Checked In -> Waiting -> In Consultation -> Completed).
  - Turn-approaching alert banner with audio chime when position <= 2.
  - Interactive self check-in card when patient has no active token for today.
  - Cancel queue entry confirmation modal with atomic status updates.
- **Scope B — Waiting Room Monitor Display**:
  - Full-screen TV/wall display with high contrast and extra-large typography (text-7xl to text-9xl).
  - "Now Serving" hero token card with pulsating beacon.
  - "Next in Line" upcoming tokens grid showing token display, position, and estimated wait times.
  - Zero-PII privacy guarantee: no patient names, phone numbers, emails, or clinical notes rendered.
  - Web Audio announcement chime and visual pulse highlight on `PATIENT_CALLED`.
  - Doctor queue selector dropdown and fullscreen toggle button.
  - Dedicated standalone TV kiosk routes at `/queue/monitor` and `/queue/monitor/:doctorId`.
- **Dual-Transport Real-Time Engine**:
  - `useQueueSocket` hook with automatic reconnect and 10-second polling fallback.
- **Verification Results**:
  - Frontend lint (`oxlint`): 0 warnings, 0 errors across 33 files.
  - Frontend build (`vite build`): Clean build in 4.81s.
  - Backend regression suite (`pytest`): 93 passed in 10.22s.
  - Database integrity on `medismart_db`: 8 hospitals, 10 doctors, 10 users, 0 appointments, 0 queue entries. Zero schema alterations.

## Phase 5.4 Verification Summary
- **Doctor Consultation Queue Console (`DoctorQueueConsole.jsx`)**:
  - Doctor scoping: automatically matches authenticated doctor account against clinical profile (`Doctor.user_id === user.id`).
  - Active consultation workspace: patient demographics, scheduled slot, token badge (`Q-002`), live elapsed timer (MM:SS), and clinical notes input.
  - Lifecycle actions: "Complete Consultation" (`POST /{id}/complete`) and "Skip Patient" (`POST /{id}/skip`) with atomic status sync to appointment table.
  - "Call Next Patient" quick action on exam room hero card when room is available.
  - Waiting queue list with individual "Call" and "Skip" action buttons.
  - Skipped patients section with 1-click "↩ Recall" (`POST /{id}/recall`) back into waiting line.
  - KPI metric summary cards: Total Waiting, In Consultation, Completed Today, Skipped Today.
  - Concurrency 409 conflict handling: clear, non-blocking alert if doctor attempts to call while another consultation is active.
- **Route & Page Integration**:
  - `Queue.jsx` Tab 3 ("🩺 Doctor Console") with automatic selection for doctor role and deep linking (`?tab=doctor`).
  - Dedicated protected routes `/queue/doctor` and `/queue/doctor/:doctorId` restricted to clinical staff.
- **Verification Results**:
  - Frontend lint (`oxlint`): 0 warnings, 0 errors across 34 files.
  - Frontend build (`vite build`): Clean build in 618ms.
  - Backend regression suite (`pytest`): 93 passed in 7.31s.
  - Database integrity on `medismart_db`: 8 hospitals, 10 doctors, 10 users, 0 appointments, 0 queue entries. Zero schema alterations.

## Phase 5.5 Verification Summary
- **Patient Clinical-Notes Privacy Fix**:
  - Removed `notes` from `QueueEntryResponse` (`GET /api/v1/queue/my` and check-in response).
  - Retained `notes` strictly in `DoctorQueueItemResponse` and `DoctorQueueResponse` for authenticated clinical staff.
  - Confirmed public monitor (`QueuePublicBoardResponse`) and WebSocket messages contain zero patient PII and zero clinical notes.
- **Persistent Hospital Affiliation & Database-Validated Authorization**:
  - Additive migration `63b2c1f9d5e2` applied to `medismart_db`.
  - Added nullable `users.hospital_id` UUID column with foreign key referencing `hospitals.id` (`ON DELETE SET NULL`) and lookup index `ix_users_hospital_id`.
  - Authoritative database validation in `deps.get_current_user`: hospital affiliation is loaded directly from PostgreSQL and validated against JWT claims.
  - Client headers (e.g. `X-Hospital-Id`) and spoofed/stale JWT claims are rejected.
  - Removing an affiliation in the database results in immediate `401`/`403` fail-closed authorization denial on subsequent requests.
  - Administrative provisioning CLI (`scripts/create_admin.py`) accepts `--hospital-id` and validates target hospital existence. Public registration blocks administrative roles.
- **Strict Test Database Isolation**:
  - `backend/tests/conftest.py` enforces isolation guard redirecting all test executions to `medismart_test_db`.
  - Hard fail-fast assertion prevents test suite execution if `medismart_test_db` is not the target.
- **Verification Results**:
  - Backend regression suite (`pytest tests/ -v`): 105 passed in 8.42s across all 8 test modules on `medismart_test_db`.
  - Frontend lint (`oxlint`): 0 warnings, 0 errors across 34 files.
  - Frontend production build (`vite build`): Clean build in 572ms.
  - Active `medismart_db` baseline: revision `63b2c1f9d5e2`, 8 hospitals, 10 doctors, 10 users (all with `hospital_id IS NULL`), 0 appointments, 0 queue entries.

## Next Steps
1. Phase 5.5 Security & Integrity Remediation is COMPLETE.
2. Await user instructions for Phase 6 (ML Predictions: Wait Time & No-Show).

