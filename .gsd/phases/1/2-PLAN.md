---
phase: 1
plan: 2
wave: 1
gap_closure: false
---

# Plan 1.2: PostgreSQL Database Schema & Connection

## Objective
Set up PostgreSQL database connection using SQLAlchemy async engine and create the initial schema with Alembic migrations for the core tables: users, hospitals, doctors, appointments, and queues.

## Context
Load these files for context:
- .gsd/SPEC.md (Users section, Technology Stack)
- backend/app/core/config.py

## Tasks

<task type="auto" effort="high">
  <name>Create SQLAlchemy async database engine and session</name>
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
       - get_db() async generator yielding AsyncSession (dependency injection)

    2. Create `backend/app/models/base.py`:
       - DeclarativeBase subclass with common fields (id: UUID PK, created_at, updated_at)

    3. Create SQLAlchemy models:

       **User** (models/user.py):
       - id: UUID (PK, default uuid4)
       - email: String(255), unique, indexed
       - hashed_password: String(255)
       - full_name: String(255)
       - phone: String(20), nullable
       - role: Enum("patient", "doctor", "hospital_admin", "system_admin")
       - is_active: Boolean, default True
       - created_at, updated_at: DateTime with timezone

       **Hospital** (models/hospital.py):
       - id: UUID (PK)
       - name: String(255)
       - address: Text
       - city: String(100), indexed
       - state: String(100)
       - latitude: Float
       - longitude: Float
       - phone: String(20)
       - email: String(255)
       - specialties: ARRAY(String) (PostgreSQL array)
       - facilities: ARRAY(String)
       - is_active: Boolean, default True
       - created_at, updated_at

       **Doctor** (models/doctor.py):
       - id: UUID (PK)
       - user_id: UUID (FK → users.id)
       - hospital_id: UUID (FK → hospitals.id)
       - specialty: String(100), indexed
       - qualification: String(255)
       - experience_years: Integer
       - consultation_fee: Float
       - is_available: Boolean, default True
       - created_at, updated_at

       **Appointment** (models/appointment.py):
       - id: UUID (PK)
       - patient_id: UUID (FK → users.id)
       - doctor_id: UUID (FK → doctors.id)
       - hospital_id: UUID (FK → hospitals.id)
       - appointment_date: Date
       - appointment_time: Time
       - status: Enum("scheduled", "checked_in", "in_progress", "completed", "cancelled", "no_show")
       - notes: Text, nullable
       - created_at, updated_at

       **QueueEntry** (models/queue.py):
       - id: UUID (PK)
       - appointment_id: UUID (FK → appointments.id, unique)
       - hospital_id: UUID (FK → hospitals.id)
       - doctor_id: UUID (FK → doctors.id)
       - patient_id: UUID (FK → users.id)
       - token_number: Integer
       - position: Integer
       - status: Enum("waiting", "in_progress", "completed", "skipped")
       - estimated_wait_minutes: Integer, nullable
       - checked_in_at: DateTime
       - called_at: DateTime, nullable
       - completed_at: DateTime, nullable

    4. Update `models/__init__.py` to import all models.

    AVOID: Using synchronous SQLAlchemy — all database operations must be async
    AVOID: String-based column types without length limits
    USE: UUID primary keys (not auto-increment integers) for all tables
    USE: server_default for timestamps, not Python-side defaults
  </action>
  <verify>
    cd backend
    python -c "from app.models import User, Hospital, Doctor, Appointment, QueueEntry; print('All models imported successfully')"
  </verify>
  <done>
    - All 5 models import without errors
    - Models have proper relationships and foreign keys
    - Database engine/session utilities are importable
  </done>
</task>

<task type="auto" effort="medium">
  <name>Initialize Alembic and create initial migration</name>
  <files>
    backend/alembic.ini
    backend/alembic/env.py
    backend/alembic/versions/
  </files>
  <action>
    1. Run: cd backend && alembic init alembic
    2. Edit alembic.ini: set sqlalchemy.url to empty (will be overridden in env.py)
    3. Edit alembic/env.py:
       - Import settings from app.core.config
       - Import Base from app.models.base
       - Import all models from app.models (so autogenerate detects them)
       - Set config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("+asyncpg", ""))
       - Set target_metadata = Base.metadata
    4. Create initial migration: alembic revision --autogenerate -m "initial schema"

    NOTE: Migration generation requires PostgreSQL to be running.
    If PostgreSQL is not available, create the migration file manually with the correct schema.

    AVOID: Committing alembic.ini with hardcoded database credentials
    USE: Environment variable override in env.py
  </action>
  <verify>
    cd backend
    alembic heads
  </verify>
  <done>
    - Alembic initialized with env.py pointing to correct database
    - Initial migration exists with all 5 tables
    - `alembic heads` shows the migration revision
  </done>
</task>

## Must-Haves
After all tasks complete, verify:
- [ ] 5 SQLAlchemy models defined with proper relationships
- [ ] Async database session utility works
- [ ] Alembic configured for migration management
- [ ] All models use UUID primary keys

## Success Criteria
- [ ] All tasks verified passing
- [ ] Must-haves confirmed
- [ ] Models and database utilities importable without errors
