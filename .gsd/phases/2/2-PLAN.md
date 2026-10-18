---
phase: 2
plan: 2
wave: 1
gap_closure: false
---

# Plan 2.2: Backend Role-Based Access Control (RBAC) & Administrative Provisioning

## Objective
Implement backend-enforced authentication dependencies supporting dual transport (HttpOnly cookies + Bearer headers), strict claims validation, role-based access control guards (`require_roles(...)`) covering all 4 roles, and an administrative provisioning mechanism for privileged roles.

## Context
- `backend/app/core/security.py` (Argon2id & decode_access_token)
- `backend/app/models/user.py` (User model)
- `backend/app/core/database.py` (get_db AsyncSession)

## Security & Architecture Rules
1. **Dual Transport Token Extraction**:
   - Extract JWT token first from `request.cookies.get("access_token")`.
   - Fallback to standard `Authorization: Bearer <token>` header if cookie not present.
   - Enables secure browser cookie auth while supporting mobile/CLI/docs API access.
2. **Backend-Enforced Authorization**:
   - Every protected route uses FastAPI dependency injection:
     ```python
     @router.get("/doctor-only", dependencies=[Depends(require_roles("doctor", "system_admin"))])
     ```
   - Returns `401 Unauthorized` for missing, expired, or tampered tokens.
   - Returns `403 Forbidden` for insufficient role permissions.
3. **Controlled Administrative Provisioning**:
   - To satisfy security requirement 5 (no public self-assignment of admin roles), implement an administrative provisioning CLI script `backend/scripts/create_admin.py` and a protected provisioning endpoint `POST /api/v1/auth/provision-user` (restricted to `system_admin`).

## Tasks

<task type="auto" effort="medium">
  <name>Implement dual-transport auth dependency and RBAC role guards</name>
  <files>
    backend/app/core/deps.py
    backend/app/api/v1/auth.py
    backend/scripts/create_admin.py
  </files>
  <action>
    1. Create `backend/app/core/deps.py`:
       - Implement `get_token_from_request(request: Request) -> Optional[str]`: Checks `request.cookies.get("access_token")`, then `request.headers.get("Authorization")` with `Bearer ` prefix.
       - Implement `get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User`:
         - Validates token with `decode_access_token`.
         - Ensures `iss == settings.JWT_ISSUER` and extracts `sub` (UUID).
         - Queries user from `medismart_db`.
         - If user not found, raises 401 Unauthorized.
       - Implement `get_current_active_user(user: User = Depends(get_current_user)) -> User`:
         - Raises 403 Forbidden if not `user.is_active`.
       - Implement `require_roles(*allowed_roles: str)`:
         - Dependency callable that checks `current_user.role in allowed_roles`.
         - Raises `HTTPException(status_code=403, detail="Access forbidden: insufficient role permissions")` on mismatch.
    2. Add endpoints to `backend/app/api/v1/auth.py`:
       - `GET /me`: Returns `UserResponse` for `get_current_active_user`.
       - `GET /patient-test`: Restricted to `["patient", "system_admin"]`.
       - `GET /doctor-test`: Restricted to `["doctor", "system_admin"]`.
       - `GET /admin-test`: Restricted to `["hospital_admin", "system_admin"]`.
    3. Create safe CLI script `backend/scripts/create_admin.py`:
       - Non-interactive / argument-based utility to bootstrap a verified `system_admin` or `hospital_admin` directly in PostgreSQL using Argon2id without exposing public registration endpoints.
  </action>
  <verify>
    .\.venv\Scripts\python.exe -c "from app.core.deps import get_current_user, require_roles; print('RBAC_AND_DEPS_OK')"
  </verify>
  <done>
    - Dual transport token extraction operational (Cookie + Header)
    - RBAC dependency enforcing 4-role hierarchy
    - Controlled admin provisioning script created
  </done>
</task>

## Must-Haves
- [ ] Role authorization enforced strictly on backend
- [ ] Missing/invalid token returns 401 Unauthorized
- [ ] Mismatched role returns 403 Forbidden
- [ ] Safe admin provisioning mechanism without public self-assignment
