# SPEC.md — Project Specification

> **Status**: `FINALIZED`

## Vision

MediSmart is a full-stack healthcare platform that enables patients to discover nearby hospitals on an interactive map, find and book appointments with doctors, and track their real-time position in a digital queue — eliminating the uncertainty and wasted time of traditional hospital waiting rooms. The system serves four user roles (patient, doctor, hospital admin, system admin) through dedicated dashboards, and uses machine learning to predict waiting times and appointment no-shows.

## Goals

1. **Hospital Discovery** — Interactive map-based hospital search using real geographic data (OpenStreetMap + Leaflet) with filtering by location, specialty, facilities, and availability.
2. **Doctor Discovery** — Browse and search doctors by specialty, hospital affiliation, ratings, and availability; receive personalized recommendations.
3. **Appointment Management** — Patient registration/login, appointment booking, cancellation, and full appointment history with role-based access control.
4. **Digital Queue System** — Token generation at check-in, real-time queue position tracking via WebSockets, live queue board updates.
5. **Smart Notifications** — Mobile push notifications for queue changes, estimated wait-time updates, and turn-approaching alerts (low-cost/free initial implementation).
6. **ML Predictions** — Regression-based waiting-time prediction and classification-based appointment no-show prediction using scikit-learn/XGBoost.
7. **Role-Based Dashboards** — Separate dashboard views for patients, doctors, hospital administrators, and system administrators.
8. **Analytics & Reporting** — Operational analytics (appointment volume, wait times, no-show rates, peak hours) with visual charts and exportable reports.

## Non-Goals (Out of Scope)

- Electronic Health Records (EHR) or medical data storage
- Telemedicine / video consultations
- Payment processing or insurance billing
- Real hospital API integrations or verified partnerships (synthetic data only, clearly labeled)
- Native mobile apps (web-first, responsive design; PWA considered later)
- HIPAA/GDPR compliance certification (follow best practices but no formal audit)
- Production deployment or cloud hosting setup

## Users

| Role | Description |
|------|-------------|
| **Patient** | Searches hospitals/doctors, books appointments, tracks queue position, receives notifications |
| **Doctor** | Views schedule, manages appointment slots, calls next patient in queue, views patient history |
| **Hospital Admin** | Manages hospital profile, doctor roster, facilities, queue configuration, views hospital analytics |
| **System Admin** | Manages all hospitals, users, system-wide analytics, platform configuration |

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Vite 8, Tailwind CSS |
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| Maps | OpenStreetMap + Leaflet.js |
| Real-time | WebSockets (FastAPI native) |
| ML | pandas, NumPy, scikit-learn, XGBoost |
| Auth | JWT (httpOnly cookies) + bcrypt |
| Version Control | Git + GitHub |

## Constraints

- **Preserve existing work** — Never overwrite or delete existing files without explicit permission
- **Phase-by-phase execution** — Build and test one phase at a time; no monolithic generation
- **Synthetic data only** — Use clearly labeled synthetic/seed data; never claim real hospital partnerships or fabricate model accuracy
- **Free tools preferred** — Use free/open-source tools and services; plan paid services for future phases only
- **Modular architecture** — Clean separation of concerns; backend and frontend independently runnable
- **Inspect before modify** — Always examine existing files before making changes
- **Honest ML** — Report actual metrics from training on synthetic data; do not invent accuracy numbers

## Success Criteria

- [ ] Interactive map renders real hospital locations with search/filter
- [ ] Patient can register, login, search hospitals/doctors, and book an appointment
- [ ] Doctor can view schedule and manage queue (call next patient)
- [ ] Queue position updates in real-time via WebSockets without page refresh
- [ ] ML models trained on synthetic data with honestly reported metrics
- [ ] All four role-based dashboards are functional and access-controlled
- [ ] Notification system delivers queue alerts (at minimum via in-app; push as stretch)
- [ ] Analytics dashboard shows appointment volume, wait times, no-show rates
- [ ] Application runs locally with documented setup instructions
