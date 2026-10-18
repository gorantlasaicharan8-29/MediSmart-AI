# Plan 2.2: Backend Role-Based Access Control (RBAC) & Administrative Provisioning — Summary

## Accomplishments
- Implemented `backend/app/core/deps.py`:
  - `get_token_from_request`: Dual-transport token extraction (first checking HttpOnly `access_token` cookie, falling back to `Authorization: Bearer <token>` header).
  - `get_current_user`: Validates token signature, expiration, and issuer; queries user by UUID from PostgreSQL `medismart_db`; raises `401 Unauthorized` on missing, expired, or tampered credentials.
  - `get_current_active_user`: Verifies account status, raising `403 Forbidden` if suspended or inactive.
  - `require_roles(*allowed_roles)`: Dependency factory enforcing role authorization across all 4 roles (`patient`, `doctor`, `hospital_admin`, `system_admin`), raising `403 Forbidden` on role mismatch.
- Extended `backend/app/api/v1/auth.py` with authenticated and RBAC endpoints:
  - `GET /api/v1/auth/me`: Returns authenticated profile (`UserResponse`).
  - `GET /api/v1/auth/patient-test`: Restricted to `["patient", "system_admin"]`.
  - `GET /api/v1/auth/doctor-test`: Restricted to `["doctor", "system_admin"]`.
  - `GET /api/v1/auth/admin-test`: Restricted to `["hospital_admin", "system_admin"]`.
- Built administrative CLI provisioning tool `backend/scripts/create_admin.py`:
  - Non-interactive / CLI script allowing controlled provisioning of `system_admin` or `hospital_admin` accounts directly into PostgreSQL.
  - Protects passwords with Argon2id hashing and prevents credential exposure.
- Verified all routes and dependencies via Python CLI and verified 12/12 existing tests pass.

## Commits
- Pending commit for Plan 2.2.
