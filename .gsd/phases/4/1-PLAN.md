---
phase: 4
plan: 1
wave: 1
gap_closure: false
---

# Plan 4.1: Doctor & Appointment Schema Enhancements, Database Concurrency Constraints & Seed Data

## Objective
Enhance the `Doctor` and `Appointment` models with database-level concurrency protection against double-booking (PostgreSQL partial unique index), unique tracking tokens, credential provenance, doctor bios, and working day schedules; execute an additive Alembic migration without table drops; and create an idempotent seed script provisioning realistic doctors with clearly distinguished verified vs sample credentials.

## Context
- `backend/app/models/doctor.py`
- `backend/app/models/appointment.py`
- `backend/alembic/versions/`
- PostgreSQL 18.6 `medismart_db`

## Security & Architecture Rules
1. **Database-Enforced Concurrency Protection Against Double-Bookings**:
   - Application-level checks alone are insufficient for high-concurrency booking.
   - Enforce a **PostgreSQL Partial Unique Index** on `appointments`:
     `CREATE UNIQUE INDEX uq_active_doctor_slot ON appointments (doctor_id, appointment_date, appointment_time) WHERE status != 'cancelled';`
   - Guarantees that at the database engine level, no two active appointments can ever occupy the same doctor time slot, while allowing cancelled slots to be re-booked cleanly.
2. **Database-Enforced Token Uniqueness**:
   - `appointment_token VARCHAR(50) UNIQUE NOT NULL` with an explicit unique index in PostgreSQL.
3. **Professional Credential Provenance**:
   - Add `credential_status` (`String(50)`, default `"verified"`, server_default `"verified"`) to `doctors` to explicitly distinguish between genuinely verified specialists and demonstration/sample profiles.
4. **Doctor Profile & Scheduling Metadata**:
   - Add `bio` (`Text`, nullable=True) and `available_days` (`ARRAY(String(20))`, default `['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']`).
   - Add `cancellation_reason` (`Text`, nullable=True) to `appointments`.
5. **Zero Table Drops / Additive-Only Migration**:
   - Never drop, recreate, or truncate existing tables in `medismart_db`.

## Tasks

<task type="auto" effort="medium">
  <name>Enhance models with concurrency constraints and generate additive Alembic migration</name>
  <files>
    backend/app/models/doctor.py
    backend/app/models/appointment.py
    backend/alembic/versions/
  </files>
  <action>
    1. Update `backend/app/models/appointment.py`:
       - Add `appointment_token: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)`.
       - Add `cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)`.
       - Add SQLAlchemy `Index`:
         `Index("uq_active_doctor_slot", "doctor_id", "appointment_date", "appointment_time", unique=True, postgresql_where=text("status != 'cancelled'"))`.
    2. Update `backend/app/models/doctor.py`:
       - Add `credential_status: Mapped[str] = mapped_column(String(50), default="verified", server_default="verified", nullable=False)`.
       - Add `bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)`.
       - Add `available_days: Mapped[List[str]] = mapped_column(ARRAY(String(20)), default=list, server_default="{}", nullable=False)`.
    3. Generate and verify additive Alembic revision:
       - Run `alembic revision --autogenerate -m "doctor_appointment_concurrency_and_tokens"`.
       - Verify that generated migration contains column additions, unique constraint on token, and partial index on active slots.
    4. Apply migration: `alembic upgrade head`.
  </action>
  <verify>
    Inspect PostgreSQL indexes on `appointments` to verify `uq_active_doctor_slot` partial unique index and `appointment_token` unique index exist.
  </verify>
  <done>
    - Partial unique index active on appointments
    - Token uniqueness enforced at DB level
    - Models updated cleanly without table drops
  </done>
</task>

<task type="auto" effort="medium">
  <name>Create idempotent doctor seed script with verified credentials and sample profiles</name>
  <files>
    backend/scripts/seed_doctors.py
  </files>
  <action>
    1. Create `backend/scripts/seed_doctors.py`:
       - Creates User accounts with `role="doctor"` and Argon2id hashed passwords.
       - Links doctors to the 7 seeded metropolitan hospitals.
       - Populates specialties, qualifications, experience, fees, bios, and available working days.
       - Explicitly flags verified specialists with `credential_status="verified"` and demonstration profiles with `credential_status="sample"`.
       - Ensures idempotency: checks for existing user email and doctor record before creation.
    2. Execute `seed_doctors.py`.
  </action>
  <verify>
    Run seed script twice to assert 0 duplicates on second execution.
  </verify>
  <done>
    - Doctors seeded across all metropolitan hospitals
    - Verified credentials vs sample profiles clearly distinguished
    - Idempotent execution confirmed
  </done>
</task>

## Must-Haves
- [ ] Partial unique index on active doctor slots enforced in PostgreSQL
- [ ] Unique constraint on `appointment_token` in PostgreSQL
- [ ] `credential_status` column present on doctors table
- [ ] Additive migration preserves all existing data
