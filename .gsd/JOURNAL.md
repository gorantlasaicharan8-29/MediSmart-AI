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

---

## 2026-10-20

### Phase 5.5: Security & Integrity Remediation
- **Safety Review**:
  - Confirmed active baseline in `medismart_db`: 8 hospitals, 10 doctors, 10 users, 0 appointments, 0 queue entries, head revision `52a1b9e8c4d1`.
  - Created dedicated PostgreSQL database `medismart_test_db`.
- **Patient Privacy Fix**:
  - Removed `notes` field from `QueueEntryResponse` in `backend/app/schemas/queue.py`.
  - Updated `check_in_appointment` and `get_my_queue_entry` in `backend/app/api/v1/queue.py` to eliminate note leakage.
  - Confirmed `DoctorQueueItemResponse` and `DoctorQueueResponse` retain clinical notes for authorized clinical staff.
  - Confirmed `QueuePublicBoardResponse` and WebSocket broadcasts strictly exclude clinical notes and patient PII.
- **Hospital Affiliation Architecture**:
  - Authored additive migration `63b2c1f9d5e2_add_user_hospital_affiliation.py` adding nullable `users.hospital_id` with foreign key and index.
  - Updated `User` model with `hospital_id` column and `Hospital.hospital_admins` relationship.
  - Updated `backend/scripts/create_admin.py` to support authoritative `--hospital-id` provisioning.
  - Updated `backend/app/api/v1/auth.py` and `backend/app/schemas/auth.py` to embed persistent `hospital_id` in token issuance.
  - Updated `backend/app/core/deps.py` to validate hospital affiliation directly from PostgreSQL rather than trusting JWT claims or client headers.
- **Test Database Isolation**:
  - Configured `backend/tests/conftest.py` with hard fail-fast assertion ensuring all pytest runs strictly target `medismart_test_db`.
  - Verified migration upgrade and downgrade on `medismart_test_db`.
  - Seeded standard reference fixtures in `medismart_test_db`.
- **Testing & Verification**:
  - Added 12 regression tests in `backend/tests/test_remediation_phase5_5.py` (all passed).
  - Executed full test suite (105/105 tests passed across all 8 test modules).
  - Frontend: `oxlint` passed with 0 errors/warnings; production build succeeded cleanly.
  - Verified `medismart_db` baseline data and schema remain strictly untouched at `52a1b9e8c4d1`.

### Phase 6: Machine Learning Foundation & Prediction Engine
- **Phase 6.1 (Datasets)**:
  - Generated reproducible synthetic datasets (`waiting_time_dataset.csv`, 5,000 records; `noshow_dataset.csv`, 10,000 records) outside the database with clear synthetic provenance.
  - Passed 19 validation tests (`test_ml_dataset.py`) confirming schemas, value bounds, chronological ordering, and zero target leakage.
- **Phase 6.2 (Waiting-Time Model)**:
  - Trained and compared waiting-time regression pipelines (Baseline Dummy, Ridge, Random Forest, XGBoost) using chronological train/test splits.
  - Persisted best performing pipeline (`waiting_time_pipeline.joblib`) with custom transformer `NonNegativeWaitPredictor`.
  - Passed 12 unit tests (`test_ml_waiting_time.py`).
- **Phase 6.3 (No-Show Model)**:
  - Trained and evaluated no-show classification models (Baseline Dummy, Logistic Regression, Random Forest, XGBoost).
  - Persisted best model (`noshow_pipeline.joblib`) with calibrated `ThresholdClassifier` (optimal validation threshold=0.50).
  - Passed 11 unit tests (`test_ml_noshow.py`).
- **Phase 6.4 (Shared Prediction Service)**:
  - Implemented thread-safe in-memory `MLPredictionService` (`app/ml/service.py`) and singleton bridge (`app/services/ml_prediction.py`).
  - Enforced Pydantic validation schemas (`schemas/ml.py`) with synthetic disclosure notices and risk band calibrations.
  - Passed 12 unit tests (`test_ml_service.py`).
- **Phase 6.5 (Prediction API Endpoints)**:
  - Implemented FastAPI router (`app/api/v1/predictions.py`) with `POST /waiting-time`, `POST /no-show`, and `GET /status`.
  - Mounted router under prefix `/predictions` in `app/api/v1/__init__.py`.
  - Protected endpoints with active user authentication (`get_current_active_user`).
  - Implemented sanitized error responses (503 Service Unavailable when model artifacts are missing/corrupt, 500 on inference failure), strictly concealing internal filesystem paths and stack traces.
  - Confirmed zero database mutations or reads during inference.
  - Added 12 API tests (`test_ml_api.py`); full backend test suite passing (171/171 tests).

