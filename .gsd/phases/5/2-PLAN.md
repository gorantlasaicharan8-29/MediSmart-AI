---
phase: 5
plan: 2
wave: 1
gap_closure: false
---

# Plan 5.2: Real-Time Queue Engine & Concurrency-Safe Daily Token Allocation APIs

## 1. Objective & Scope
Implement high-concurrency FastAPI REST endpoints and scoped WebSocket streaming for the digital queue management system:
1. Patient check-in by appointment tracking token or ID with clinic-date validation in `Asia/Kolkata`.
2. PostgreSQL transaction-level advisory locking for deterministic, collision-safe daily token generation and position tracking.
3. Concurrency-protected doctor queue controls (Call Next, In Consultation, Complete, Skip, Recall, Cancel) with pessimistic row locking (`with_for_update()`) and database-enforced single active consultation partial unique index.
4. Deterministic waiting position calculation and baseline wait-time estimation (`waiting_ahead_count * 15` min).
5. Strict resource-level role-based authorization (RBAC) and privacy-preserving public board view (zero PII).
6. Scoped WebSocket notification system with secure handshake, origin validation, event isolation per doctor, and REST polling fallback.
7. Comprehensive automated test suite verifying concurrency, state transitions, RBAC, and zero regression against `medismart_db`.

---

## 2. Core Architecture & Mandatory Requirements

### 2.1 Token Allocation & Concurrency Safety
- **Clinic-Date Policy (`Asia/Kolkata`)**:
  - Check-in dates and queue dates evaluate in `Asia/Kolkata`:
    ```python
    from zoneinfo import ZoneInfo
    CLINIC_TZ = ZoneInfo("Asia/Kolkata")
    clinic_today = datetime.now(CLINIC_TZ).date()
    ```
  - Rejects check-in if `appointment.appointment_date != clinic_today` with `400 Bad Request` ("Check-in is only available on the day of the appointment").
- **Deterministic Transaction-Scoped Advisory Lock**:
  - Uses PostgreSQL two-argument 32-bit transaction advisory lock `pg_advisory_xact_lock(int, int)`:
    ```python
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:doctor_id), hashtext(:clinic_date));"),
        {"doctor_id": str(doctor_id), "clinic_date": str(clinic_today)}
    )
    ```
  - Lock is acquired before querying `MAX(token_number)`.
  - Automatically released by PostgreSQL at transaction commit or rollback (`_xact_lock`).
  - Next token calculation: `SELECT COALESCE(MAX(token_number), 0) + 1 FROM queue_entries WHERE doctor_id = :d AND queue_date = :dt`.
  - Insertion and commit happen inside the same transaction.
  - Final database safeguard: `uq_doctor_date_token_number` unique constraint. Uniqueness collisions are caught and translated to `409 Conflict` without exposing database internals.

### 2.2 Call-Next Concurrency & Serialization
- **Serialization**:
  - `POST /api/v1/queue/{entry_id}/call` acquires the doctor/date advisory lock `pg_advisory_xact_lock(hashtext(:doctor_id), hashtext(:clinic_date))` and acquires row lock `with_for_update()` on the target `QueueEntry`.
  - Checks if another entry is currently `in_consultation` for this `doctor_id` on `queue_date`. If found, immediately returns `409 Conflict` ("Another patient is currently in consultation. Please complete or skip the active consultation first.").
  - Supported at the database engine level by partial unique index `uq_active_doctor_in_consultation` on `(doctor_id, queue_date)` WHERE `status = 'in_consultation'`.
  - Queue status transition to `in_consultation` and appointment status transition to `in_progress` occur atomically in the same database transaction.

### 2.3 Queue Position Ordering Policy
- **Deterministic Ordering**:
  - Token numbers are assigned sequentially at check-in and are immutable (`token_number`).
  - Waiting queue order is strictly ordered by `token_number ASC` for entries where `status = 'waiting'`.
  - Waiting position for an entry is deterministically calculated as:
    ```sql
    SELECT COUNT(*) + 1 
    FROM queue_entries 
    WHERE doctor_id = :d AND queue_date = :dt 
      AND status = 'waiting' 
      AND token_number < :my_token_number;
    ```
  - Position becomes `0` once `in_consultation`, `completed`, `skipped`, or `cancelled`.
  - Baseline estimated wait time: `(position - 1) * 15` minutes for waiting entries (0 when in consultation).
  - Positions are consistently recalculated after call, complete, skip, recall, and cancellation.

### 2.4 Lifecycle State Machine & Synchronized Transitions
All queue status updates are executed in a single transaction with atomic appointment status synchronization:

```
[Appointment: scheduled]
           │
           ▼ (Patient check-in on clinic date)
    [Queue: waiting]
           │
   ┌───────┴────────────────────────┐
   ▼ (call-next)                    ▼ (skip)
[Queue: in_consultation]     [Queue: skipped]
[Appt: in_progress]          [Appt: no_show]
   │       │                        │
   │       ▼ (skip)                 ▼ (recall)
   │ [Queue: skipped]        [Queue: waiting]
   │ [Appt: no_show]         [Appt: scheduled]
   │
   ▼ (complete)
[Queue: completed]
[Appt: completed]
```

- **Cancellation Rules**:
  - Patients can cancel their queue entry (`DELETE /api/v1/queue/{entry_id}`) ONLY if status is `waiting` or `skipped`.
  - Patients CANNOT cancel entries already `in_consultation` or `completed` (`400 Bad Request`).
  - Cancellation atomically transitions queue entry to `cancelled` and appointment to `cancelled`.
  - If an appointment is cancelled, it CANNOT be recalled into the queue (`400 Bad Request`).

### 2.5 Resource-Level Authorization & Privacy
- **Patient Isolation**:
  - Check-in requires `current_user.id == appointment.patient_id` (or authorized clinic staff).
  - `GET /api/v1/queue/my`: Patients can only retrieve their own active queue entry. Returns `404` or empty if no active check-in exists.
- **Doctor Scoping**:
  - `POST /api/v1/queue/{entry_id}/call|complete|skip|recall`: Authorized ONLY for the assigned doctor (`current_user.id == doctor.user_id`) or an administrator of that doctor's hospital. Other doctors receive `403 Forbidden`.
- **Hospital Admin Scoping**:
  - Hospital administrators can only view/manage queues for doctors belonging to their authorized hospital (`doctor.hospital_id == current_user.hospital_id`).
- **Public Board Privacy**:
  - `GET /api/v1/queue/doctor/{doctor_id}/public-board`:
    - Publicly accessible for waiting room monitors.
    - Strictly ZERO PII: returns only `token_display` (e.g. `Q-001`), `token_number`, `position`, `status`, and `estimated_wait_minutes`.
    - No patient names, emails, phones, user IDs, appointment IDs, or clinical notes are exposed.

### 2.6 WebSocket Architecture & Real-Time Isolation
- **Endpoint**: `/api/v1/queue/ws/{doctor_id}`
- **Authentication Handshake**:
  - Authenticates before accepting connection.
  - Extracts JWT token from HttpOnly cookie `access_token` (browser clients) or `Authorization: Bearer <token>` header.
  - Validates Origin against `settings.CORS_ORIGINS`.
  - Rejects unauthenticated connections with `1008 Policy Violation` without leaking tokens in URL queries.
- **Queue Room Scoping**:
  - Connections are subscribed exclusively to `rooms[doctor_id]`.
  - Broadcasts on `doctor_A` are delivered ONLY to subscribers of `doctor_A`.
  - Prevents cross-doctor event leakage.
- **Event Payload**:
  - Lightweight and privacy-preserving:
    ```json
    {
      "event": "QUEUE_UPDATED",
      "doctor_id": "...",
      "action": "CHECKED_IN|PATIENT_CALLED|COMPLETED|SKIPPED|RECALLED|CANCELLED",
      "token_display": "Q-001",
      "timestamp": "2026-10-19T23:00:00Z"
    }
    ```
- **Connection Resilience**:
  - Clean `WebSocketDisconnect` handling removing dead sockets without memory leaks.
  - REST polling fallback (`GET /api/v1/queue/my` and `/public-board`) remains fully functional.

---

## 3. Implementation Tasks Breakdown

### Task 1: Schemas & WebSocket Connection Manager
- **Files**:
  - `backend/app/schemas/queue.py`
  - `backend/app/schemas/__init__.py`
  - `backend/app/core/websocket.py`
- **Actions**:
  - Define `QueueCheckInRequest`, `QueueEntryResponse`, `QueuePublicItem`, `QueuePublicBoardResponse`, `DoctorQueueItemResponse`, `QueueActionRequest`.
  - Implement `QueueConnectionManager` with scoped rooms per `doctor_id`, origin validation, safe broadcast, and disconnect handlers.

### Task 2: REST & WebSocket Endpoints
- **Files**:
  - `backend/app/api/v1/queue.py`
  - `backend/app/api/v1/__init__.py`
- **Actions**:
  - `POST /api/v1/queue/check-in`: Advisory-locked token allocation, Asia/Kolkata date check, appointment sync, WS broadcast.
  - `GET /api/v1/queue/my`: Patient queue status with dynamic position.
  - `GET /api/v1/queue/doctor/{doctor_id}/public-board`: Zero-PII public board.
  - `GET /api/v1/queue/doctor/{doctor_id}`: Authenticated clinical queue for doctor/admin.
  - `POST /api/v1/queue/{entry_id}/call`: Row-locked call action with 409 conflict protection.
  - `POST /api/v1/queue/{entry_id}/complete`: Row-locked completion.
  - `POST /api/v1/queue/{entry_id}/skip`: Row-locked skip.
  - `POST /api/v1/queue/{entry_id}/recall`: Row-locked recall.
  - `DELETE /api/v1/queue/{entry_id}`: Row-locked cancel.
  - `WebSocket /api/v1/queue/ws/{doctor_id}`: Authenticated real-time streaming endpoint.

### Task 3: Automated Test Suite
- **Files**:
  - `backend/tests/test_queue_api.py`
- **Actions**:
  - Implement all 27 targeted test cases outlined below.

---

## 4. Test Verification Matrix (27 Targeted Tests)

| Requirement | Test Name | Specific Verification |
| :--- | :--- | :--- |
| **Token Allocation** | `test_checkin_valid_appointment_token` | Successful check-in via appointment token `MS-YYYYMMDD-XXXX`. |
| **Token Allocation** | `test_checkin_valid_appointment_id` | Successful check-in via UUID `appointment_id`. |
| **Token Allocation** | `test_checkin_invalid_or_unknown_token_rejected_404` | Non-existent appointment token rejected with 404 Not Found. |
| **Token Allocation** | `test_checkin_duplicate_prevention_409` | Second check-in attempt for same appointment rejected with 409 Conflict. |
| **Token Allocation** | `test_concurrent_http_checkins_distinct_sequential_tokens` | 5 simultaneous HTTP check-ins against PostgreSQL; verifies advisory lock serializes allocation and produces distinct sequential tokens (`Q-001` to `Q-005`) without duplicates. |
| **Date Policy** | `test_checkin_past_date_rejected_400` | Appointment scheduled on yesterday rejected with 400 Bad Request. |
| **Date Policy** | `test_checkin_future_date_rejected_400` | Appointment scheduled on tomorrow rejected with 400 Bad Request. |
| **Call Concurrency** | `test_doctor_call_next_success_and_status_sync` | Calling next patient sets queue to `in_consultation` and appointment to `in_progress`. |
| **Call Concurrency** | `test_doctor_call_next_conflict_when_already_in_consultation_409` | Calling another patient while one is in consultation rejected with 409 Conflict. |
| **Call Concurrency** | `test_simultaneous_call_next_concurrency_409` | Two simultaneous HTTP call-next requests for same doctor serialize: exactly one succeeds (200), other receives 409 Conflict. |
| **Lifecycle Transitions** | `test_doctor_complete_consultation_and_status_sync` | Completing consultation sets queue to `completed` and appointment to `completed`. |
| **Lifecycle Transitions** | `test_doctor_skip_patient_and_status_sync` | Skipping patient sets queue to `skipped` and appointment to `no_show`. |
| **Lifecycle Transitions** | `test_doctor_recall_skipped_patient_success` | Recalling skipped patient returns queue to `waiting` and appointment to `scheduled`. |
| **Lifecycle Transitions** | `test_doctor_cannot_recall_cancelled_appointment_400` | Recalling a queue entry whose appointment was cancelled rejected with 400 Bad Request. |
| **Lifecycle Transitions** | `test_patient_cannot_cancel_active_consultation_400` | Patient attempting to cancel entry while `in_consultation` rejected with 400 Bad Request. |
| **Lifecycle Transitions** | `test_patient_can_cancel_waiting_entry_and_status_sync` | Patient cancelling `waiting` entry sets queue to `cancelled` and appointment to `cancelled`. |
| **Queue Positions** | `test_queue_position_consistency_after_each_lifecycle_action` | Verifies deterministic queue positions (`1, 2, 3...`) across 4 patients as patients are called, completed, skipped, recalled, and cancelled. |
| **Authorization** | `test_checkin_wrong_patient_rejected_403` | Patient B attempting to check in for Patient A's appointment rejected with 403 Forbidden. |
| **Authorization** | `test_patient_my_queue_status_isolation` | Patient A queries `/api/v1/queue/my` and sees only their own entry; Patient B sees empty/404. |
| **Authorization** | `test_doctor_cross_queue_authorization_403` | Doctor B attempting to call/skip Doctor A's patient rejected with 403 Forbidden. |
| **Authorization** | `test_hospital_admin_scoping_authorization` | Admin of Hospital X attempting to manage queue of Hospital Y doctor rejected with 403 Forbidden. |
| **Privacy** | `test_public_board_zero_pii` | Verifies public board JSON contains strictly zero patient names, emails, phones, notes, or patient UUIDs. |
| **WebSockets** | `test_websocket_unauthenticated_connection_rejected` | WebSocket connection without valid token rejected with 1008 Policy Violation. |
| **WebSockets** | `test_websocket_broadcast_delivery_on_queue_mutation` | Verifies connected client on `doctor_A` receives `QUEUE_UPDATED` event on check-in and call. |
| **WebSockets** | `test_websocket_cross_doctor_event_isolation` | Verifies subscriber to `doctor_A` receives zero events when `doctor_B` queue mutates. |
| **Transactions** | `test_database_transaction_rollback_on_failed_queue_mutation` | Verifies that an unhandled failure during status mutation rolls back both queue and appointment. |
| **Regression** | `test_full_backend_regression_suite` | Complete existing regression suite (59 baseline tests) executes and passes 100%. |

---

## 5. Safety & Guardrails
- `medismart_db` will never be dropped, truncated, reset, or recreated.
- Existing records (10 doctors, 8 hospitals, 10 users) preserved.
- No modifications to existing Alembic migrations (`52a1b9e8c4d1`).
- No ML prediction in Plan 5.2 (baseline calculation: `(position - 1) * 15` min).
- No start on Plans 5.3 or 5.4.
