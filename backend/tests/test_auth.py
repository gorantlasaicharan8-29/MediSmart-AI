import uuid
from datetime import timedelta
import pytest
from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, verify_password
from app.models.user import User


@pytest.fixture(autouse=True)
async def cleanup_test_users():
    """Ensure any test accounts created during test execution are cleanly deleted without touching real data."""
    yield
    async with AsyncSessionLocal() as session:
        await session.execute(delete(User).where(User.email.like("test_auth_%")))
        await session.commit()


@pytest.mark.asyncio
async def test_register_patient_success(client):
    """Verify standard public user registration for Patient role."""
    unique_email = f"test_auth_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": unique_email,
        "password": "SecurePassword123!",
        "full_name": "Test Patient",
        "phone": "+15551234567",
        "role": "patient",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == unique_email
    assert data["full_name"] == "Test Patient"
    assert data["role"] == "patient"
    assert data["is_active"] is True
    assert "id" in data
    # Ensure sensitive credentials are never returned in response
    assert "hashed_password" not in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_register_doctor_success(client):
    """Verify standard public user registration for Doctor role."""
    unique_email = f"test_auth_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": unique_email,
        "password": "DocPassword123!",
        "full_name": "Dr. Test Physician",
        "role": "doctor",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "doctor"


@pytest.mark.asyncio
async def test_register_blocks_admin_roles(client):
    """Security check: Verify public registration strictly blocks self-assignment of administrative roles."""
    admin_roles = ["hospital_admin", "system_admin"]
    for role in admin_roles:
        unique_email = f"test_auth_{uuid.uuid4().hex[:8]}@example.com"
        payload = {
            "email": unique_email,
            "password": "AdminPassword123!",
            "full_name": "Attempted Admin",
            "role": role,
        }
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 403
        data = response.json()
        assert "Administrative roles cannot be self-assigned" in data["detail"]


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    """Verify duplicate email registration returns safe 409 Conflict."""
    unique_email = f"test_auth_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": unique_email,
        "password": "Password123!",
        "full_name": "First User",
        "role": "patient",
    }
    # Initial registration
    res1 = await client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    # Duplicate registration attempt
    res2 = await client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409
    data = res2.json()
    assert "already exists" in data["detail"]


@pytest.mark.asyncio
async def test_password_is_argon2id(client):
    """Verify password hashing algorithm is strictly Argon2id in medismart_db."""
    unique_email = f"test_auth_{uuid.uuid4().hex[:8]}@example.com"
    password = "TestPassword456!"
    payload = {
        "email": unique_email,
        "password": password,
        "full_name": "Argon2 Test User",
        "role": "patient",
    }
    res = await client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201

    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.email == unique_email)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.hashed_password.startswith("$argon2id$")
        assert verify_password(password, user.hashed_password) is True
        assert verify_password("WrongPassword!", user.hashed_password) is False


@pytest.mark.asyncio
async def test_login_success_and_cookie(client):
    """Verify successful login returns valid JWT token and sets HttpOnly cookie."""
    unique_email = f"test_auth_{uuid.uuid4().hex[:8]}@example.com"
    password = "LoginPass789!"
    await client.post("/api/v1/auth/register", json={
        "email": unique_email,
        "password": password,
        "full_name": "Login User",
        "role": "patient",
    })

    login_res = await client.post("/api/v1/auth/login", json={
        "email": unique_email,
        "password": password,
    })
    assert login_res.status_code == 200
    data = login_res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in_minutes"] == 60
    assert data["user"]["email"] == unique_email

    # Check Set-Cookie header
    cookie_header = login_res.headers.get("set-cookie")
    assert cookie_header is not None
    assert "access_token=" in cookie_header
    assert "HttpOnly" in cookie_header or "httponly" in cookie_header.lower()
    assert "samesite=lax" in cookie_header.lower()


@pytest.mark.asyncio
async def test_login_invalid_password(client):
    """Security check: verify wrong password returns generic 401 without account leakage."""
    unique_email = f"test_auth_{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/api/v1/auth/register", json={
        "email": unique_email,
        "password": "CorrectPassword123!",
        "full_name": "Generic Error Test",
        "role": "patient",
    })

    res = await client.post("/api/v1/auth/login", json={
        "email": unique_email,
        "password": "WrongPassword999!",
    })
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_login_unknown_email(client):
    """Security check: verify unknown email returns identical generic 401 (prevents user enumeration)."""
    res = await client.post("/api/v1/auth/login", json={
        "email": f"test_auth_nonexistent_{uuid.uuid4().hex[:6]}@example.com",
        "password": "SomePassword123!",
    })
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_me_with_cookie_auth(client):
    """Verify /me profile endpoint authenticates via HttpOnly cookie."""
    unique_email = f"test_auth_{uuid.uuid4().hex[:8]}@example.com"
    password = "AuthCookiePassword!"
    await client.post("/api/v1/auth/register", json={
        "email": unique_email,
        "password": password,
        "full_name": "Cookie User",
        "role": "patient",
    })

    login_res = await client.post("/api/v1/auth/login", json={
        "email": unique_email,
        "password": password,
    })
    token = login_res.json()["access_token"]

    # Call /me passing cookie
    me_res = await client.get("/api/v1/auth/me", cookies={"access_token": token})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == unique_email


@pytest.mark.asyncio
async def test_me_with_bearer_token(client):
    """Verify /me profile endpoint authenticates via Authorization: Bearer header."""
    unique_email = f"test_auth_{uuid.uuid4().hex[:8]}@example.com"
    password = "AuthBearerPassword!"
    await client.post("/api/v1/auth/register", json={
        "email": unique_email,
        "password": password,
        "full_name": "Bearer User",
        "role": "doctor",
    })

    login_res = await client.post("/api/v1/auth/login", json={
        "email": unique_email,
        "password": password,
    })
    token = login_res.json()["access_token"]

    # Call /me passing Bearer header
    me_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["email"] == unique_email
    assert me_res.json()["role"] == "doctor"


@pytest.mark.asyncio
async def test_me_unauthenticated(client):
    """Verify /me returns 401 when no token or cookie is supplied."""
    me_res = await client.get("/api/v1/auth/me")
    assert me_res.status_code == 401


@pytest.mark.asyncio
async def test_token_expired(client):
    """Verify expired JWT token returns 401 Unauthorized."""
    user_id = uuid.uuid4()
    expired_token = create_access_token(
        user_id=user_id,
        role="patient",
        expires_delta=timedelta(minutes=-10),
    )
    me_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert me_res.status_code == 401


@pytest.mark.asyncio
async def test_token_invalid_signature(client):
    """Verify tampered JWT token returns 401 Unauthorized."""
    user_id = uuid.uuid4()
    valid_token = create_access_token(user_id=user_id, role="patient")
    tampered_token = valid_token[:-6] + "xxxxxx"

    me_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tampered_token}"},
    )
    assert me_res.status_code == 401


@pytest.mark.asyncio
async def test_logout_clears_cookie(client):
    """Verify /logout clears the access_token cookie."""
    logout_res = await client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 200
    assert logout_res.json()["message"] == "Session terminated successfully"

    cookie_header = logout_res.headers.get("set-cookie")
    assert cookie_header is not None
    # Max-Age=0 or expires indicates deletion
    assert "max-age=0" in cookie_header.lower() or "expires=" in cookie_header.lower()


@pytest.mark.asyncio
async def test_four_role_authorization_matrix(client):
    """
    Verify RBAC enforcement across all four roles:
    - patient: can access /patient-test, forbidden on /doctor-test & /admin-test
    - doctor: can access /doctor-test, forbidden on /admin-test
    - hospital_admin: can access /admin-test, forbidden on /doctor-test
    - system_admin: can access all (/patient-test, /doctor-test, /admin-test)
    """
    roles_and_credentials = [
        ("patient", "Test Patient RBAC"),
        ("doctor", "Test Doctor RBAC"),
        ("hospital_admin", "Test Hospital Admin RBAC"),
        ("system_admin", "Test System Admin RBAC"),
    ]

    tokens = {}

    # Seed users directly in DB to allow administrative roles without public registration
    async with AsyncSessionLocal() as session:
        for role, name in roles_and_credentials:
            email = f"test_auth_{role}_{uuid.uuid4().hex[:6]}@example.com"
            user = User(
                email=email,
                hashed_password="$argon2id$v=19$m=65536,t=2,p=1$fakehashfakehashfakehashfakehash",
                full_name=name,
                role=role,
                is_active=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            tokens[role] = create_access_token(user_id=user.id, role=role)

    # 1. Patient access checks
    p_headers = {"Authorization": f"Bearer {tokens['patient']}"}
    assert (await client.get("/api/v1/auth/patient-test", headers=p_headers)).status_code == 200
    assert (await client.get("/api/v1/auth/doctor-test", headers=p_headers)).status_code == 403
    assert (await client.get("/api/v1/auth/admin-test", headers=p_headers)).status_code == 403

    # 2. Doctor access checks
    d_headers = {"Authorization": f"Bearer {tokens['doctor']}"}
    assert (await client.get("/api/v1/auth/doctor-test", headers=d_headers)).status_code == 200
    assert (await client.get("/api/v1/auth/admin-test", headers=d_headers)).status_code == 403

    # 3. Hospital Admin access checks
    ha_headers = {"Authorization": f"Bearer {tokens['hospital_admin']}"}
    assert (await client.get("/api/v1/auth/admin-test", headers=ha_headers)).status_code == 200
    assert (await client.get("/api/v1/auth/doctor-test", headers=ha_headers)).status_code == 403

    # 4. System Admin access checks (unrestricted oversight)
    sa_headers = {"Authorization": f"Bearer {tokens['system_admin']}"}
    assert (await client.get("/api/v1/auth/patient-test", headers=sa_headers)).status_code == 200
    assert (await client.get("/api/v1/auth/doctor-test", headers=sa_headers)).status_code == 200
    assert (await client.get("/api/v1/auth/admin-test", headers=sa_headers)).status_code == 200
