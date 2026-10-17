---
phase: 1
plan: 1
wave: 1
gap_closure: false
---

# Plan 1.1: Backend Foundation (FastAPI + Project Structure)

## Objective
Create the FastAPI backend project with proper structure, configuration, CORS middleware, and a health-check endpoint. This is the foundation every subsequent backend feature builds on.

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
    backend/.env.example
  </files>
  <action>
    Create the FastAPI backend with this directory structure:

    ```
    backend/
    ├── requirements.txt
    ├── .env.example
    ├── app/
    │   ├── __init__.py
    │   ├── main.py              # FastAPI app factory, CORS, router mounting
    │   ├── core/
    │   │   ├── __init__.py
    │   │   └── config.py        # Pydantic Settings (env vars: DATABASE_URL, SECRET_KEY, etc.)
    │   ├── api/
    │   │   ├── __init__.py
    │   │   └── v1/
    │   │       ├── __init__.py
    │   │       └── health.py    # GET /api/v1/health → {"status": "ok", "version": "0.1.0"}
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

    config.py: Use pydantic_settings.BaseSettings with fields:
    - DATABASE_URL (default: postgresql+asyncpg://postgres:postgres@localhost:5432/medismart)
    - SECRET_KEY (default: dev-secret-change-in-production)
    - CORS_ORIGINS (default: ["http://localhost:5173"])
    - API_V1_PREFIX (default: /api/v1)

    main.py: Create FastAPI app with:
    - title="MediSmart API"
    - CORS middleware allowing CORS_ORIGINS
    - Include v1 router at API_V1_PREFIX
    - Root endpoint returning {"message": "MediSmart API", "docs": "/docs"}

    AVOID: Using synchronous database drivers — we use asyncpg for async PostgreSQL
    USE: pydantic-settings (not raw os.environ) for type-safe configuration
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
  </done>
</task>

<task type="auto" effort="low">
  <name>Verify backend runs and health endpoint responds</name>
  <files>
    backend/app/main.py
    backend/app/api/v1/health.py
  </files>
  <action>
    Start the uvicorn server and verify:
    1. Run: uvicorn app.main:app --host 0.0.0.0 --port 8000
    2. Verify GET http://localhost:8000/ returns {"message": "MediSmart API", "docs": "/docs"}
    3. Verify GET http://localhost:8000/api/v1/health returns {"status": "ok", "version": "0.1.0"}
    4. Verify GET http://localhost:8000/docs returns Swagger UI (200 status)

    AVOID: Leaving uvicorn running after verification — stop it cleanly
  </action>
  <verify>
    curl http://localhost:8000/api/v1/health
  </verify>
  <done>
    - Health endpoint returns {"status": "ok", "version": "0.1.0"} with 200 status
    - Root endpoint returns API info
    - Swagger docs accessible at /docs
  </done>
</task>

## Must-Haves
After all tasks complete, verify:
- [ ] FastAPI app starts without errors
- [ ] Health endpoint responds with JSON
- [ ] Project structure follows modular pattern
- [ ] CORS is configured for frontend origin (localhost:5173)

## Success Criteria
- [ ] All tasks verified passing
- [ ] Must-haves confirmed
- [ ] Backend starts and serves requests
