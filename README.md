# MediSmart

> **AI-Powered Hospital Discovery, Appointment Booking & Real-Time Queue Management System**

MediSmart is a modern healthcare web platform designed to streamline patient discovery of nearby medical facilities, dynamic doctor appointment booking, real-time digital queue management, and operational machine learning predictions for waiting times and appointment attendance.

> ⚠️ **Notice**: This platform uses **synthetic clinical and hospital simulation data** for demonstration and development purposes. Predictions derive from simulation models and are not clinically validated for medical triage.

---

## Key Features

1. **🏥 Hospital Discovery & Interactive Maps**:
   - Geolocation-aware directory of hospitals and multi-specialty healthcare centers.
   - Interactive Leaflet / OpenStreetMap mapping with geographic pin markers.
   - Multi-parameter filtering by specialty, facility capabilities, city, and emergency facilities.

2. **🩺 Doctor Directory & Dynamic Slot Scheduling**:
   - Directory of verified specialists and clinical practitioners.
   - Dynamic 30-minute consultation slot generation (09:00 - 16:30, excluding lunch).
   - Database-level concurrency protection via PostgreSQL partial unique indexes (`uq_active_doctor_slot`) preventing double-booking race conditions.
   - Unique alphanumeric tracking token generation (`MS-YYYYMMDD-XXXX`).

3. **⏱️ Digital Queue & Real-Time Waiting Room**:
   - Patient check-in by appointment tracking token or UUID.
   - Transaction-scoped PostgreSQL advisory locks (`pg_advisory_xact_lock`) ensuring collision-free daily sequential token issuance (`Q-001`, `Q-002`, ...).
   - Real-time WebSocket live updates with dual-transport automatic 10-second polling fallback.
   - Strict clinical notes privacy: consultation annotations are strictly isolated to medical staff and never exposed in patient responses or public displays.

4. **📺 Public Waiting Room Monitor & Doctor Console**:
   - Standalone zero-PII high-contrast TV / wall kiosk display (`/queue/monitor`) showing "Now Serving" and upcoming queue tokens with audio chimes.
   - Dedicated clinical console (`/queue/doctor`) allowing doctors to call next patient, record clinical notes, complete consultations, skip no-shows, and recall patients.

5. **🤖 Machine Learning Intelligence (Simulation Models)**:
   - **Waiting-Time Prediction**: In-memory XGBoost regression pipeline predicting elapsed minutes until consultation call, wrapped with non-negative constraints (`NonNegativeRegressor`).
   - **Appointment No-Show Prediction**: In-memory Logistic Regression classification pipeline calculating attendance risk probabilities against a calibrated decision threshold of 0.50.
   - Transparent synthetic disclosure returned on all predictions.

---

## Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 19, Vite 8, Tailwind CSS v4 (`@tailwindcss/vite`), React Router v7, Lucide Icons |
| **Backend** | Python 3.13+, FastAPI (ASGI), SQLAlchemy 2.0 (Async), Pydantic v2, Uvicorn |
| **Database** | PostgreSQL 18.6 (or 15+), Alembic migrations, AsyncPG (runtime), Psycopg2 (migrations) |
| **Machine Learning** | scikit-learn, XGBoost, pandas, NumPy, joblib (cached thread-safe in-memory inference) |
| **Real-Time** | WebSockets (FastAPI WebSocket endpoint) with automatic HTTP polling fallback |
| **Maps** | Leaflet, React-Leaflet, OpenStreetMap public tiles |
| **Testing** | pytest, pytest-asyncio, httpx, oxlint, Vite production bundler |

---

## Directory Structure

```
MediSmart/
├── backend/
│   ├── alembic/              # Database migration versions and environment
│   ├── app/
│   │   ├── api/v1/           # API routers (auth, hospitals, doctors, appointments, queue, predictions)
│   │   ├── core/             # Settings, database engine, security (Argon2id/JWT), WebSocket manager
│   │   ├── ml/               # ML dataset generator, training scripts, and serialized pipelines (.joblib)
│   │   ├── models/           # SQLAlchemy models (User, Hospital, Doctor, Appointment, QueueEntry)
│   │   ├── schemas/          # Pydantic validation schemas (requests/responses)
│   │   ├── services/         # Reusable business logic & in-memory ML inference service
│   │   └── main.py           # FastAPI application entrypoint & CORS middleware
│   ├── scripts/              # Seed scripts (seed_hospitals.py, seed_doctors.py, create_admin.py)
│   ├── tests/                # 171 automated regression & integration tests
│   ├── .env.example          # Backend environment variables template
│   ├── alembic.ini           # Alembic configuration
│   └── requirements.txt      # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/       # UI components (Navbar, Footer, Modals, Badges, Cards)
│   │   │   ├── appointments/ # Slot booking modal, appointment cards, attendance risk badge
│   │   │   ├── doctors/      # Doctor cards and filtering controls
│   │   │   ├── hospitals/    # Hospital cards, detail modal, and creation modal
│   │   │   ├── map/          # Leaflet OpenStreetMap component
│   │   │   ├── ml/           # Model status and risk badges
│   │   │   └── queue/        # Patient queue tracker, Doctor console, TV Waiting room monitor
│   │   ├── context/          # AuthContext (HttpOnly cookie session management)
│   │   ├── hooks/            # useQueueSocket (WebSocket + 10s polling fallback)
│   │   ├── layouts/          # Layout shells
│   │   ├── pages/            # Views (Home, Hospitals, Doctors, Appointments, Queue, Login, Register)
│   │   └── services/         # api.js fetch client with credentials included
│   ├── index.html            # Application HTML shell & Google Fonts
│   ├── package.json          # Node dependencies & build scripts
│   ├── vite.config.js        # Vite + Tailwind v4 + Proxy configuration
│   └── .env.example          # Frontend environment variables template
├── .gsd/                     # GSD development roadmap, phase plans, and verification summaries
└── README.md                 # Project documentation
```

---

## Getting Started

### Prerequisites

- **Node.js** (v18.0.0 or higher) & **npm**
- **Python** (v3.11 or higher, tested on Python 3.13)
- **PostgreSQL 18.6** (or 15+) running locally or accessible remotely

---

### 1. Database Setup

Create the local PostgreSQL database:

```sql
psql -U postgres
CREATE DATABASE medismart_db;
CREATE DATABASE medismart_test_db; -- For isolated automated testing
```

---

### 2. Backend Setup

1. **Navigate to the backend directory**:
   ```bash
   cd backend
   ```

2. **Create and activate a virtual environment**:
   ```bash
   # Windows (PowerShell)
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and set your local PostgreSQL password:
   ```env
   DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/medismart_db
   SECRET_KEY=your-secure-random-32-character-key
   CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
   API_V1_PREFIX=/api/v1
   ```

5. **Run database migrations**:
   ```bash
   alembic upgrade head
   ```

6. **Seed demonstration data (optional)**:
   ```bash
   python scripts/seed_hospitals.py
   python scripts/seed_doctors.py
   ```

7. **Start the FastAPI backend server**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   - API Root: `http://localhost:8000/`
   - Interactive Swagger Docs: `http://localhost:8000/docs`
   - Health Check: `http://localhost:8000/api/v1/health`

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

3. **Configure environment variables (optional)**:
   ```bash
   cp .env.example .env
   ```

4. **Start the Vite development server**:
   ```bash
   npm run dev
   ```
   - Web Application: `http://localhost:5173/`
   - Waiting Room TV Display: `http://localhost:5173/queue/monitor`

---

## Running Automated Tests

### Backend Regression Suite

The backend test suite is strictly isolated to `medismart_test_db` to protect development data:

```bash
cd backend
pytest -v
```

All 171 automated tests verify:
- Authentication, Argon2id hashing, and RBAC authorization boundaries
- Concurrency conflict handling and partial unique indexes
- Sequential token allocation with advisory locks
- Patient privacy and clinical note isolation
- ML inference services, non-negative bounds, and 0.50 decision threshold
- Sanitized error handling (zero internal path/stack trace leakage)

### Frontend Verification

```bash
cd frontend
npx oxlint       # Fast lint check (0 errors, 0 warnings)
npm run build    # Production bundle verification
```

---

## Screenshots

*(Screenshots will be placed here in future updates)*

| Screen | Description |
|---|---|
| *Hospital Discovery Map* | Interactive Leaflet view with facility cards |
| *Doctor Slot Booking* | Real-time 30-minute calendar slots with conflict protection |
| *Patient Live Queue Tracker* | Live token status, AI wait-time estimation, and turn alerts |
| *Doctor Clinical Console* | Active exam room, consultation timer, and patient workflow |
| *Waiting Room TV Monitor* | Zero-PII full-screen wall display with audio chime |

---

## License

This project is licensed under the MIT License.
