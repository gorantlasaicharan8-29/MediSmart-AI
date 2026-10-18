# Plan 3.1: Data Model Refinements, Additive Alembic Migration & Seed Data — Summary

## Accomplishments
- Refined `Hospital` SQLAlchemy model in `backend/app/models/hospital.py`:
  - Made `latitude` and `longitude` `Optional[float]` (`nullable=True`) so incomplete data or unverified coordinates do not crash the database or violate constraints.
  - Added `data_source` (`String(50)`, default `"verified"`, server_default `"verified"`) to explicitly categorize `verified`, `imported`, and `sample` facilities.
  - Added `source_attribution` (`String(255)`, nullable=True) for OpenStreetMap data provenance.
- Executed additive Alembic migration `75eb29345f17_hospital_optional_coords_and_source_.py`:
  - Preserved all existing tables, foreign keys, and records without table drops or resets.
  - Applied migration successfully to PostgreSQL 18.6 `medismart_db`.
- Created and executed idempotent seed utility `backend/scripts/seed_hospitals.py`:
  - Seeded 7 major metropolitan hospitals across India with real coordinates and OSM attribution (`"© OpenStreetMap contributors"`).
  - Seeded 1 sample demonstration health center with missing coordinates (`latitude=None, longitude=None, data_source="sample"`) to test graceful handling.
  - Verified idempotency (subsequent execution detected 8 existing facilities and added 0).
- Confirmed full test suite regression: 27/27 tests passed.

## Commits
- Pending commit for Plan 3.1.
