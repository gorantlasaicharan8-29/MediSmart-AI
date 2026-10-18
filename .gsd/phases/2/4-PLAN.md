---
phase: 2
plan: 4
wave: 2
depends_on: [1, 2, 3]
gap_closure: false
---

# Plan 2.4: Automated Auth Test Suite & Integration Verification

## Objective
Implement comprehensive automated tests for authentication and authorization using pytest, verify non-destructive test execution against PostgreSQL, run full frontend verification, and report complete Phase 2 results.

## Context
- `backend/tests/conftest.py`
- `backend/app/api/v1/auth.py`
- `backend/app/core/security.py`
- `backend/app/core/deps.py`

## Security & Architecture Rules
1. **Non-Destructive Test Execution**:
   - Tests MUST NOT drop, reset, or truncate tables in `medismart_db`.
   - Test accounts use unique prefixes (`test_auth_*@example.com`) and are cleaned up in teardown fixtures or run within rolling-back transactions.
2. **Comprehensive Test Matrix**:
   - Password Hashing: verify hash format is `$argon2id$v=19$m=65536,t=2,p=1$...`
   - Login Success: verify access token and Set-Cookie header.
   - Login Failure: verify generic `"Invalid email or password"` for non-existent user and wrong password alike.
   - Token Expiration: verify expired JWT returns 401 Unauthorized.
   - Tampered Token: verify modified signature returns 401 Unauthorized.
   - Role Escalation Prevention: verify public registration attempting `hospital_admin` or `system_admin` returns 403 Forbidden.
   - Duplicate Email: verify second registration attempt returns 409 Conflict.
   - Four-Role Authorization:
     - Patient accessing patient-route -> 200; doctor-route -> 403; admin-route -> 403.
     - Doctor accessing doctor-route -> 200; admin-route -> 403.
     - Hospital Admin accessing admin-route -> 200; patient-route -> 403 (or 200 if permitted).
     - System Admin accessing all protected routes -> 200.

## Tasks

<task type="auto" effort="medium">
  <name>Create backend authentication & authorization test suite</name>
  <files>
    backend/tests/test_auth.py
  </files>
  <action>
    1. Create `backend/tests/test_auth.py`:
       - `test_register_patient_success`: Validates 201 Created and response schema.
       - `test_register_blocks_admin_roles`: Attempting `role="hospital_admin"` or `"system_admin"` returns 403 Forbidden.
       - `test_register_duplicate_email`: Duplicate email returns 409 Conflict with generic safe message.
       - `test_password_is_argon2id`: Verifies stored hash starts with `$argon2id$`.
       - `test_login_success`: Validates token returned and `Set-Cookie` header present with `HttpOnly` and `SameSite=lax`.
       - `test_login_invalid_password`: Returns 401 with generic `"Invalid email or password"`.
       - `test_login_unknown_email`: Returns 401 with identical generic `"Invalid email or password"`.
       - `test_me_with_cookie_auth`: Verifies authentication succeeds via HttpOnly cookie.
       - `test_me_with_bearer_token`: Verifies authentication succeeds via Bearer header.
       - `test_token_expired`: Generates token with expired timestamp; asserts `/me` returns 401 Unauthorized.
       - `test_token_invalid_signature`: Modifies token bytes; asserts `/me` returns 401 Unauthorized.
       - `test_four_role_authorization_matrix`: Verifies RBAC access permissions across all 4 roles.
       - Fixture teardown removes all `test_auth_*` records safely.
  </action>
  <verify>
    .\.venv\Scripts\pytest.exe tests/test_auth.py -v (in backend/)
  </verify>
  <done>
    - All security test cases pass
    - Zero data loss or table truncation
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
    1. Run all backend tests: `.\.venv\Scripts\pytest.exe -v` (expect 20+ tests from Phase 1 and Phase 2 to pass).
    2. Run frontend lint: `npm run lint` (0 errors, 0 warnings).
    3. Run frontend build: `npm run build` (clean production build).
  </action>
  <verify>
    .\.venv\Scripts\pytest.exe -v (in backend/)
    npm run build (in frontend/)
  </verify>
  <done>
    - 100% backend tests pass
    - Frontend build succeeds with zero lint warnings
  </done>
</task>

## Must-Haves
- [ ] Automated tests cover Argon2id, generic 401, duplicate 409, token expiration, and all 4 roles
- [ ] Tests never reset or truncate medismart_db tables
- [ ] Frontend builds cleanly with zero errors
