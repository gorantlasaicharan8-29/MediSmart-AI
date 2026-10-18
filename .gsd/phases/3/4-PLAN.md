---
phase: 3
plan: 4
wave: 2
depends_on: [1, 2, 3]
gap_closure: false
---

# Plan 3.4: Automated Test Suite & Full Integration Verification

## Objective
Implement comprehensive automated tests for hospital discovery, geo-filtering, and RBAC authorization in `backend/tests/test_hospitals.py`, verify non-destructive test execution against PostgreSQL, run full frontend verification, and prepare Phase 3 completion report.

## Context
- `backend/tests/`
- `backend/app/api/v1/hospitals.py`
- `backend/app/models/hospital.py`
- `frontend/`

## Security & Architecture Rules
1. **Non-Destructive Test Execution**:
   - Tests MUST NOT drop, reset, or truncate tables in `medismart_db`.
   - Test hospitals use unique prefixes (`test_hospital_*`) and are cleaned up in teardown fixtures.
2. **Comprehensive Test Coverage**:
   - Public listing, full-text search, and multi-criteria array filtering.
   - Missing coordinates edge case: ensures facilities with null latitude/longitude return valid JSON and do not cause exceptions.
   - Spatial proximity filtering: calculates distances safely.
   - OpenStreetMap attribution and data source tracking (`data_source` and `source_attribution`).
   - Four-role RBAC authorization matrix for hospital mutation:
     - Patients and unauthenticated users receive 401/403 on create/edit/delete.
     - Doctors receive 403 on create/edit/delete.
     - Hospital Admins can create and edit facilities (201/200), but cannot delete (403).
     - System Admins have full access (create, edit, delete).

## Tasks

<task type="auto" effort="medium">
  <name>Create backend hospital discovery and RBAC test suite</name>
  <files>
    backend/tests/test_hospitals.py
  </files>
  <action>
    1. Create `backend/tests/test_hospitals.py`:
       - `test_list_hospitals_public`: Public access to `/api/v1/hospitals`.
       - `test_search_hospitals_by_name_and_city`: Case-insensitive text and city filtering.
       - `test_filter_by_specialty_and_facility`: PostgreSQL array overlap filtering.
       - `test_missing_coordinates_handling`: Asserts hospital with null coordinates returns `latitude: null, longitude: null, has_coordinates: false` without 500 errors.
       - `test_geo_proximity_filter`: Distance filter with lat/lng/radius_km.
       - `test_data_source_and_osm_attribution`: Asserts presence of `data_source` and OSM attribution.
       - `test_create_hospital_rbac`: Verifies 401 for anonymous, 403 for Patient/Doctor, 201 for Hospital Admin and System Admin.
       - `test_update_hospital_rbac`: Verifies 403 for Patient, 200 for Hospital Admin.
       - `test_delete_hospital_rbac`: Verifies 403 for Hospital Admin, 200 for System Admin.
       - Non-destructive fixture deletes only records where `name.like("test_hospital_%")`.
  </action>
  <verify>
    .\.venv\Scripts\pytest.exe tests/test_hospitals.py -v (in backend/)
  </verify>
  <done>
    - All hospital tests pass
    - Non-destructive execution confirmed
  </done>
</task>

<task type="auto" effort="low">
  <name>Run full regression test suite and frontend production build</name>
  <files>
    backend/tests/
    frontend/dist/
  </files>
  <action>
    1. Run all backend tests: `.\.venv\Scripts\pytest.exe -v` (all Phase 1, Phase 2, and Phase 3 tests).
    2. Check PostgreSQL database integrity to ensure no tables dropped and 0 leftover test records.
    3. Run frontend lint: `npm run lint` (0 errors, 0 warnings).
    4. Run frontend production build: `npm run build` (clean Vite bundle).
  </action>
  <verify>
    .\.venv\Scripts\pytest.exe -v (in backend/)
    npm run build (in frontend/)
  </verify>
  <done>
    - 100% backend tests pass
    - Database integrity verified
    - Frontend build succeeds with zero lint warnings
  </done>
</task>

## Must-Haves
- [ ] Tests cover search, specialty filtering, missing coordinates, and RBAC matrix
- [ ] Tests never drop or truncate medismart_db tables
- [ ] Frontend builds cleanly with zero errors
