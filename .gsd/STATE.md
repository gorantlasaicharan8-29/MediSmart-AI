# STATE.md — Project Memory

> Last updated: 2026-10-18 16:50 IST

## Current Position

- **Phase**: 4 — Doctor Discovery & Appointment Booking (COMPLETE ✓)
- **Status**: Verified & Committed
- **Completed Plans in Phase 4**:
  - Plan 4.1: Doctor & Appointment Model Enhancements, Concurrency Index & Seed Data
  - Plan 4.2: Backend Doctor & Appointment APIs with Slot Validation, Concurrency Safety & RBAC
  - Plan 4.3: Frontend Doctor Directory, Slot Booking Modal & Appointment Management
  - Plan 4.4: Automated Test Suite & Full Integration Verification
- **Next Up**: Phase 5 — Digital Queue & Real-Time Updates

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

## Next Steps
1. Discuss / Plan Phase 5: Digital Queue & Real-Time Updates.
