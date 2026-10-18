---
phase: 4
plan: 4
wave: 2
depends_on: [1, 2, 3]
gap_closure: false
---

# Plan 4.4: Automated Test Suite & Full Integration Verification

## Objective
Implement comprehensive automated tests in `backend/tests/test_appointments.py` covering concurrent booking race conditions, database-enforced double-booking prevention (409 Conflict), token uniqueness, slot boundary validation, doctor availability, patient data isolation (403 Forbidden), and cancellation workflows, followed by full regression testing and frontend production build verification.

## Context
- `backend/tests/`
- `backend/app/api/v1/doctors.py`
- `backend/app/api/v1/appointments.py`
- `frontend/`

## Security & Architecture Rules
1. **Non-Destructive Test Execution**:
   - Tests MUST NOT drop, reset, or truncate tables in `medismart_db`.
   - Test data uses unique prefixes (`test_appt_*`, `test_appt_user_*`) and is deleted by teardown fixtures.
2. **Comprehensive Concurrency & Validation Testing**:
   - **Simultaneous booking test**: Fire concurrent asynchronous booking requests targeting the exact same `(doctor_id, date, time)` slot. Assert that one succeeds with 201 Created and the other triggers the PostgreSQL `uq_active_doctor_slot` partial unique constraint and returns `409 Conflict`.
   - **Collision-safe token test**: Verify appointment tokens conform to `MS-YYYYMMDD-XXXX` and that uniqueness is enforced in PostgreSQL.
   - **Slot boundary validation**: Assert booking with invalid/non-conforming slot times (e.g. 10:17 AM or midnight) returns `400 Bad Request`.
   - **Past date validation**: Assert booking for a past date returns `400 Bad Request`.
   - **Doctor availability validation**: Assert booking on a doctor's non-working day returns `400 Bad Request`.
   - **Patient data isolation**: Assert Patient A cannot view or cancel Patient B's appointment (`403 Forbidden`).
   - **Status transition integrity**: Assert patients cannot mark appointments as `completed` or `no_show`.
   - **Slot freeing on cancellation**: Assert cancelling an appointment immediately frees the slot for another patient to book without conflict.

## Tasks

<task type="auto" effort="medium">
  <name>Create automated doctor and appointment test suite</name>
  <files>
    backend/tests/test_appointments.py
  </files>
  <action>
    1. Create `backend/tests/test_appointments.py`:
       - `test_list_doctors_public`: Public directory listing and pagination.
       - `test_filter_doctors_by_specialty_and_hospital`: Multi-facet filtering.
       - `test_doctor_slots_schedule`: Available slot generation excluding booked slots.
       - `test_book_appointment_success`: Validates token format (`MS-YYYYMMDD-XXXX`) and 201 status.
       - `test_simultaneous_booking_conflict`: Concurrently issues two booking requests for the same slot; asserts exactly one succeeds (201) and the other returns 409 Conflict.
       - `test_past_date_booking_rejected`: Rejects past date with 400 Bad Request.
       - `test_invalid_slot_time_boundary_rejected`: Rejects non-half-hour time with 400 Bad Request.
       - `test_doctor_unavailable_day_rejected`: Rejects booking on a doctor's off-day.
       - `test_patient_can_only_view_own_appointments`: Asserts 403 Forbidden on cross-patient snooping.
       - `test_cancel_appointment_frees_slot`: Validates cancellation and subsequent successful re-booking of the freed slot.
       - `test_patient_cannot_set_arbitrary_status`: Rejects unauthorized status mutations.
       - Non-destructive fixture cleans up test data after execution.
  </action>
  <verify>
    .\.venv\Scripts\pytest.exe tests/test_appointments.py -v (in backend/)
  </verify>
  <done>
    - Concurrency and conflict tests pass
    - Validation and RBAC isolation verified
    - Non-destructive execution confirmed
  </done>
</task>

<task type="auto" effort="low">
  <name>Run full regression test suite and frontend production build</name>
  <files>
    backend/tests/
    frontend/dist/
  </files>
  <action>
    1. Run all backend tests: `.\.venv\Scripts\pytest.exe -v` (expecting 50+ tests from Phases 1-4 to pass).
    2. Check PostgreSQL database integrity to ensure no tables dropped and 0 leftover test records.
    3. Run frontend lint: `npm run lint` (0 errors, 0 warnings).
    4. Run frontend production build: `npm run build` (clean Vite bundle).
  </action>
  <verify>
    .\.venv\Scripts\pytest.exe -v (in backend/)
    npm run build (in frontend/)
  </verify>
  <done>
    - 100% backend tests pass
    - Database integrity verified
    - Frontend build succeeds with zero lint warnings
  </done>
</task>

## Must-Haves
- [ ] Concurrency test validates database partial unique index under simultaneous bookings
- [ ] Tests cover slot conflict detection (409 Conflict)
- [ ] Tests cover cross-patient data isolation (403 Forbidden)
- [ ] Tests verify cancellation and slot re-availability
- [ ] Boundary validation tests cover past dates and non-conforming times
- [ ] All tests run non-destructively
- [ ] Frontend builds cleanly with zero errors
