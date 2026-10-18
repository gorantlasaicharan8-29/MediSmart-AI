---
phase: 4
plan: 2
wave: 1
gap_closure: false
---

# Plan 4.2: Backend Doctor & Appointment APIs with Slot Validation, Concurrency Safety & RBAC

## Objective
Implement FastAPI endpoints for doctor discovery, dynamic slot calculation, transactional appointment booking with database-level conflict handling (409 Conflict), collision-safe token generation, rigorous slot boundary validation, strict patient data isolation, and safe cancellation workflows.

## Context
- `backend/app/models/doctor.py`
- `backend/app/models/appointment.py`
- `backend/app/models/hospital.py`
- `backend/app/core/deps.py` (`get_current_active_user`, `require_roles`)

## Security & Architecture Rules
1. **Concurrency Safety & Double-Booking Protection**:
   - Booking uses database-level concurrency protection.
   - Any concurrent request attempting to book an occupied slot trips PostgreSQL's `uq_active_doctor_slot` partial unique index (or application lock).
   - Catches database `IntegrityError` on slot collision and translates it to **`409 Conflict`** (*"This appointment time slot is already booked. Please choose another slot."*).
2. **Collision-Safe Token Generation**:
   - Generates cryptographically secure alphanumeric tokens formatted as `MS-YYYYMMDD-XXXX`.
   - Incorporates retry logic (up to 3 attempts with fresh entropy) in the rare event of a token collision before committing.
3. **Rigorous Backend Validation**:
   - **Date validation**: Disallows past dates (`appointment_date >= date.today()`).
   - **Doctor availability**: Validates `doctor.is_available` and ensures `appointment_date.strftime("%A") in doctor.available_days`.
   - **Slot boundaries**: Validates that `appointment_time` falls on predefined 30-minute boundaries (09:00 to 16:30, excluding lunch 13:00-14:00). Arbitrary irregular times (e.g. 03:17) are rejected with `400 Bad Request`.
4. **Strict Patient Data Isolation**:
   - `GET /api/v1/appointments` scopes patient queries to `patient_id == current_user.id`.
   - `GET /api/v1/appointments/{id}` rejects cross-patient snooping with **`403 Forbidden`**.
5. **Restricted Status Transitions & Transactional Cancellation**:
   - Cancellation uses a database transaction with row locking (`with_for_update()`) on the appointment row.
   - Verifies the appointment is currently `scheduled`.
   - Updates status to `cancelled`, records `cancellation_reason`, and commits.
   - Releasing the active status immediately frees the partial unique index slot for other patients.
   - Patients are forbidden from marking appointments as `completed` or `no_show` (only doctors or administrators can complete consultations).

## Tasks

<task type="auto" effort="medium">
  <name>Create schemas and doctor discovery endpoints with slot computation</name>
  <files>
    backend/app/schemas/doctor.py
    backend/app/schemas/appointment.py
    backend/app/schemas/__init__.py
    backend/app/api/v1/doctors.py
    backend/app/api/v1/__init__.py
  </files>
  <action>
    1. Create schemas in `backend/app/schemas/doctor.py` and `backend/app/schemas/appointment.py`.
       - Include `credential_status` in `DoctorResponse`.
       - Include `appointment_token`, `cancellation_reason`, and nested doctor/hospital summaries in `AppointmentResponse`.
    2. Create `backend/app/api/v1/doctors.py`:
       - `GET /api/v1/doctors`: Search by doctor name, specialty, hospital_id, city, and credential_status.
       - `GET /api/v1/doctors/{doctor_id}`: Detailed doctor profile with hospital information.
       - `GET /api/v1/doctors/{doctor_id}/slots`: Accepts `date: date`.
         - Verifies doctor is active and working on that day of the week.
         - Generates standard 30-min consultation slot boundaries (09:00 - 17:00, lunch 13:00 - 14:00).
         - Checks active appointments (`status != 'cancelled'`) on that date and marks occupied slots as `is_available: false`.
    3. Mount doctor router in `backend/app/api/v1/__init__.py`.
  </action>
  <verify>
    Verify doctor endpoints via python -c "from app.api.v1.doctors import router; print('DOCTOR_ROUTES:', [r.path for r in router.routes])"
  </verify>
  <done>
    - Doctor schemas and discovery endpoints ready
    - Dynamic slot availability calculation functional
  </done>
</task>

<task type="auto" effort="medium">
  <name>Implement transactional appointment booking, conflict handling, and cancellation</name>
  <files>
    backend/app/api/v1/appointments.py
    backend/app/api/v1/__init__.py
  </files>
  <action>
    1. Create `backend/app/api/v1/appointments.py`:
       - `POST /api/v1/appointments`:
         - Enforces authentication (`current_user: User = Depends(get_current_active_user)`).
         - Validates date is present or future (rejects past with 400 Bad Request).
         - Validates slot boundary (must be valid half-hour slot within clinic hours).
         - Validates doctor availability on selected day.
         - Collision-safe token generation (retries on token collision).
         - Sets `patient_id = current_user.id` and `status = "scheduled"`.
         - Wraps booking in transaction; catches `IntegrityError` from `uq_active_doctor_slot` partial unique index and raises `409 Conflict`.
         - Returns 201 Created with `AppointmentResponse`.
       - `GET /api/v1/appointments`:
         - Enforces role isolation: Patient sees only their own; Doctor sees their roster; Admin sees all.
       - `GET /api/v1/appointments/{appointment_id}`:
         - Enforces patient ownership: raises 403 Forbidden if not the patient, doctor, or admin.
       - `POST /api/v1/appointments/{appointment_id}/cancel`:
         - Uses `with_for_update()` row lock.
         - Verifies current status is `scheduled` (cannot re-cancel or cancel completed).
         - Verifies ownership (patient can cancel their own; doctor/admin can cancel).
         - Sets `status = "cancelled"` and records `cancellation_reason`.
         - Frees the slot in the database partial unique index.
    2. Mount appointment router in `backend/app/api/v1/__init__.py`.
  </action>
  <verify>
    Verify appointment endpoints via python -c "from app.api.v1.appointments import router; print('APPT_ROUTES:', [r.path for r in router.routes])"
  </verify>
  <done>
    - Concurrency-safe booking with partial unique index handling
    - Collision-safe token generation
    - Rigorous boundary validation
    - Transactional cancellation releasing slots
  </done>
</task>

## Must-Haves
- [ ] Database partial unique index catches concurrent double-bookings and yields 409 Conflict
- [ ] Collision-safe token generation with retry
- [ ] Boundary validation rejects past dates and non-conforming slot times
- [ ] Strict patient ownership and data isolation (403 Forbidden on cross-patient snooping)
- [ ] Transactional cancellation frees the slot immediately
- [ ] Patients prevented from modifying status to completed
