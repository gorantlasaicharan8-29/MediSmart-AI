# MediSmart

> **Smart Hospital Discovery, Doctor Appointment & Real-Time Queue Management System**

MediSmart is a full-stack healthcare platform engineered to streamline patient discovery of nearby medical facilities, doctor appointment scheduling, and real-time digital queue management with wait-time intelligence.

> ⚠️ **Notice**: This platform uses **synthetic clinical and hospital simulation data**. No real patient records or institutional partnerships are utilized.

---

## Architecture & Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 19, Vite 8, Tailwind CSS v4 (`@tailwindcss/vite`), React Router v7 |
| **Backend** | Python 3.13+, FastAPI, SQLAlchemy 2.x (Async), Pydantic v2 |
| **Database** | PostgreSQL 18.6 (Local instance, `medismart_db`), Alembic migrations |
| **Database Drivers** | `asyncpg` (Async runtime queries), `psycopg2-binary` (Synchronous Alembic migrations) |
| **Testing** | `pytest`, `pytest-asyncio`, `httpx` (Backend), `oxlint`, Vite build (Frontend) |

---

## Prerequisites

Before running MediSmart, ensure you have the following installed on your machine:

- **Node.js** (v18.0.0 or higher) & **npm**
- **Python** (v3.11 or higher, tested on Python 3.13)
- **PostgreSQL 18.6** installed and running locally on port `5432`

---

## Getting Started

### 1. Database Setup

Ensure PostgreSQL 18.6 is running locally and that the database `medismart_db` exists:

```sql
-- Connect to local PostgreSQL instance
psql -U postgres

-- Create the database if not already created
CREATE DATABASE medismart_db;
```

---

### 2. Backend Setup

1. **Navigate to the backend directory**:
   ```bash
   cd backend
   ```

2. **Create and activate a Python virtual environment**:
   ```bash
   # Windows (PowerShell)
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

   # macOS / Linux
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   Copy the example template to create your local `.env` file:
   ```bash
   # Windows
   copy .env.example .env

   # macOS / Linux
   cp .env.example .env
   ```

   Edit `backend/.env` and update the `DATABASE_URL` with your local PostgreSQL password:
   ```env
   # Format: postgresql+asyncpg://<USER>:<PASSWORD>@localhost:5432/medismart_db
   # Note: If your password contains special characters (like '@'), URL-encode them (e.g., '@' -> '%40')
   DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/medismart_db
   SECRET_KEY=dev-secret-change-in-production-random-bytes-key-32chars
   CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
   API_V1_PREFIX=/api/v1
   ```

5. **Run database migrations**:
   Apply the existing Alembic migration to create all 5 core tables (`users`, `hospitals`, `doctors`, `appointments`, `queue_entries`):
   ```bash
   alembic upgrade head
   ```

6. **Start the FastAPI backend server**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   - API Root: `http://localhost:8000/`
   - Interactive Swagger Docs: `http://localhost:8000/docs`
   - Health Check: `http://localhost:8000/api/v1/health`
   - Database Health Check: `http://localhost:8000/api/v1/health/db`

---

### 3. Frontend Setup

1. **Navigate to the frontend directory**:
   ```bash
   cd frontend
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Start the Vite development server**:
   ```bash
   npm run dev
   ```
   - Web Application: `http://localhost:5173/`

The frontend includes a pre-configured Vite proxy forwarding `/api` requests directly to `http://localhost:8000`, allowing live end-to-end communication with the backend.

---

## Running Automated Tests

### Backend Tests (pytest)

Run the backend test suite to verify endpoints and database model schemas:

```bash
cd backend
python -m pytest tests/ -v
```

All 12 tests verify:
- API root and Swagger UI documentation endpoints
- System health and live database connectivity endpoints
- Model table registrations, primary keys (UUID), foreign keys, and cascading constraints

### Frontend Verification

Validate frontend compilation and coding standards:

```bash
cd frontend

# Linting with oxlint
npm run lint

# Production build test
npm run build
```

---

## Project Structure

```
MediSmart/
├── backend/
│   ├── alembic/              # Database migration versions and environment
│   ├── app/
│   │   ├── api/v1/           # API routes (health, auth, hospitals, etc.)
│   │   ├── core/             # Configuration (pydantic-settings) & database engine
│   │   ├── models/           # SQLAlchemy models (User, Hospital, Doctor, Appointment, QueueEntry)
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── services/         # Business logic services
│   │   └── main.py           # FastAPI application factory & CORS setup
│   ├── tests/                # pytest test suite
│   ├── .env.example          # Environment variables template (committed)
│   ├── .env                  # Local secret configuration (gitignored)
│   ├── alembic.ini           # Alembic migration configuration
│   └── requirements.txt      # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/       # Reusable UI components (Navbar, Footer)
│   │   ├── layouts/          # Layout shells (MainLayout)
│   │   ├── pages/            # Application pages (Home, Login, Register, NotFound, etc.)
│   │   ├── services/         # API client utilities
│   │   ├── App.jsx           # React Router route definitions
│   │   ├── index.css         # Tailwind CSS v4 entrypoint
│   │   └── main.jsx          # React DOM entrypoint
│   ├── index.html            # Application HTML shell & Google Fonts
│   ├── package.json          # Node dependencies & scripts
│   └── vite.config.js        # Vite + Tailwind v4 + Proxy configuration
├── .gsd/                     # GSD development roadmap, state, and phase plans
├── .gitignore                # Root gitignore protecting credentials and environments
└── README.md                 # Project documentation
```

---

## Roadmap

- [x] **Phase 1: Project Foundation & Architecture** (FastAPI, PostgreSQL 18.6 schema, React 19 + Tailwind v4 shell, health checks)
- [ ] **Phase 2: Authentication & User Management** (JWT, bcrypt, 4 role-based dashboards)
- [ ] **Phase 3: Hospital Discovery & Interactive Map** (Leaflet, OpenStreetMap, geographic search)
- [ ] **Phase 4: Doctor Discovery & Appointment Booking** (Specialty matching, slot scheduling)
- [ ] **Phase 5: Digital Queue & Real-Time Tracking** (WebSockets, token generation, live queue updates)
- [ ] **Phase 6: Machine Learning Predictions** (Wait-time regression & appointment no-show classification)
- [ ] **Phase 7: Role-Based Dashboards & Notifications** (Patient, Doctor, Hospital Admin, System Admin views)
- [ ] **Phase 8: Analytics & Reporting** (Operational metrics, throughput, wait-time analysis)
- [ ] **Phase 9: Production Hardening, Polish & Handover** (Security audits, end-to-end integration, final release)
