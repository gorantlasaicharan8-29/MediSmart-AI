---
phase: 1
plan: 5
wave: 2
depends_on: [1, 3, 4]
gap_closure: false
---

# Plan 1.5: Basic Tests & Developer Documentation

## Objective
Add basic pytest tests for the backend (health endpoints, DB connectivity, model imports) and create developer documentation with setup and run instructions for both frontend and backend.

## Context
Load these files for context:
- backend/app/main.py
- backend/app/api/v1/health.py
- backend/app/models/__init__.py
- frontend/package.json

## Tasks

<task type="auto" effort="medium">
  <name>Create basic backend tests with pytest</name>
  <files>
    backend/tests/__init__.py
    backend/tests/conftest.py
    backend/tests/test_health.py
    backend/tests/test_models.py
    backend/pytest.ini
  </files>
  <action>
    1. Create `backend/pytest.ini`:
       ```ini
       [pytest]
       asyncio_mode = auto
       testpaths = tests
       ```

    2. Create `backend/tests/__init__.py` (empty)

    3. Create `backend/tests/conftest.py`:
       - Import pytest and httpx
       - Create an async test client fixture using httpx.AsyncClient with FastAPI's app
       ```python
       import pytest
       from httpx import AsyncClient, ASGITransport
       from app.main import app

       @pytest.fixture
       async def client():
           transport = ASGITransport(app=app)
           async with AsyncClient(transport=transport, base_url="http://test") as ac:
               yield ac
       ```

    4. Create `backend/tests/test_health.py`:
       - test_root_endpoint: GET / returns 200 and contains "MediSmart API"
       - test_health_endpoint: GET /api/v1/health returns 200 and {"status": "ok"}
       - test_health_db_endpoint: GET /api/v1/health/db returns 200 (requires DB running)
       - test_docs_endpoint: GET /docs returns 200

    5. Create `backend/tests/test_models.py`:
       - test_import_all_models: Import User, Hospital, Doctor, Appointment, QueueEntry — assert no errors
       - test_user_model_has_required_columns: Check User.__table__.columns contains id, email, role, etc.
       - test_hospital_model_has_required_columns: Check Hospital.__table__.columns contains latitude, longitude, specialties, etc.
       - test_all_models_use_uuid_pk: Verify all 5 models have a UUID primary key column

    AVOID: Tests that mock everything — use real app instance with httpx.AsyncClient
    AVOID: Tautological assertions like `assert True` or `assert response is not None`
    AVOID: Testing framework behavior — test OUR code
    USE: httpx.AsyncClient with ASGITransport for testing FastAPI
    USE: pytest-asyncio for async test support
    USE: Specific assertions (status codes, JSON keys, column names)
  </action>
  <verify>
    cd backend
    python -m pytest tests/ -v
  </verify>
  <done>
    - All tests pass with `pytest tests/ -v`
    - At least 6 test functions defined
    - Tests verify real behavior (not mocks)
    - Health endpoint tests confirm actual JSON responses
    - Model tests confirm actual table structure
  </done>
</task>

<task type="auto" effort="low">
  <name>Create developer documentation (setup + run instructions)</name>
  <files>
    README.md
  </files>
  <action>
    Create `README.md` in project root with:

    ```markdown
    # MediSmart

    Smart Hospital Discovery, Doctor Appointment & Real-Time Queue Management System.

    > ⚠️ This project uses **synthetic data only**. No real hospital partnerships exist.

    ## Tech Stack

    | Layer     | Technology                        |
    |-----------|-----------------------------------|
    | Frontend  | React 19, Vite 8, Tailwind CSS v4 |
    | Backend   | Python, FastAPI                   |
    | Database  | PostgreSQL 18.6 (local)           |
    | Maps      | OpenStreetMap + Leaflet (Phase 3) |
    | Real-time | WebSockets (Phase 5)              |
    | ML        | scikit-learn, XGBoost (Phase 6)   |

    ## Prerequisites

    - Node.js 18+ and npm
    - Python 3.11+
    - PostgreSQL 18.6 (installed locally)
    - Database `medismart_db` created

    ## Setup

    ### Database
    Ensure PostgreSQL is running and the database exists:
    ```bash
    psql -U postgres -c "CREATE DATABASE medismart_db;"
    ```
    (Skip if already created)

    ### Backend
    ```bash
    cd backend
    python -m venv .venv
    # Windows:
    .venv\Scripts\activate
    # macOS/Linux:
    source .venv/bin/activate

    pip install -r requirements.txt

    # Copy environment template and set your PostgreSQL password:
    copy .env.example .env    # Windows
    # cp .env.example .env    # macOS/Linux
    # Edit .env and set your PostgreSQL password

    # Run database migrations:
    alembic upgrade head

    # Start the backend:
    uvicorn app.main:app --reload --port 8000
    ```
    API docs: http://localhost:8000/docs

    ### Frontend
    ```bash
    cd frontend
    npm install
    npm run dev
    ```
    App: http://localhost:5173

    ## Running Tests

    ```bash
    cd backend
    python -m pytest tests/ -v
    ```

    ## Project Structure

    ```
    MediSmart/
    ├── frontend/           # React + Vite + Tailwind CSS
    │   ├── src/
    │   │   ├── components/ # Reusable components (Navbar, Footer)
    │   │   ├── layouts/    # Page layouts (MainLayout)
    │   │   └── pages/      # Route pages (Home, Login, Register)
    │   └── package.json
    ├── backend/            # FastAPI + SQLAlchemy
    │   ├── app/
    │   │   ├── api/v1/     # API endpoints
    │   │   ├── core/       # Config, database
    │   │   ├── models/     # SQLAlchemy models
    │   │   ├── schemas/    # Pydantic schemas
    │   │   └── services/   # Business logic
    │   ├── alembic/        # Database migrations
    │   ├── tests/          # pytest tests
    │   └── requirements.txt
    ├── .gsd/               # Project management (GSD methodology)
    └── README.md
    ```

    ## Development Status

    See `.gsd/ROADMAP.md` for full development phases.
    ```

    AVOID: Claiming real hospital partnerships or unverified features
    AVOID: Listing features that haven't been built yet as "available"
    USE: Clear separation between "implemented" and "planned" features
  </action>
  <verify>
    Test-Path README.md
  </verify>
  <done>
    - README.md exists in project root
    - Contains setup instructions for frontend, backend, and database
    - Contains test run instructions
    - Clearly states synthetic data disclaimer
    - Project structure documented
  </done>
</task>

## Must-Haves
After all tasks complete, verify:
- [ ] pytest tests pass for health endpoints and model structure
- [ ] README.md has complete setup instructions for both frontend and backend
- [ ] Test instructions are documented and verified
- [ ] No features beyond Phase 1 are claimed as working

## Success Criteria
- [ ] All tasks verified passing
- [ ] Must-haves confirmed
- [ ] New developer can set up the project using README.md alone
