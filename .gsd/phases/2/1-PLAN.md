---
phase: 2
plan: 1
wave: 1
gap_closure: false
---

# Plan 2.1: Backend Core Auth — Argon2id Hashing, Secure JWTs, Cookie Auth & Endpoints

## Objective
Implement Argon2id password hashing, securely signed and validated JWT tokens (with short TTL, claims validation, and fail-safe secret checks), HttpOnly cookie + Bearer dual-transport authentication, input validation, safe generic error responses, and restricted public registration.

## Context
- `backend/app/models/user.py` (User model in PostgreSQL 18.6 medismart_db)
- `backend/app/core/config.py` (Settings with SECRET_KEY)
- `backend/app/core/database.py` (AsyncSession `get_db`)

## Security & Architecture Rules
1. **Argon2id Hashing**: Use `argon2-cffi` configured with `argon2.Type.ID`, `time_cost=2`, `memory_cost=65536` (64 MB), `parallelism=1`, `hash_len=32`.
2. **Secure JWT Tokens**:
   - Short expiration: `ACCESS_TOKEN_EXPIRE_MINUTES = 60` (prevents long-lived token exposure).
   - Validated claims: `sub` (User UUID), `role`, `iat`, `exp`, `jti` (unique UUID), `iss` ("medismart").
   - Explicitly validate signature, expiration, and issuer on decode.
3. **Secret Key Safety**:
   - Loaded exclusively from `backend/.env`.
   - Fail safely: on application startup or token creation, raise a configuration error if `SECRET_KEY` is missing or less than 32 characters in length. Never log the key value.
4. **Controlled Registration & Role Provisioning**:
   - Public self-registration (`POST /api/v1/auth/register`) only permits `patient` and `doctor` roles (`patient` by default).
   - Any registration attempt requesting `hospital_admin` or `system_admin` is rejected with `403 Forbidden` ("Administrative roles cannot be self-assigned. Contact your system administrator.").
   - System admins are provisioned via administrative CLI script or protected admin endpoint.
5. **Generic Error Responses**:
   - Login failures return a generic `"Invalid email or password"` (`401 Unauthorized`) regardless of whether the email exists or password is wrong, preventing account enumeration.
   - Duplicate email registration returns `409 Conflict` with `"An account with this email address already exists"`.
6. **Dual-Transport Auth & Accurate Logout**:
   - Login sets `access_token` in a `HttpOnly`, `SameSite=Lax`, `Secure` (in production / disabled on localhost HTTP) cookie, and also returns token in JSON body for API consumers.
   - Logout clears the `access_token` cookie with `max_age=0` and returns `"Session terminated successfully"`. Accurately documents that stateless tokens expire naturally after short TTL (60 min).

## Tasks

<task type="auto" effort="medium">
  <name>Install dependencies and create security engine with Argon2id and fail-safe JWTs</name>
  <files>
    backend/requirements.txt
    backend/app/core/config.py
    backend/app/core/security.py
  </files>
  <action>
    1. Update `backend/requirements.txt`:
       - Ensure `argon2-cffi>=23.1.0` and `pyjwt>=2.8.0` are listed.
    2. Update `backend/app/core/config.py`:
       - Add `ACCESS_TOKEN_EXPIRE_MINUTES: int = 60` (shortened TTL).
       - Add `JWT_ISSUER: str = "medismart"`.
       - Add validation in `Settings`: ensure `SECRET_KEY` is at least 32 characters long.
    3. Create `backend/app/core/security.py`:
       - Configure `argon2.PasswordHasher(type=argon2.Type.ID, time_cost=2, memory_cost=65536, parallelism=1, hash_len=32)`.
       - Implement `get_password_hash(password: str) -> str`.
       - Implement `verify_password(plain_password: str, hashed_password: str) -> bool`.
       - Implement `create_access_token(user_id: UUID, role: str, expires_delta: Optional[timedelta] = None) -> str`.
       - Implement `decode_access_token(token: str) -> Optional[dict]` validating signature, `iss`, and `exp`.
  </action>
  <verify>
    .\.venv\Scripts\python.exe -c "from app.core.security import get_password_hash, verify_password, create_access_token, decode_access_token; import uuid; uid = uuid.uuid4(); h = get_password_hash('SecretP@ss123'); assert h.startswith('$argon2id$'); assert verify_password('SecretP@ss123', h); assert not verify_password('WrongPass', h); t = create_access_token(uid, 'patient'); claims = decode_access_token(t); assert claims['sub'] == str(uid) and claims['role'] == 'patient'; print('ARGON2ID_AND_JWT_OK')"
  </verify>
  <done>
    - Argon2id password hashing implemented and verified
    - JWT creation with validated claims (iss, exp, jti, sub, role) and decode verification
    - Fail-safe SECRET_KEY validation in place
  </done>
</task>

<task type="auto" effort="medium">
  <name>Create schemas and auth endpoints with role restriction and cookie handling</name>
  <files>
    backend/app/schemas/auth.py
    backend/app/schemas/__init__.py
    backend/app/api/v1/auth.py
    backend/app/api/v1/__init__.py
  </files>
  <action>
    1. Create `backend/app/schemas/auth.py`:
       - `UserRegisterRequest`: email (EmailStr), password (str, min_length=8), full_name (str, min_length=2), phone (Optional[str]), role (str = "patient"). Role validator rejects `hospital_admin` and `system_admin`.
       - `UserLoginRequest`: email (EmailStr), password (str).
       - `UserResponse`: id (UUID), email, full_name, phone, role, is_active, created_at.
       - `TokenResponse`: access_token, token_type ("bearer"), expires_in_minutes (60), user (UserResponse).
    2. Create `backend/app/api/v1/auth.py`:
       - `POST /register`: Rejects self-assignment of `hospital_admin` or `system_admin` with 403. Checks duplicate email with 409 Conflict. Hashes password with Argon2id. Creates user. Returns 201 Created with `UserResponse`.
       - `POST /login`: Accepts `UserLoginRequest` and `Response`. Authenticates against Argon2id hash. If invalid email or password mismatch, raises `HTTPException(status_code=401, detail="Invalid email or password")`. If inactive, raises 403. Issues JWT token. Sets `access_token` in `HttpOnly`, `SameSite=Lax` cookie and returns `TokenResponse`.
       - `POST /logout`: Accepts `Response`. Clears `access_token` cookie. Returns `{"message": "Session terminated successfully"}`.
    3. Register auth router in `backend/app/api/v1/__init__.py`.
  </action>
  <verify>
    .\.venv\Scripts\python.exe -c "from app.api.v1.auth import router; print('ROUTES:', [r.path for r in router.routes])"
  </verify>
  <done>
    - Pydantic schemas validate inputs cleanly
    - Public self-assignment of administrative roles blocked
    - Generic 401 error message for failed login
    - Duplicate emails handled with safe 409
    - HttpOnly cookie set on login and cleared on logout
  </done>
</task>

## Must-Haves
- [ ] Argon2id used exclusively for password hashing
- [ ] Public registration blocks hospital_admin and system_admin self-assignment
- [ ] Generic authentication error message on failed login (no user enumeration)
- [ ] Safe 409 Conflict response on duplicate email registration
- [ ] HttpOnly cookies set with SameSite=Lax and short token expiration (60 min)
