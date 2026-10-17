---
phase: 1
plan: 4
wave: 2
depends_on: [1, 2]
gap_closure: false
---

# Plan 1.4: Environment Configuration & Docker Compose for PostgreSQL

## Objective
Create the Docker Compose configuration for PostgreSQL, environment files for both backend and frontend, and verify the full backend ↔ database connection works end-to-end.

## Context
Load these files for context:
- backend/app/core/config.py
- backend/app/core/database.py
- backend/requirements.txt

## Tasks

<task type="auto" effort="medium">
  <name>Create Docker Compose for PostgreSQL and environment files</name>
  <files>
    docker-compose.yml
    backend/.env
    backend/.env.example
    .gitignore
  </files>
  <action>
    1. Create `docker-compose.yml` in project root:
       ```yaml
       services:
         db:
           image: postgres:16-alpine
           environment:
             POSTGRES_DB: medismart
             POSTGRES_USER: postgres
             POSTGRES_PASSWORD: postgres
           ports:
             - "5432:5432"
           volumes:
             - pgdata:/var/lib/postgresql/data
           healthcheck:
             test: ["CMD-SHELL", "pg_isready -U postgres"]
             interval: 5s
             timeout: 5s
             retries: 5

       volumes:
         pgdata:
       ```

    2. Create `backend/.env` (actual env file, gitignored):
       ```
       DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/medismart
       SECRET_KEY=dev-secret-change-in-production
       CORS_ORIGINS=["http://localhost:5173"]
       ```

    3. Update `backend/.env.example` (template, committed):
       ```
       DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/medismart
       SECRET_KEY=change-this-to-a-random-secret
       CORS_ORIGINS=["http://localhost:5173"]
       ```

    4. Create/update root `.gitignore`:
       ```
       # Environment
       .env
       backend/.env
       
       # Python
       __pycache__/
       *.pyc
       *.pyo
       .venv/
       venv/
       
       # Node
       node_modules/
       dist/
       
       # IDE
       .vscode/
       .idea/
       
       # OS
       .DS_Store
       Thumbs.db
       ```

    AVOID: Committing .env files with real credentials
    USE: Docker healthcheck so dependent services know when DB is ready
  </action>
  <verify>
    docker compose up -d db
    docker compose ps
  </verify>
  <done>
    - PostgreSQL container starts and passes healthcheck
    - `docker compose ps` shows db service as "healthy"
    - .env file exists but is gitignored
  </done>
</task>

<task type="auto" effort="medium">
  <name>Verify backend connects to PostgreSQL and run migrations</name>
  <files>
    backend/app/main.py
    backend/alembic/env.py
  </files>
  <action>
    1. With PostgreSQL running (docker compose up -d db), test the connection:
       ```
       cd backend
       python -c "
       import asyncio
       from app.core.database import engine
       async def test():
           async with engine.connect() as conn:
               result = await conn.execute(text('SELECT 1'))
               print('Database connected:', result.scalar())
       from sqlalchemy import text
       asyncio.run(test())
       "
       ```

    2. Run Alembic migrations to create all tables:
       ```
       cd backend
       alembic upgrade head
       ```

    3. Verify tables exist:
       ```
       docker compose exec db psql -U postgres -d medismart -c "\dt"
       ```

    4. Add a startup event to main.py that logs database connectivity (optional but helpful for debugging).

    AVOID: Running migrations against a database that hasn't started yet
    USE: Docker healthcheck or a short wait to ensure PostgreSQL is ready
  </action>
  <verify>
    docker compose exec db psql -U postgres -d medismart -c "\dt"
  </verify>
  <done>
    - Alembic migration runs without errors
    - All 5 tables appear in PostgreSQL (\dt output)
    - Backend can connect to database programmatically
  </done>
</task>

## Must-Haves
After all tasks complete, verify:
- [ ] PostgreSQL runs in Docker with persistent volume
- [ ] Backend connects to database successfully
- [ ] All 5 tables created via Alembic migration
- [ ] .env is gitignored, .env.example is committed

## Success Criteria
- [ ] All tasks verified passing
- [ ] Must-haves confirmed
- [ ] Full backend + database stack operational
