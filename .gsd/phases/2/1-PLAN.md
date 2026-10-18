---
phase: 2
plan: 1
wave: 1
gap_closure: false
---

# Plan 2.1: Backend Core Auth — Argon2 Password Hashing, JWT Tokens & Auth Endpoints

## Objective
Implement cryptographic password hashing using Argon2, JWT token issuance/verification, Pydantic authentication schemas, and FastAPI authentication endpoints (`/register`, `/login`, `/me`, `/logout`).

## Context
- `backend/app/models/user.py` (User model with UUID PK, email, hashed_password, role, is_active)
- `backend/app/core/config.py` (settings with SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES)
- `backend/app/core/database.py` (AsyncSession dependency `get_db`)

## Tasks

<task type="auto" effort="medium">
  <name>Install Argon2 dependencies and create security utilities</name>
  <files>
    backend/requirements.txt
    backend/app/core/security.py
  </files>
  <action>
    1. Add `argon2-cffi>=23.1.0` and `pyjwt>=2.8.0` to `backend/requirements.txt`.
    2. Install dependencies in `.venv`.
    3. Create `backend/app/core/security.py`:
       - Use `argon2.PasswordHasher(time_cost=2, memory_cost=65536, parallelism=1, hash_len=32, type=argon2.Type.ID)`
       - Implement `get_password_hash(password: str) -> str`
       - Implement `verify_password(plain_password: str, hashed_password: str) -> bool` (with `argon2.exceptions.VerifyMismatchError` handling)
       - Implement `create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str` using PyJWT and `settings.SECRET_KEY`
       - Implement `decode_access_token(token: str) -> Optional[dict]` handling ExpiredSignatureError and InvalidTokenError cleanly.
  </action>
  <verify>
    .\.venv\Scripts\python.exe -c "from app.core.security import get_password_hash, verify_password, create_access_token, decode_access_token; h = get_password_hash('testpass'); assert verify_password('testpass', h); assert not verify_password('wrong', h); t = create_access_token({'sub': 'user123'}); assert decode_access_token(t)['sub'] == 'user123'; print('SECURITY_VERIFIED')"
  </verify>
  <done>
    - Argon2id password hashing verified
    - JWT token generation and decoding verified
  </done>
</task>

<task type="auto" effort="medium">
  <name>Create Pydantic auth schemas and authentication endpoints</name>
  <files>
    backend/app/schemas/auth.py
    backend/app/schemas/__init__.py
    backend/app/api/v1/auth.py
    backend/app/api/v1/__init__.py
  </files>
  <action>
    1. Create `backend/app/schemas/auth.py`:
       - `UserRegisterRequest`: email (EmailStr), password (min 8 chars), full_name (min 2 chars), phone (optional), role (default "patient", validated to in ["patient", "doctor", "hospital_admin", "system_admin"])
       - `UserLoginRequest`: email (EmailStr), password (str)
       - `UserResponse`: id (UUID), email, full_name, phone, role, is_active, created_at
       - `TokenResponse`: access_token, token_type ("bearer"), user (UserResponse)
    2. Create `backend/app/api/v1/auth.py`:
       - `POST /register`: Checks if email already exists via `select(User).where(User.email == request.email)`. If exists, raises `HTTPException(status_code=409, detail="A user with this email already exists")`. Hashes password with Argon2, creates `User`, returns `UserResponse` with 201 Created.
       - `POST /login`: Authenticates user by email and Argon2 hash. If invalid email or password, returns `HTTPException(status_code=401, detail="Incorrect email or password")`. If inactive, returns 403. Generates JWT access token containing `sub` (user.id as string) and `role`. Returns `TokenResponse`.
       - `POST /logout`: Returns `{"message": "Successfully logged out"}`.
    3. Mount `auth.router` on `backend/app/api/v1/__init__.py` with prefix `/auth` and tags `["auth"]`.
  </action>
  <verify>
    .\.venv\Scripts\python.exe -c "from app.api.v1.auth import router; print('AUTH_ROUTER_OK', [route.path for route in router.routes])"
  </verify>
  <done>
    - Auth schemas defined and exported
    - Register and Login endpoints implemented with Argon2 and duplicate email handling
  </done>
</task>

## Must-Haves
- [ ] Argon2 password hashing used for all stored passwords
- [ ] JWT tokens issued with user ID and role
- [ ] Duplicate emails rejected safely with 409 Conflict
- [ ] No database tables dropped or recreated
