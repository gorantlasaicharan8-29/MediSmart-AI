---
phase: 2
plan: 4
wave: 2
depends_on: [1, 2, 3]
gap_closure: false
---

# Plan 2.4: Automated Auth Test Suite & Integration Verification

## Objective
Implement comprehensive automated tests for authentication and role-based authorization using pytest, verify end-to-end frontend and backend auth flows, and confirm zero regressions across the codebase.

## Context
- `backend/tests/conftest.py`
- `backend/app/api/v1/auth.py`
- `backend/app/core/security.py`
- `backend/app/core/deps.py`

## Tasks

<task type="auto" effort="medium">
  <name>Create backend authentication & RBAC test suite</name>
  <files>
    backend/tests/test_auth.py
  </files>
  <action>
    1. Create `backend/tests/test_auth.py`:
       - `test_register_user_success`: Register user, assert 201, assert response contains UUID and email, assert password is not returned.
       - `test_register_user_duplicate_email`: Attempt registering same email twice, assert 409 Conflict with clear detail message.
       - `test_argon2_password_hashing`: Inspect created user in database session, assert `hashed_password` starts with `$argon2id$`.
       - `test_login_success`: Login with valid credentials, assert 200 OK, assert `access_token` and `token_type == 'bearer'` returned.
       - `test_login_invalid_password`: Attempt login with incorrect password, assert 401 Unauthorized.
       - `test_login_nonexistent_user`: Attempt login with unknown email, assert 401 Unauthorized.
       - `test_get_current_user_me`: Query `/api/v1/auth/me` with Bearer token, assert 200 and matches user profile.
       - `test_get_me_unauthorized`: Query `/api/v1/auth/me` with no token or invalid token, assert 401 Unauthorized.
       - `test_rbac_patient_access`: Patient token on `patient-test` -> 200 OK; on `doctor-test` -> 403 Forbidden.
       - `test_rbac_doctor_access`: Doctor token on `doctor-test` -> 200 OK; on `admin-test` -> 403 Forbidden.
       - `test_rbac_admin_access`: System Admin token on `admin-test` -> 200 OK.
    2. Ensure test cleanup deletes only the test-generated test users by unique test email prefix (e.g. `test_*@example.com`), never touching any existing database records.
  </action>
  <verify>
    python -m pytest tests/test_auth.py -v (in backend/)
  </verify>
  <done>
    - All authentication and RBAC tests pass
    - 401 and 403 security controls verified
    - Argon2 hashing verified
  </done>
</task>

<task type="auto" effort="low">
  <name>Run full regression suite and frontend production build</name>
  <files>
    backend/tests/
    frontend/dist/
  </files>
  <action>
    1. Run all backend tests: `python -m pytest tests/ -v` (expect all Phase 1 + Phase 2 tests to pass).
    2. Run frontend linter: `npm run lint` (expect 0 errors, 0 warnings).
    3. Run frontend build: `npm run build` (expect clean production build).
  </action>
  <verify>
    python -m pytest tests/ -v (in backend/)
    npm run build (in frontend/)
  </verify>
  <done>
    - 100% backend tests pass
    - Frontend build succeeds with zero lint warnings
  </done>
</task>

## Must-Haves
- [ ] Automated tests cover registration, Argon2, login, token decode, and 4-role RBAC
- [ ] Duplicate email safety verified with 409 Conflict
- [ ] No database drops, resets, or data loss
- [ ] Zero secrets in Git or test output
