---
phase: 2
plan: 2
wave: 1
gap_closure: false
---

# Plan 2.2: Role-Based Access Control (RBAC Middleware & Protected Endpoints)

## Objective
Implement reusable FastAPI dependency guards for user authentication (`get_current_user`, `get_current_active_user`) and role-based authorization (`require_roles(...)`) supporting Patient, Doctor, Hospital Admin, and System Admin roles.

## Context
- `backend/app/core/security.py` (decode_access_token)
- `backend/app/models/user.py` (User model with `role` and `is_active`)
- `backend/app/core/database.py` (get_db AsyncSession)

## Tasks

<task type="auto" effort="medium">
  <name>Implement auth dependencies and role checker guards</name>
  <files>
    backend/app/core/deps.py
    backend/app/api/v1/auth.py
  </files>
  <action>
    1. Create `backend/app/core/deps.py`:
       - Use `fastapi.security.OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")` (or HTTPBearer)
       - Implement `get_current_user(token: str, db: AsyncSession)`:
         - Decodes token via `decode_access_token(token)`
         - Extracts `sub` (user_id UUID)
         - Queries `User` from database
         - Raises 401 Unauthorized with `WWW-Authenticate: Bearer` if token is invalid or user not found.
       - Implement `get_current_active_user(current_user: User)`:
         - Raises 403 Forbidden if not `current_user.is_active`.
       - Implement `RoleChecker` class or dependency factory `require_roles(*allowed_roles: str)`:
         - Compares `current_user.role` against `allowed_roles`
         - If user's role is not in allowed roles, raises `HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden: insufficient role permissions")`.
    2. Add `GET /api/v1/auth/me` endpoint in `auth.py`:
       - Protected by `Depends(get_current_active_user)`
       - Returns `UserResponse` for currently authenticated user.
    3. Add test role-restricted verification endpoints:
       - `GET /api/v1/auth/patient-test` (requires `patient` or `system_admin`)
       - `GET /api/v1/auth/doctor-test` (requires `doctor` or `system_admin`)
       - `GET /api/v1/auth/admin-test` (requires `hospital_admin` or `system_admin`)
  </action>
  <verify>
    .\.venv\Scripts\python.exe -c "from app.core.deps import get_current_user, require_roles; print('RBAC_DEPS_OK')"
  </verify>
  <done>
    - `get_current_user` dependency implemented
    - `require_roles` RBAC enforcement dependency implemented
    - `/auth/me` endpoint returns current user profile
  </done>
</task>

## Must-Haves
- [ ] Backend enforces roles at API route level
- [ ] 401 returned for missing or invalid tokens
- [ ] 403 returned for insufficient role permissions
- [ ] All database queries use existing tables non-destructively
