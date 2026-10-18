---
phase: 3
plan: 2
wave: 1
gap_closure: false
---

# Plan 3.2: Backend Hospital API with Search, Geo-Filtering & Admin RBAC

## Objective
Implement public and administrative REST API endpoints for hospitals in FastAPI, supporting full-text search, multi-criteria filtering (city, specialty, facility, coordinate availability), geographical proximity/bounding calculations, and backend-enforced RBAC for hospital administration.

## Context
- `backend/app/models/hospital.py`
- `backend/app/core/deps.py` (`require_roles`, `get_current_active_user`)
- `backend/app/core/database.py` (`get_db`)

## Security & Architecture Rules
1. **Public Read vs Admin Mutation**:
   - `GET /api/v1/hospitals` and `GET /api/v1/hospitals/{id}` are publicly accessible (no authentication required) so patients and visitors can discover care facilities.
   - `POST /api/v1/hospitals` and `PUT /api/v1/hospitals/{id}` require `hospital_admin` or `system_admin` role (`require_roles("hospital_admin", "system_admin")`).
   - `DELETE /api/v1/hospitals/{id}` is restricted to `system_admin` only.
2. **Robust Filtering & Graceful Fallbacks**:
   - Query filters: `search` (substring match on name, address, or city), `city`, `specialty`, `facility`, `data_source`, `has_coords` (bool).
   - Distance calculation: Haversine distance calculation in SQL/Python when `lat`, `lng`, and `radius_km` are provided.
   - Hospitals with missing coordinates are excluded from spatial distance queries without causing calculation exceptions, and are flagged clearly in results (`has_coordinates: false`).
3. **Data Provenance Preservation**:
   - APIs return `data_source` and `source_attribution` with every hospital record to respect OpenStreetMap attribution requirements.

## Tasks

<task type="auto" effort="medium">
  <name>Create Pydantic schemas and hospital repository query logic</name>
  <files>
    backend/app/schemas/hospital.py
    backend/app/schemas/__init__.py
  </files>
  <action>
    1. Create `backend/app/schemas/hospital.py`:
       - `HospitalBase`: name, address, city, state, latitude (Optional[float]), longitude (Optional[float]), phone (Optional[str]), email (Optional[str]), specialties (List[str]), facilities (List[str]), is_active (bool), data_source (str), source_attribution (Optional[str]).
       - `HospitalCreate`: required name, address, city, state; optional coordinates, contact info, arrays.
       - `HospitalUpdate`: partial update schema with all fields optional.
       - `HospitalResponse`: includes `id` (UUID), `created_at`, `updated_at`, `has_coordinates` (computed boolean).
       - `HospitalListResponse`: `items` (List[HospitalResponse]), `total` (int), `limit` (int), `offset` (int).
    2. Export hospital schemas in `backend/app/schemas/__init__.py`.
  </action>
  <verify>
    Import schemas via python -c "from app.schemas.hospital import HospitalResponse, HospitalListResponse; print('SCHEMAS_OK')"
  </verify>
  <done>
    - Pydantic schemas validate all hospital inputs and outputs
    - Safe handling for optional coordinates
  </done>
</task>

<task type="auto" effort="medium">
  <name>Implement hospital router with search, geo-filtering, and RBAC guards</name>
  <files>
    backend/app/api/v1/hospitals.py
    backend/app/api/v1/__init__.py
  </files>
  <action>
    1. Create `backend/app/api/v1/hospitals.py`:
       - `GET /`: Search and filter hospitals with pagination.
         - Filters: `search: Optional[str]`, `city: Optional[str]`, `specialty: Optional[str]`, `facility: Optional[str]`, `data_source: Optional[str]`, `has_coords: Optional[bool]`, `lat: Optional[float]`, `lng: Optional[float]`, `radius_km: Optional[float]`.
         - Safely ignores null coordinates in proximity calculations.
         - Returns `HospitalListResponse`.
       - `GET /{hospital_id}`: Retrieves single hospital by UUID. Raises 404 if not found.
       - `POST /`: Creates a new hospital. Enforces `Depends(require_roles("hospital_admin", "system_admin"))`.
       - `PUT /{hospital_id}`: Updates existing hospital. Enforces `Depends(require_roles("hospital_admin", "system_admin"))`.
       - `DELETE /{hospital_id}`: Soft deletes or removes hospital. Enforces `Depends(require_roles("system_admin"))`.
    2. Register router in `backend/app/api/v1/__init__.py` under `/hospitals`.
  </action>
  <verify>
    Verify router routes with python -c "from app.api.v1.hospitals import router; print('HOSPITAL_ROUTES:', [r.path for r in router.routes])"
  </verify>
  <done>
    - Hospital endpoints live and accessible
    - Public discovery endpoints open, modification endpoints guarded by RBAC
  </done>
</task>

## Must-Haves
- [ ] Public endpoints for listing and viewing hospital details
- [ ] Search by name/city and filtering by specialty/facility
- [ ] Safe handling of facilities lacking latitude/longitude
- [ ] Administrative creation/editing restricted to `hospital_admin` and `system_admin`
- [ ] Deletion restricted to `system_admin`
