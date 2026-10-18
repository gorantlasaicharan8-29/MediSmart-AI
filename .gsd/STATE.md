# STATE.md — Project Memory

> Last updated: 2026-10-18 15:25 IST

## Current Position

- **Phase**: 3 — Hospital Discovery & Interactive Map (COMPLETE ✓)
- **Status**: Verified & Committed
- **Completed Plans in Phase 3**:
  - Plan 3.1: Data Model Refinements, Additive Alembic Migration & Seed Data
  - Plan 3.2: Backend Hospital API with Search, Geo-Filtering & Admin RBAC
  - Plan 3.3: Frontend Interactive Leaflet Map & Hospital Discovery Directory
  - Plan 3.4: Automated Test Suite & Full Integration Verification
- **Next Up**: Phase 4 — Doctor Discovery & Appointment Booking

## Phase 3 Verification Summary

- **Geographic & OpenStreetMap Compliance**:
  - React Leaflet (v5) + Leaflet (v1.9) with standard OpenStreetMap tile layer and mandatory attribution:
    `&copy; OpenStreetMap contributors`.
  - Custom vector SVG medical cross markers styled with MediSmart theme colors.
  - Data provenance explicitly categorized (`data_source`: `"verified"`, `"imported"`, `"sample"`) and displayed via UI badges.
- **Resilience to Incomplete Information**:
  - `latitude` and `longitude` are safely nullable in `Hospital` model and PostgreSQL schema.
  - Facilities lacking coordinates are safely flagged (`has_coordinates: false`, `⚠️ GPS Pending`) and presented in list view without breaking map queries or rendering.
- **Backend Architecture & RBAC**:
  - Discovery endpoints `GET /api/v1/hospitals` and `GET /api/v1/hospitals/{id}` are publicly accessible.
  - Search (name, address, city), city exact filter, PostgreSQL array filters for specialties and facilities, and Haversine spatial proximity filtering (`lat`, `lng`, `radius_km`).
  - Creation and editing restricted to `hospital_admin` and `system_admin`.
  - Deletion restricted to `system_admin`.
- **Database Status**:
  - Additive Alembic migration applied (`75eb29345f17`).
  - Zero tables dropped or reset; all 5 core tables intact.
  - 8 seeded facilities (7 verified with real OSM coordinates, 1 sample facility without coordinates).
  - 0 leftover test records.
- **Automated Tests**:
  - 40/40 pytest tests passing in 3.32s (12 Phase 1 + 15 Phase 2 + 13 Phase 3).
- **Frontend Status**:
  - `oxlint`: 0 errors, 0 warnings across 24 files.
  - Vite production build: clean build in 601ms.

## Context Dump

### Decisions Made
- Decision 18: Use custom SVG medical divIcons for Leaflet to prevent bundler 404s and provide high-DPI retina rendering.
- Decision 19: Allow nullable latitude/longitude to gracefully handle facilities pending GPS surveys without schema corruption.
- Decision 20: Haversine distance bounding in PostgreSQL using safe clamped `least`/`greatest` bounds to prevent acos domain errors.

### Files of Interest
- `backend/app/models/hospital.py`: Hospital model with optional coordinates and source provenance.
- `backend/app/schemas/hospital.py`: Pydantic validation schemas with computed `has_coordinates`.
- `backend/app/api/v1/hospitals.py`: Public search, geo-proximity, and admin RBAC endpoints.
- `frontend/src/components/map/HospitalMap.jsx`: Leaflet OpenStreetMap interactive container with auto-bounds.
- `frontend/src/components/hospitals/`: Directory cards, filter panel, detail modal, and admin creation modal.
- `backend/tests/test_hospitals.py`: 13-test automated hospital suite.

## Next Steps
1. Discuss / Plan Phase 4: Doctor Discovery & Appointment Booking.
