# STATE.md — Project Memory

> Last updated: 2026-10-18 14:40 IST

## Current Position

- **Phase**: 2 — Authentication & User Management (COMPLETE ✓)
- **Status**: Verified & Committed
- **Completed Plans in Phase 2**:
  - Plan 2.1: Backend Core Auth — Argon2id Hashing, Secure JWTs, Cookie Auth & Endpoints
  - Plan 2.2: Backend Role-Based Access Control (RBAC) & Administrative Provisioning
  - Plan 2.3: Frontend Auth State, Connected Pages & Protected Routes
  - Plan 2.4: Automated Auth Test Suite & Integration Verification
- **Next Up**: Phase 3 — Hospital Discovery & Interactive Map

## Phase 2 Verification Summary

- **Security & Integrity**:
  - Argon2id password hashing implemented (`argon2-cffi`, `m=65536, t=2, p=1, l=32`).
  - Secure JWTs with 60-minute short TTL, validated claims (`sub`, `role`, `iss`, `iat`, `exp`, `jti`).
  - Fail-safe `SECRET_KEY` validator enforcing `len(SECRET_KEY) >= 32`.
  - Generic `401 Unauthorized` responses on login prevents account enumeration.
  - Safe `409 Conflict` on duplicate email registrations.
  - Public registration strictly blocks self-assignment of `hospital_admin` and `system_admin` with `403 Forbidden`.
  - Administrative provisioning CLI utility: `backend/scripts/create_admin.py`.
  - Dual-transport authentication: HttpOnly `SameSite=Lax` cookies for browser session; Bearer tokens for API/test headers. No long-lived tokens stored in `localStorage`.
- **Database Status**:
  - Reused existing PostgreSQL 18.6 `medismart_db`.
  - Zero tables dropped or reset; all 5 core tables intact.
  - 0 leftover test user accounts.
- **Automated Tests**:
  - 27/27 pytest tests passing in 2.01s (12 Phase 1 tests + 15 Phase 2 tests).
- **Frontend Status**:
  - `oxlint`: 0 errors, 0 warnings across 18 files.
  - Vite production build: clean build in 253ms.

## Context Dump

### Decisions Made
- Decision 13: Use Argon2id instead of bcrypt for password hashing.
- Decision 14: Use HttpOnly, SameSite=Lax cookies with dual-transport fallback to Bearer header.
- Decision 15: Restrict public self-registration to `patient` and `doctor`; provision administrative roles via CLI script or authorized channels.
- Decision 16: Separate React context definition to maintain Fast Refresh without linter warnings.
- Decision 17: Configure pytest-asyncio session loop scope for stable asynchronous PostgreSQL tests on Windows.

### Files of Interest
- `backend/app/core/security.py`: Argon2id and JWT signing/validation.
- `backend/app/core/deps.py`: Dual-transport auth dependencies and `require_roles` RBAC guards.
- `backend/app/api/v1/auth.py`: Register, Login, Logout, /me, and RBAC test routes.
- `backend/scripts/create_admin.py`: Safe CLI administrator provisioning tool.
- `backend/tests/test_auth.py`: Comprehensive 15-test auth suite.
- `frontend/src/context/AuthContext.jsx`: Session management via HttpOnly cookies.
- `frontend/src/components/ProtectedRoute.jsx`: Client-side route protection.

## Next Steps
1. Discuss / Plan Phase 3: Hospital Discovery & Interactive Map.
