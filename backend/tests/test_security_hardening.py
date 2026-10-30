import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import KNOWN_DEV_SECRETS, Settings, settings
from app.main import create_app


def test_default_development_configuration():
    """Verify that the default settings reflect safe local development defaults."""
    assert settings.ENVIRONMENT == "development"
    assert settings.COOKIE_SECURE is False
    assert settings.DOCS_ENABLED is True
    assert settings.SECRET_KEY is not None
    assert len(settings.SECRET_KEY) >= 32


def test_production_rejects_default_development_secret():
    """Verify production startup fails if SECRET_KEY uses the known development fallback."""
    with pytest.raises(ValueError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY=list(KNOWN_DEV_SECRETS)[0],
        )
    err = str(exc_info.value)
    assert "cannot use the known development fallback" in err
    # Verify no secret leakage in error output
    assert list(KNOWN_DEV_SECRETS)[0] not in err


def test_production_rejects_weak_or_short_secret():
    """Verify production rejects secrets shorter than 32 characters."""
    with pytest.raises(ValueError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="short-secret",
        )
    assert "at least 32 characters" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="   ",
        )
    assert "at least 32 characters" in str(exc_info.value)


def test_production_accepts_strong_secret_and_auto_resolves_attributes():
    """Verify valid production settings enable cookie security and disable public docs by default."""
    strong_secret = "c" * 64
    prod_cfg = Settings(
        ENVIRONMENT="production",
        SECRET_KEY=strong_secret,
        DATABASE_URL=settings.DATABASE_URL,
    )
    assert prod_cfg.ENVIRONMENT == "production"
    assert prod_cfg.COOKIE_SECURE is True
    assert prod_cfg.DOCS_ENABLED is False


def test_production_rejects_insecure_cookie_override():
    """Verify production rejects attempts to disable COOKIE_SECURE."""
    strong_secret = "d" * 64
    with pytest.raises(ValueError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY=strong_secret,
            COOKIE_SECURE=False,
            DATABASE_URL=settings.DATABASE_URL,
        )
    assert "COOKIE_SECURE cannot be False in production" in str(exc_info.value)


def test_production_allows_explicit_docs_override():
    """Verify operators can intentionally re-enable API documentation in production if desired."""
    strong_secret = "e" * 64
    prod_cfg = Settings(
        ENVIRONMENT="production",
        SECRET_KEY=strong_secret,
        DOCS_ENABLED=True,
        DATABASE_URL=settings.DATABASE_URL,
    )
    assert prod_cfg.DOCS_ENABLED is True


@pytest.mark.asyncio
async def test_cookie_secure_attribute_in_development(client):
    """Verify that in development mode, cookies are HttpOnly and SameSite=Lax without Secure flag."""
    unique_email = f"test_dev_cookie_{uuid.uuid4().hex[:8]}@example.com"
    password = "DevPassword123!"

    reg_res = await client.post("/api/v1/auth/register", json={
        "email": unique_email,
        "password": password,
        "full_name": "Dev Cookie User",
        "role": "patient",
    })
    assert reg_res.status_code == 201

    login_res = await client.post("/api/v1/auth/login", json={
        "email": unique_email,
        "password": password,
    })
    assert login_res.status_code == 200

    cookie_header = login_res.headers.get("set-cookie", "")
    assert "access_token=" in cookie_header
    assert "httponly" in cookie_header.lower()
    assert "samesite=lax" in cookie_header.lower()
    # In development (COOKIE_SECURE=False), 'secure' attribute must not be present
    assert "secure" not in cookie_header.lower()


@pytest.mark.asyncio
async def test_cookie_secure_attribute_in_production(client, monkeypatch):
    """Verify that when COOKIE_SECURE is True, login and logout cookies enforce the Secure flag."""
    monkeypatch.setattr(settings, "COOKIE_SECURE", True)

    unique_email = f"test_prod_cookie_{uuid.uuid4().hex[:8]}@example.com"
    password = "ProdPassword123!"

    # Create account first via test client
    reg_res = await client.post("/api/v1/auth/register", json={
        "email": unique_email,
        "password": password,
        "full_name": "Prod Cookie User",
        "role": "patient",
    })
    assert reg_res.status_code == 201

    login_res = await client.post("/api/v1/auth/login", json={
        "email": unique_email,
        "password": password,
    })
    assert login_res.status_code == 200

    login_cookie = login_res.headers.get("set-cookie", "")
    assert "access_token=" in login_cookie
    assert "httponly" in login_cookie.lower()
    assert "samesite=lax" in login_cookie.lower()
    assert "secure" in login_cookie.lower()

    # Logout test
    logout_res = await client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 200
    logout_cookie = logout_res.headers.get("set-cookie", "")
    assert "secure" in logout_cookie.lower()


@pytest.mark.asyncio
async def test_api_documentation_availability_dev_vs_prod():
    """Verify /docs, /redoc, and /openapi.json are available in dev and disabled in production."""
    # Development App
    dev_settings = Settings(
        ENVIRONMENT="development",
        DATABASE_URL=settings.DATABASE_URL,
    )
    dev_app = create_app(dev_settings)
    async with AsyncClient(transport=ASGITransport(app=dev_app), base_url="http://test") as dev_client:
        root_res = await dev_client.get("/")
        assert root_res.status_code == 200
        assert root_res.json()["docs"] == "/docs"

        docs_res = await dev_client.get("/docs")
        assert docs_res.status_code == 200

        redoc_res = await dev_client.get("/redoc")
        assert redoc_res.status_code == 200

        openapi_res = await dev_client.get("/openapi.json")
        assert openapi_res.status_code == 200

    # Production App
    prod_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="g" * 64,
        DATABASE_URL=settings.DATABASE_URL,
    )
    prod_app = create_app(prod_settings)
    async with AsyncClient(transport=ASGITransport(app=prod_app), base_url="http://test") as prod_client:
        root_res = await prod_client.get("/")
        assert root_res.status_code == 200
        assert root_res.json()["docs"] is None

        docs_res = await prod_client.get("/docs")
        assert docs_res.status_code == 404

        redoc_res = await prod_client.get("/redoc")
        assert redoc_res.status_code == 404

        openapi_res = await prod_client.get("/openapi.json")
        assert openapi_res.status_code == 404
