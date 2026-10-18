# Plan 3.2: Backend Hospital API with Search, Geo-Filtering & Admin RBAC — Summary

## Accomplishments
- Implemented comprehensive Pydantic v2 schemas in `backend/app/schemas/hospital.py`:
  - `HospitalBase`, `HospitalCreate`, `HospitalUpdate`, `HospitalResponse`, `HospitalListResponse`.
  - Added computed property `has_coordinates` safely evaluating presence of `latitude` and `longitude`.
  - Exported schemas in `backend/app/schemas/__init__.py`.
- Developed FastAPI hospital router in `backend/app/api/v1/hospitals.py`:
  - `GET /api/v1/hospitals`: Public search and discovery endpoint. Supports case-insensitive text search (name, address, city, state), exact city filter, PostgreSQL array filtering for specialties and facilities (`specialties.contains(...)`), data source filtering, coordinate existence filtering (`has_coords`), and spatial proximity filtering via Haversine formula calculation.
  - `GET /api/v1/hospitals/{hospital_id}`: Public detail view returning complete facility metadata and OpenStreetMap attribution.
  - `POST /api/v1/hospitals`: Facility creation guarded by `require_roles("hospital_admin", "system_admin")`.
  - `PUT /api/v1/hospitals/{hospital_id}`: Facility updates guarded by `require_roles("hospital_admin", "system_admin")`.
  - `DELETE /api/v1/hospitals/{hospital_id}`: Facility deletion restricted exclusively to `system_admin`.
- Mounted `hospitals_router` in `backend/app/api/v1/__init__.py` under `/hospitals`.
- Validated via live async client:
  - `GET /api/v1/hospitals` returned all 8 hospitals with status 200.
  - Tested handling of missing coordinates: records with null coordinates return `has_coordinates: false` without breaking queries.

## Commits
- Pending commit for Plan 3.2.
