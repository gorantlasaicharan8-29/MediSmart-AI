# STATE.md — Project Memory

> Last updated: 2026-10-17 19:54 IST

## Current Position

- **Phase**: 1 — Project Foundation & Architecture
- **Task**: Plan 1.2 — PostgreSQL Database Schema & Connection (Models created & tested; awaiting local DB password for migration execution)
- **Status**: Saved & Paused at 2026-10-17 19:54 IST
- **Completed Plans**: Plan 1.1 (Backend Foundation)
- **In-Progress Plans**: Plan 1.2 (Models, engine, session, Alembic configured; DB auth pending)

## Last Session Summary

- **Project Planning & Realignment**:
  - Realigned all Phase 1 plans with user requirements (reusing local PostgreSQL 18.6 `medismart_db`, eliminating Docker Compose requirement, preserving existing React 19 + Vite 8 frontend, using `String(20)` instead of Enum for roles/statuses to ensure additive migrations).
  - Created root `.gitignore` protecting `.env` and Python/Node artifacts.
- **Plan 1.1 Completed & Verified**:
  - Scaffolded FastAPI app structure (`backend/app/main.py`, `backend/app/core/config.py`, `backend/app/api/v1/health.py`).
  - Added `/api/v1/health` and `/api/v1/health/db` endpoints.
  - Initialized Python 3.13 `.venv` and installed all dependencies (`fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `greenlet`, `asyncpg`, `psycopg2-binary`, `alembic`, `pydantic-settings`, `pytest`).
  - Verified endpoints live via uvicorn (Root 200, Docs 200, Health 200).
  - Documented in `backend/.gsd/phases/1/1-SUMMARY.md` and committed in git (`ef587c6`, `ac2642f`).
- **Plan 1.2 Implemented & Committed**:
  - Created `backend/app/core/database.py` with async engine and `get_db()` session generator.
  - Created `backend/app/models/base.py` with `UUIDMixin` and `TimestampMixin`.
  - Implemented all 5 core models: `User`, `Hospital`, `Doctor`, `Appointment`, `QueueEntry` with proper UUID PKs, relationships, cascading constraints, and native PostgreSQL types.
  - Verified model imports and table resolution.
  - Initialized and configured Alembic (`backend/alembic.ini`, `backend/alembic/env.py`) using dynamic connection from `DATABASE_URL` with sync `psycopg2` driver and `Base.metadata`.
  - Tested database connection against local PostgreSQL 18.6: service is running on 5432, failed authentication with placeholder password `postgres`.
  - Adhered to safety requirement: stopped at auth check without guessing passwords or modifying existing data.
  - Committed code in git (`90a9999`).

## In-Progress Work

- **Files created/modified**:
  - `backend/app/core/database.py`
  - `backend/app/models/base.py`
  - `backend/app/models/user.py`
  - `backend/app/models/hospital.py`
  - `backend/app/models/doctor.py`
  - `backend/app/models/appointment.py`
  - `backend/app/models/queue.py`
  - `backend/app/models/__init__.py`
  - `backend/alembic.ini`
  - `backend/alembic/env.py`
- **Tests status**:
  - Model definitions & imports: PASS
  - App & health endpoints: PASS
  - Database connectivity test: Awaiting actual password in `backend/.env`

## Blockers

- PostgreSQL `medismart_db` connection requires the user's local password for user `postgres` in `backend/.env`.

## Context Dump

### Decisions Made
- Decision 9: Use existing local PostgreSQL 18.6 with `medismart_db` instead of Docker Compose.
- Decision 10: Additive-only migrations with String types instead of Enum for roles and statuses.
- Decision 11: Preserve existing Vite 8 + React 19 frontend setup and add Tailwind CSS v4 via `@tailwindcss/vite`.
- Decision 12: Stop execution before applying migrations if DB credentials fail; never guess passwords.

### Files of Interest
- `backend/.env`: Local credentials file (gitignored). Needs user's actual password in `DATABASE_URL`.
- `backend/app/core/database.py`: Async engine and session factory.
- `backend/app/models/`: Contains all 5 core entity models.
- `backend/alembic/env.py`: Alembic configuration reading `settings.DATABASE_URL`.
- `.gsd/phases/1/2-PLAN.md`: Full Plan 1.2 tasks.
- `.gsd/phases/1/3-PLAN.md`: Plan 1.3 (Frontend Tailwind v4 & Layout Shell).

## Next Steps
1. User updates `DATABASE_URL` in `backend/.env` with their actual PostgreSQL password.
2. Run database inspection on `medismart_db` to verify existing tables.
3. Generate initial Alembic revision (`alembic revision --autogenerate -m "create initial tables"`).
4. Review generated migration (confirm only CREATE, no DROP).
5. Apply migration (`alembic upgrade head`).
6. Verify tables in `medismart_db` and write `2-SUMMARY.md`.
7. Proceed to Plan 1.3 (Frontend Tailwind v4 and React Router setup).
