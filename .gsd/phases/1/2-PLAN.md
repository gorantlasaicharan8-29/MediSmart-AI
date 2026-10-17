---
phase: 1
plan: 2
wave: 1
gap_closure: false
---

# Plan 1.2: PostgreSQL Database Schema & Connection (Using Existing Local DB)

## Objective
Set up SQLAlchemy 2.x async engine and session against the existing local PostgreSQL 18.6 database (medismart_db), then create the initial schema with Alembic migrations for the 5 core tables. Migrations must be additive — never drop, reset, or recreate the database.

## Context
Load these files for context:
- .gsd/SPEC.md (Users section, Technology Stack)
- backend/app/core/config.py (after Plan 1.1 creates it)

## Tasks

<task type="auto" effort="high">
  <name>Create SQLAlchemy async database engine, session, and all 5 models</name>
  <files>
    backend/app/core/database.py
    backend/app/models/base.py
    backend/app/models/user.py
    backend/app/models/hospital.py
    backend/app/models/doctor.py
    backend/app/models/appointment.py
    backend/app/models/queue.py
    backend/app/models/__init__.py
  </files>
  <action>
    1. Create `backend/app/core/database.py`:
       - AsyncEngine from create_async_engine(settings.DATABASE_URL)
       - async_sessionmaker with expire_on_commit=False
       - get_db() async generator yielding AsyncSession (for FastAPI dependency injection)

    2. Create `backend/app/models/base.py`:
       - DeclarativeBase subclass
       - Common mixin or base with id (UUID PK), created_at, updated_at

    3. Create SQLAlchemy models:

       **User** (models/user.py):
       - id: UUID (PK, default uuid4)
       - email: String(255), unique, indexed, not null
       - hashed_password: String(255), not null
       - full_name: String(255), not null
       - phone: String(20), nullable
       - role: String(20), not null (values: "patient", "doctor", "hospital_admin", "system_admin")
         Use String instead of PostgreSQL Enum to avoid migration issues when adding roles later
       - is_active: Boolean, default True
       - created_at: DateTime(timezone=True), server_default=func.now()
       - updated_at: DateTime(timezone=True), server_default=func.now(), onupdate=func.now()

       **Hospital** (models/hospital.py):
       - id: UUID (PK)
       - name: String(255), not null
       - address: Text, not null
       - city: String(100), indexed, not null
       - state: String(100), not null
       - latitude: Float, not null
       - longitude: Float, not null
       - phone: String(20), nullable
       - email: String(255), nullable
       - specialties: ARRAY(String) (PostgreSQL native array)
       - facilities: ARRAY(String)
       - is_active: Boolean, default True
       - created_at, updated_at (same pattern as User)

       **Doctor** (models/doctor.py):
       - id: UUID (PK)
       - user_id: UUID (FK → users.id), not null
       - hospital_id: UUID (FK → hospitals.id), not null
       - specialty: String(100), indexed, not null
       - qualification: String(255), nullable
       - experience_years: Integer, default 0
       - consultation_fee: Float, nullable
       - is_available: Boolean, default True
       - created_at, updated_at

       **Appointment** (models/appointment.py):
       - id: UUID (PK)
       - patient_id: UUID (FK → users.id), not null
       - doctor_id: UUID (FK → doctors.id), not null
       - hospital_id: UUID (FK → hospitals.id), not null
       - appointment_date: Date, not null
       - appointment_time: Time, not null
       - status: String(20), default "scheduled"
         (values: "scheduled", "checked_in", "in_progress", "completed", "cancelled", "no_show")
       - notes: Text, nullable
       - created_at, updated_at

       **QueueEntry** (models/queue.py):
       - id: UUID (PK)
       - appointment_id: UUID (FK → appointments.id, unique), not null
       - hospital_id: UUID (FK → hospitals.id), not null
       - doctor_id: UUID (FK → doctors.id), not null
       - patient_id: UUID (FK → users.id), not null
       - token_number: Integer, not null
       - position: Integer, not null
       - status: String(20), default "waiting"
         (values: "waiting", "in_progress", "completed", "skipped")
       - estimated_wait_minutes: Integer, nullable
       - checked_in_at: DateTime(timezone=True), not null
       - called_at: DateTime(timezone=True), nullable
       - completed_at: DateTime(timezone=True), nullable

    4. Update `models/__init__.py` to import all models so Alembic autogenerate detects them.

    SCHEMA CORRECTIONS from original plan:
    - Use String(20) instead of PostgreSQL Enum type for role/status columns.
      Reason: Enum types require explicit ALTER TYPE migrations when adding values,
      which breaks additive-only migration strategy. String columns are more flexible.
    - Ensure all FKs have explicit ondelete behavior (SET NULL or CASCADE as appropriate).
    - Add index on appointment_date for query performance.

    AVOID: Using PostgreSQL Enum columns — use String with application-level validation
    AVOID: Any DROP TABLE or destructive operations
    USE: UUID primary keys (not auto-increment integers) for all tables
    USE: server_default=func.now() for timestamps (not Python-side defaults)
    USE: The existing local medismart_db — do NOT create a new database
  </action>
  <verify>
    cd backend
    python -c "from app.models import User, Hospital, Doctor, Appointment, QueueEntry; print('All models imported successfully')"
  </verify>
  <done>
    - All 5 models import without errors
    - Models have proper relationships and foreign keys
    - Database engine/session utilities are importable
    - No PostgreSQL Enum types used (String columns instead)
  </done>
</task>

<task type="auto" effort="medium">
  <name>Initialize Alembic and create initial migration (additive only)</name>
  <files>
    backend/alembic.ini
    backend/alembic/env.py
    backend/alembic/script.py.mako
    backend/alembic/versions/
  </files>
  <action>
    1. Run: cd backend && alembic init alembic
    2. Edit alembic.ini:
       - Set sqlalchemy.url to empty string (overridden in env.py)
    3. Edit alembic/env.py:
       - Import settings from app.core.config
       - Import Base from app.models.base
       - Import all models from app.models (so autogenerate detects them)
       - Override sqlalchemy.url using settings.DATABASE_URL:
         For Alembic (sync): replace "+asyncpg" with "+psycopg2" or use plain "postgresql://"
         config.set_main_option("sqlalchemy.url",
             settings.DATABASE_URL.replace("+asyncpg", ""))
       - Set target_metadata = Base.metadata
    4. Add psycopg2-binary to requirements.txt (Alembic needs a sync driver)
    5. Create initial migration:
       alembic revision --autogenerate -m "create initial tables"
    6. Review the generated migration to confirm it only contains CREATE TABLE operations
       and does NOT contain any DROP statements.
    7. Run the migration: alembic upgrade head

    CRITICAL: Before running autogenerate, check if tables already exist in medismart_db.
    If they do, use alembic stamp head instead of upgrade to mark current state
    without running migration SQL.

    AVOID: DROP TABLE, DROP COLUMN, or any destructive migration operations
    AVOID: Hardcoding database credentials in alembic.ini
    AVOID: Using asyncpg driver with Alembic (it requires a sync driver)
    USE: alembic stamp head if tables already exist (don't recreate)
    USE: Environment variable override in env.py
  </action>
  <verify>
    cd backend
    alembic heads
    alembic current
  </verify>
  <done>
    - Alembic initialized with env.py pointing to medismart_db
    - Initial migration exists with all 5 tables (CREATE only, no DROP)
    - `alembic heads` shows the migration revision
    - `alembic current` shows migration is applied
    - Existing data in medismart_db is preserved
  </done>
</task>

## Must-Haves
After all tasks complete, verify:
- [ ] 5 SQLAlchemy models defined with proper relationships
- [ ] Async database session utility works against local medismart_db
- [ ] Alembic configured — no destructive operations
- [ ] All models use UUID primary keys and String (not Enum) for status columns
- [ ] Existing medismart_db data is untouched

## Success Criteria
- [ ] All tasks verified passing
- [ ] Must-haves confirmed
- [ ] Models and database utilities importable without errors
- [ ] Tables exist in medismart_db
