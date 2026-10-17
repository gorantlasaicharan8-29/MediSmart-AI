---
phase: 1
plan: 1
wave: 1
gap_closure: false
---

# Plan 1.1: Backend Foundation (FastAPI + Project Structure)

## Objective
Create the FastAPI backend project with proper structure, configuration, CORS middleware, health-check endpoint, and database connectivity check. This is the foundation every subsequent backend feature builds on.

## Context
Load these files for context:
- .gsd/SPEC.md
- .gsd/ROADMAP.md (Phase 1 section)

## Tasks

<task type="auto" effort="medium">
  <name>Scaffold FastAPI backend project</name>
  <files>
    backend/requirements.txt
    backend/app/__init__.py
    backend/app/main.py
    backend/app/core/__init__.py
    backend/app/core/config.py
    backend/app/api/__init__.py
    backend/app/api/v1/__init__.py
    backend/app/api/v1/health.py
    backend/app/models/__init__.py
    backend/app/schemas/__init__.py
    backend/app/services/__init__.py
    backend/.env
    backend/.env.example
  </files>
  <action>
    Create the FastAPI backend with this directory structure:

    ```
    backend/
    ├── requirements.txt
    ├── .env               (gitignored — actual credentials)
    ├── .env.example        (committed — template)
    ├── app/
    │   ├── __init__.py
    │   ├── main.py              # FastAPI app factory, CORS, router mounting
    │   ├── core/
    │   │   ├── __init__.py
    │   │   └── config.py        # Pydantic Settings
    │   ├── api/
    │   │   ├── __init__.py
    │   │   └── v1/
    │   │       ├── __init__.py
    │   │       └── health.py    # Health + DB connectivity endpoints
    │   ├── models/
    │   │   └── __init__.py
    │   ├── schemas/
    │   │   └── __init__.py
    │   └── services/
    │       └── __init__.py
    ```

    requirements.txt dependencies:
    - fastapi>=0.115.0
    - uvicorn[standard]>=0.30.0
    - sqlalchemy>=2.0
    - asyncpg>=0.29.0
    - alembic>=1.13
    - pydantic-settings>=2.0
    - python-jose[cryptography]>=3.3
    - passlib[bcrypt]>=1.7
    - python-multipart>=0.0.7
    - python-dotenv>=1.0
    - httpx>=0.27.0
    - pytest>=8.0
    - pytest-asyncio>=0.23

    config.py: Use pydantic_settings.BaseSettings with fields:
    - DATABASE_URL (default: postgresql+asyncpg://postgres:postgres@localhost:5432/medismart_db)
    - SECRET_KEY (default: dev-secret-change-in-production)
    - CORS_ORIGINS (default: ["http://localhost:5173"])
    - API_V1_PREFIX (default: /api/v1)
    - Load from backend/.env file via model_config = SettingsConfigDict(env_file=".env")

    .env file (gitignored):
    ```
    DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/medismart_db
    SECRET_KEY=dev-secret-change-in-production
    CORS_ORIGINS=["http://localhost:5173"]
    ```

    .env.example file (committed):
    ```
    DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/medismart_db
    SECRET_KEY=change-this-to-a-random-secret
    CORS_ORIGINS=["http://localhost:5173"]
    ```

    main.py: Create FastAPI app with:
    - title="MediSmart API"
    - CORS middleware allowing CORS_ORIGINS
    - Include v1 router at API_V1_PREFIX
    - Root endpoint returning {"message": "MediSmart API", "docs": "/docs"}

    health.py: Two endpoints:
    - GET /api/v1/health → {"status": "ok", "version": "0.1.0"}
    - GET /api/v1/health/db → Runs "SELECT 1" against the database
      Returns {"status": "ok", "database": "connected"} on success
      Returns {"status": "error", "database": "disconnected", "detail": "..."} on failure

    AVOID: Using synchronous database drivers — we use asyncpg for async PostgreSQL
    AVOID: Hardcoding credentials in source files — all config via .env
    USE: pydantic-settings (not raw os.environ) for type-safe configuration
    USE: The existing local PostgreSQL 18.6 with database medismart_db
  </action>
  <verify>
    cd backend
    pip install -r requirements.txt
    python -c "from app.main import app; print(app.title)"
  </verify>
  <done>
    - FastAPI app object is importable and prints "MediSmart API"
    - All __init__.py files exist, no import errors
    - requirements.txt installs without errors
    - .env file exists with medismart_db connection string
    - .env.example committed as template
  </done>
</task>

<task type="auto" effort="low">
  <name>Verify backend runs and health endpoints respond</name>
  <files>
    backend/app/main.py
    backend/app/api/v1/health.py
  </files>
  <action>
    Start the uvicorn server and verify:
    1. Run: cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
    2. Verify GET http://localhost:8000/ returns {"message": "MediSmart API", "docs": "/docs"}
    3. Verify GET http://localhost:8000/api/v1/health returns {"status": "ok", "version": "0.1.0"}
    4. Verify GET http://localhost:8000/api/v1/health/db returns {"status": "ok", "database": "connected"}
       (this proves the FastAPI ↔ medismart_db connection works)
    5. Verify GET http://localhost:8000/docs returns Swagger UI (200 status)

    AVOID: Leaving uvicorn running after verification — stop it cleanly
  </action>
  <verify>
    curl http://localhost:8000/api/v1/health
    curl http://localhost:8000/api/v1/health/db
  </verify>
  <done>
    - Health endpoint returns {"status": "ok", "version": "0.1.0"} with 200
    - DB health returns {"status": "ok", "database": "connected"} with 200
    - Root endpoint returns API info
    - Swagger docs accessible at /docs
  </done>
</task>

## Must-Haves
After all tasks complete, verify:
- [ ] FastAPI app starts without errors
- [ ] Health endpoint responds with JSON
- [ ] DB connectivity check confirms connection to medismart_db
- [ ] Project structure follows modular pattern
- [ ] CORS is configured for frontend origin (localhost:5173)
- [ ] .env is gitignored, .env.example is committed

## Success Criteria
- [ ] All tasks verified passing
- [ ] Must-haves confirmed
- [ ] Backend starts and serves requests against local PostgreSQL
