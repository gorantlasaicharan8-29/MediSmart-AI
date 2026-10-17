# JOURNAL.md — Development Journal

> Chronological log of development activity.

---

## 2026-10-17

### Session 1: Project Initialization & Planning
- Ran `/new-project` workflow.
- Analyzed existing codebase (Vite React boilerplate in `frontend/`).
- Created SPEC.md with 8 goals, 4 user roles, full tech stack.
- Created ROADMAP.md with 9 phases from foundation to polish.
- Initialized git repository.
- Realigned Phase 1 plans with 10 user requirements (local PostgreSQL 18.6 `medismart_db`, no Docker Compose, preserve React 19 + Vite 8 frontend, additive migrations, String roles/statuses).

### Session 2: Phase 1 Execution (Plan 1.1 & Plan 1.2)
- **Plan 1.1 Complete**:
  - Scaffolded FastAPI modular backend (`app/main.py`, `app/core/config.py`, `app/api/v1/health.py`).
  - Added root `.gitignore` protecting credentials and build directories.
  - Initialized Python 3.13 `.venv` and installed all requirements (`fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `greenlet`, `asyncpg`, `psycopg2-binary`, `alembic`, `pydantic-settings`).
  - Verified live endpoints: `GET /` (200), `GET /docs` (200), `GET /api/v1/health` (200), `GET /api/v1/health/db` (handled gracefully).
  - Created `1-SUMMARY.md` and committed in git (`ef587c6`, `ac2642f`).
- **Plan 1.2 Implementation**:
  - Created `app/core/database.py` with async SQLAlchemy engine and session generator.
  - Created base declarative models and mixins (`app/models/base.py`).
  - Implemented 5 entity models: `User`, `Hospital`, `Doctor`, `Appointment`, and `QueueEntry` with UUID PKs, relationships, and PostgreSQL native types.
  - Initialized Alembic and configured `alembic.ini` and `alembic/env.py` to dynamically load `DATABASE_URL` via sync driver.
  - Tested database connection: verified local PostgreSQL 18.6 is running; halted before applying migrations due to placeholder password in `.env`, strictly preserving database data.
  - Committed code changes in git (`90a9999`).

### Handoff Notes
- To resume: update PostgreSQL password in `backend/.env`, run connection test, autogenerate Alembic migration, and apply `alembic upgrade head`.
