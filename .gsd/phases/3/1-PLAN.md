---
phase: 3
plan: 1
wave: 1
gap_closure: false
---

# Plan 3.1: Data Model Refinements, Additive Alembic Migration & Seed Data

## Objective
Refine the `Hospital` SQLAlchemy model to safely handle optional geographic coordinates and data provenance tracking, execute an additive Alembic migration, and create an idempotent seeding script with real OpenStreetMap coordinates, clear source attribution, and sample edge cases (including hospitals with missing coordinates).

## Context
- `backend/app/models/hospital.py` (Hospital model)
- `backend/alembic/` (Alembic migration setup)
- PostgreSQL 18.6 `medismart_db`

## Security & Architecture Rules
1. **Zero Data Loss / Additive-Only Migration**:
   - Never drop or recreate the `hospitals` table.
   - Alter `latitude` and `longitude` to allow `nullable=True` so incomplete records or facilities pending GPS verification do not crash the database.
   - Add `data_source` (`String(50)`, default `"verified"`, server_default `"verified"`) to distinguish `verified`, `imported`, and `sample` records.
   - Add `source_attribution` (`String(255)`, nullable=True) for OpenStreetMap data attribution.
2. **OpenStreetMap Data Attribution & Integrity**:
   - For records using real geographic data, include clear attribution (`"© OpenStreetMap contributors"`).
   - Sample or mock data must be explicitly flagged with `data_source="sample"`.
3. **Graceful Handling of Incomplete Information**:
   - Support hospitals where coordinates are unknown or pending survey without breaking map queries or database integrity.

## Tasks

<task type="auto" effort="medium">
  <name>Update Hospital model and generate additive Alembic migration</name>
  <files>
    backend/app/models/hospital.py
    backend/alembic/versions/
  </files>
  <action>
    1. Update `backend/app/models/hospital.py`:
       - Make `latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)`.
       - Make `longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)`.
       - Add `data_source: Mapped[str] = mapped_column(String(50), default="verified", server_default="verified", nullable=False)`.
       - Add `source_attribution: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)`.
    2. Generate an additive Alembic revision:
       - Run `alembic revision --autogenerate -m "hospital_optional_coords_and_source_tracking"`.
       - Inspect generated migration to ensure it only alters column nullability and adds new columns with server defaults.
    3. Apply the migration using `alembic upgrade head`.
  </action>
  <verify>
    Inspect table columns using PostgreSQL information schema to confirm latitude/longitude are nullable and new columns exist.
  </verify>
  <done>
    - Hospital model updated cleanly
    - Additive migration applied to medismart_db without dropping tables
    - Zero data loss
  </done>
</task>

<task type="auto" effort="medium">
  <name>Create idempotent hospital seed script with verified OSM and sample data</name>
  <files>
    backend/scripts/seed_hospitals.py
  </files>
  <action>
    1. Create `backend/scripts/seed_hospitals.py`:
       - Define real metropolitan hospitals with accurate coordinates and OSM attribution:
         - e.g., AIIMS New Delhi (28.5672, 77.2100) — `data_source="verified"`, attribution `"© OpenStreetMap contributors"`
         - Fortis Hospital (28.4986, 77.0722) — `data_source="verified"`, attribution `"© OpenStreetMap contributors"`
         - Max Super Speciality (28.5284, 77.2120) — `data_source="verified"`, attribution `"© OpenStreetMap contributors"`
         - Apollo Hospital (28.5414, 77.2831) — `data_source="verified"`, attribution `"© OpenStreetMap contributors"`
       - Define sample hospitals with missing coordinates (`latitude=None`, `longitude=None`, `data_source="sample"`) to verify UI and API handling of facilities lacking GPS data.
       - Ensure script is idempotent: checks if hospital with matching name and city exists before adding.
    2. Execute seed script.
  </action>
  <verify>
    Run seed script and assert records inserted with verified coordinates and OSM attribution, plus sample record with null coordinates.
  </verify>
  <done>
    - Verified hospitals seeded with real coordinates and attribution
    - Incomplete/missing coordinate test record seeded safely
    - Idempotent execution verified
  </done>
</task>

## Must-Haves
- [ ] Existing `hospitals` table preserved without drop/reset
- [ ] Latitude and longitude columns safely accept nulls for incomplete data
- [ ] `data_source` and `source_attribution` columns present
- [ ] Real geographic data carries OpenStreetMap attribution
