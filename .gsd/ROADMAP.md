# ROADMAP.md

> **Current Phase**: Not started
> **Milestone**: v1.0

## Must-Haves (from SPEC)

- [ ] Interactive hospital map with real geographic data
- [ ] Patient registration, login, role-based access
- [ ] Doctor search and appointment booking
- [ ] Digital queue with real-time WebSocket updates
- [ ] ML-based wait-time and no-show predictions
- [ ] Four role-based dashboards
- [ ] Notification system (in-app minimum)
- [ ] Analytics and reporting

## Phases

### Phase 1: Project Foundation & Architecture
**Status**: ✅ Complete
**Objective**: Establish the full-stack project skeleton — backend (FastAPI + PostgreSQL), frontend (React + Vite + Tailwind CSS), database schema, and dev tooling. Both servers run locally and communicate via API.
**Deliverables**:
- FastAPI backend with project structure, CORS, health & DB connectivity endpoints
- PostgreSQL schema against existing local medismart_db (users, hospitals, doctors, appointments, queues)
- Frontend with Tailwind CSS v4, routing (react-router), and layout shell (preserving existing Vite setup)
- Environment configuration (.env gitignored, .env.example template, no mandatory Docker)
- Basic backend tests (pytest) and comprehensive README.md developer documentation
**Requirements**: Foundation for all subsequent phases

### Phase 2: Authentication & User Management
**Status**: ⬜ Not Started
**Objective**: Implement secure user registration, login, and role-based access control for all four user roles.
**Deliverables**:
- User registration and login API (JWT + bcrypt)
- Role-based middleware (patient, doctor, hospital_admin, system_admin)
- Frontend auth pages (register, login, protected routes)
- User profile management
**Requirements**: REQ-04 (Patient registration, login, secure role-based access)

### Phase 3: Hospital Discovery & Interactive Map
**Status**: ⬜ Not Started
**Objective**: Build the interactive map-based hospital discovery system using OpenStreetMap and Leaflet.
**Deliverables**:
- Hospital CRUD API for admins
- Interactive Leaflet map with hospital markers (real geographic coordinates)
- Search and filter by location, specialty, facilities, availability
- Hospital detail pages with doctor listings
- Synthetic hospital data for real cities (clearly labeled)
**Requirements**: REQ-01, REQ-02

### Phase 4: Doctor Discovery & Appointment Booking
**Status**: ⬜ Not Started
**Objective**: Enable patients to find doctors and book, cancel, and review appointments.
**Deliverables**:
- Doctor profile API and search/filter endpoints
- Appointment booking, cancellation, and history APIs
- Doctor availability calendar (slot-based)
- Frontend: doctor cards, booking flow, appointment history page
- Doctor dashboard: view schedule, manage slots
**Requirements**: REQ-03, REQ-05

### Phase 5: Digital Queue & Real-Time Updates
**Status**: ⬜ Not Started
**Objective**: Implement the digital queue system with token generation and live WebSocket updates.
**Deliverables**:
- Queue token generation on appointment check-in
- WebSocket server for real-time queue position broadcast
- Queue board UI (patients see their position, estimated wait)
- Doctor queue panel (call next, skip, mark complete)
- Hospital admin queue configuration (max queue size, hours)
**Requirements**: REQ-06, REQ-07

### Phase 6: ML Predictions (Wait Time & No-Show)
**Status**: ⬜ Not Started
**Objective**: Train and deploy ML models for waiting-time regression and no-show classification using synthetic data.
**Deliverables**:
- Synthetic training data generator (appointment history with features)
- Wait-time regression model (scikit-learn / XGBoost)
- No-show classification model (XGBoost)
- Prediction API endpoints integrated into booking and queue flows
- Model evaluation with honestly reported metrics
- ML pipeline documented (data → train → evaluate → serve)
**Requirements**: REQ-09, REQ-10

### Phase 7: Notifications & Alerts
**Status**: ⬜ Not Started
**Objective**: Implement notification system — in-app notifications (minimum), with push notification infrastructure planned.
**Deliverables**:
- In-app notification system (bell icon, notification center)
- Queue change alerts (position changed, turn approaching)
- Appointment reminders and status change notifications
- Push notification infrastructure (Web Push API / service worker — free tier)
- Notification preferences per user
**Requirements**: REQ-08

### Phase 8: Dashboards & Analytics
**Status**: ⬜ Not Started
**Objective**: Build all four role-based dashboards and the analytics/reporting system.
**Deliverables**:
- Patient dashboard (upcoming appointments, queue status, history)
- Doctor dashboard (today's schedule, queue panel, patient stats)
- Hospital admin dashboard (hospital metrics, doctor management, queue config)
- System admin dashboard (platform-wide stats, user management, hospital management)
- Analytics charts (appointment volume, wait times, no-show rates, peak hours)
- CSV/PDF report export
**Requirements**: REQ-11, REQ-12

### Phase 9: Polish, Integration Testing & Documentation
**Status**: ⬜ Not Started
**Objective**: End-to-end integration testing, UI polish, responsive design review, and comprehensive documentation.
**Deliverables**:
- End-to-end user flow testing (register → book → queue → complete)
- Responsive design audit and fixes
- Error handling and edge cases
- README with full setup instructions
- API documentation (auto-generated from FastAPI)
- User guide / walkthrough
**Requirements**: All success criteria validated
