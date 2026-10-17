---
phase: 1
plan: 4
wave: 2
depends_on: [1, 2]
gap_closure: false
---

# Plan 1.4: Environment Configuration, .gitignore & Database Verification

## Objective
Set up the project-wide environment configuration, ensure .env is gitignored, and verify end-to-end connectivity between the FastAPI backend and the existing local PostgreSQL medismart_db. No Docker Compose — PostgreSQL is already running locally.

## Context
Load these files for context:
- backend/app/core/config.py (created in Plan 1.1)
- backend/app/core/database.py (created in Plan 1.2)
- backend/.env (created in Plan 1.1)

## Tasks

<task type="auto" effort="medium">
  <name>Create project .gitignore and verify environment configuration</name>
  <files>
    .gitignore
    backend/.env
    backend/.env.example
  </files>
  <action>
    1. Create/update root `.gitignore` (additive — do NOT remove existing entries
       if a .gitignore already exists):
       ```
       # Environment files
       .env
       backend/.env

       # Python
       __pycache__/
       *.pyc
       *.pyo
       .venv/
       venv/
       *.egg-info/

       # Node
       node_modules/
       dist/

       # IDE
       .vscode/
       .idea/
       *.swp
       *.swo

       # OS
       .DS_Store
       Thumbs.db

       # Test
       .coverage
       htmlcov/
       .pytest_cache/
       ```

    2. Verify backend/.env exists with correct medismart_db connection:
       DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/medismart_db
       If the user hasn't set their password, prompt them to update .env.

    3. Verify backend/.env.example is correct and ready to commit.

    4. Verify frontend/.gitignore exists (created by Vite scaffold).

    AVOID: Committing .env files with any credentials
    AVOID: Overwriting existing .gitignore entries
    USE: Separate .gitignore entries for Python and Node artifacts
  </action>
  <verify>
    git status --short backend/.env
  </verify>
  <done>
    - .gitignore includes .env, __pycache__, node_modules, .venv
    - backend/.env is NOT tracked by git (shows ?? or is absent from git status)
    - backend/.env.example contains template values
  </done>
</task>

<task type="auto" effort="medium">
  <name>Verify full backend ↔ database connectivity and run migrations</name>
  <files>
    backend/app/core/database.py
    backend/alembic/env.py
  </files>
  <action>
    1. Verify PostgreSQL is running locally:
       ```
       psql -U postgres -d medismart_db -c "SELECT version();"
       ```
       If this fails, prompt the user to start their PostgreSQL service.

    2. Test async database connection from Python:
       ```python
       cd backend
       python -c "
       import asyncio
       from sqlalchemy import text
       from app.core.database import engine
       async def test():
           async with engine.connect() as conn:
               result = await conn.execute(text('SELECT 1'))
               print('Database connected:', result.scalar())
       asyncio.run(test())
       "
       ```

    3. Check if Alembic migration has been applied:
       ```
       cd backend
       alembic current
       ```

    4. If migration NOT yet applied, run:
       ```
       alembic upgrade head
       ```

    5. Verify tables exist in medismart_db:
       ```
       psql -U postgres -d medismart_db -c "\dt"
       ```
       Expected: users, hospitals, doctors, appointments, queue_entries (+ alembic_version)

    AVOID: Running alembic upgrade if tables already exist and aren't stamped
           (check first, then stamp or upgrade appropriately)
    AVOID: Any DROP TABLE, DROP DATABASE, or destructive operation
    USE: alembic stamp head if tables were created outside of Alembic
  </action>
  <verify>
    cd backend
    python -c "import asyncio; from sqlalchemy import text; from app.core.database import engine; asyncio.run((lambda: None)()  or print('OK'))"
    alembic current
  </verify>
  <done>
    - Backend connects to medismart_db via asyncpg
    - All 5 tables exist in medismart_db
    - Alembic version table tracks migration state
    - No data was lost or tables dropped
  </done>
</task>

## Must-Haves
After all tasks complete, verify:
- [ ] .env is gitignored (not tracked)
- [ ] Backend connects to local PostgreSQL medismart_db
- [ ] All 5 tables created/verified in medismart_db
- [ ] Alembic tracks migration state
- [ ] No Docker dependency required

## Success Criteria
- [ ] All tasks verified passing
- [ ] Must-haves confirmed
- [ ] Full backend + database stack operational using local PostgreSQL
