---
phase: 5
plan: 4
wave: 2
depends_on: [1, 2, 3]
gap_closure: false
---

# Plan 5.4: Queue Test Suite, Security Tests, Concurrency Tests & Full Regression

## Objective
Implement a comprehensive automated test suite in `backend/tests/test_queue.py` validating queue check-in rules, duplicate prevention, date boundary validation, concurrency protections (simultaneous call prevention), patient data isolation, doctor queue transitions, WebSocket broadcasts, followed by full system regression testing and clean production build verification.

## Context
- `backend/tests/`
- `backend/app/api/v1/queue.py`
- `backend/app/core/websocket.py`
- `frontend/`

## Safety & Architecture Rules
1. **Non-Destructive Test Execution**:
   - Tests MUST NOT drop, reset, or truncate tables in `medismart_db`.
   - Test data uses unique prefixes (`test_queue_*`) and is deleted by teardown fixtures.
2. **Comprehensive Concurrency & Integrity Testing**:
   - **Simultaneous consultation prevention**: Concurrently fire requests attempting to call two patients into consultation for the same doctor. Assert one succeeds and the other is blocked by the database partial unique index with `409 Conflict`.
   - **Duplicate check-in prevention**: Assert checking in the same appointment twice fails at the database level.
   - **Date boundary enforcement**: Assert checking in for tomorrow or past appointments returns `400 Bad Request`.
   - **Patient isolation & privacy**: Assert cross-patient access returns `403 Forbidden`, and public queue boards anonymize patient PII.
   - **Status transition cascades**: Assert completing a queue consultation transitions the underlying appointment to `completed`, and skipping transitions the appointment to `no_show`.
   - **WebSocket broadcast verification**: Validate that WebSocket subscribers receive event payloads on check-in, call, and completion.

## Tasks

<task type="auto" effort="high">
  <name>Create automated queue test suite with concurrency and security tests</name>
  <files>
    backend/tests/test_queue.py
  </files>
  <action>
    1. Create `backend/tests/test_queue.py`:
       - `test_queue_check_in_success`: Validates today's appointment check-in, token formatting `Q-001`, position 1, baseline wait time.
       - `test_queue_check_in_duplicate_rejected`: Rejects duplicate check-in at DB level.
       - `test_queue_check_in_past_or_future_date_rejected`: Rejects past or future appointments with 400 Bad Request.
       - `test_queue_check_in_cancelled_appointment_rejected`: Rejects cancelled appointment check-in.
       - `test_simultaneous_call_conflict_prevention`: Concurrency test proving partial unique index blocks calling multiple patients simultaneously (409 Conflict).
       - `test_patient_can_only_view_own_queue_entry`: Confirms 403 Forbidden on cross-patient snooping.
       - `test_doctor_call_next_advances_positions`: Validates queue position updates as patients are called.
       - `test_doctor_complete_marks_appointment_completed`: Validates status transition cascade to appointment `completed`.
       - `test_doctor_skip_marks_appointment_no_show`: Validates status transition cascade to appointment `no_show`.
       - `test_public_queue_board_masks_pii`: Asserts public board response omits patient names and emails.
       - `test_websocket_queue_connection_and_broadcast`: Verifies WebSocket connection and real-time broadcast.
       - Fixtures provide non-destructive teardown.
  </action>
  <verify>
    .\.venv\Scripts\pytest.exe tests/test_queue.py -v (in backend/)
  </verify>
  <done>
    - Queue test suite passes 100%
    - Concurrency and conflict protections verified
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
    1. Run all backend tests: `.\.venv\Scripts\pytest.exe -v` (expecting 65+ tests from Phases 1-5 to pass).
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
- [ ] Concurrency test validates partial unique index blocking simultaneous consultations
- [ ] Duplicate check-in prevented
- [ ] Date boundaries strictly enforced
- [ ] PII masked on public board
- [ ] Full regression passes with zero leftover test records
- [ ] Frontend builds cleanly with zero errors
