from unittest.mock import AsyncMock
import pytest
from httpx import ASGITransport, AsyncClient

import app.core.database as db_mod
from app.core.config import Settings, settings
from app.main import app, create_app, lifespan


def test_engine_resilience_configuration():
    """Verify SQLAlchemy async engine is configured with pool_pre_ping and pool_recycle."""
    assert db_mod.engine is not None
    # Verify pool_pre_ping is active (detects stale TCP connections on checkout)
    assert getattr(db_mod.engine.pool, "_pre_ping", None) is True
    # Verify pool_recycle is 1800s (recycles connections every 30 minutes)
    assert getattr(db_mod.engine.pool, "_recycle", None) == 1800


@pytest.mark.asyncio
async def test_lifespan_disposes_engine_on_shutdown(monkeypatch):
    """Verify application shutdown gracefully disposes of the database engine."""
    mock_engine = AsyncMock()
    monkeypatch.setattr(db_mod, "engine", mock_engine)

    async with app.router.lifespan_context(app):
        # Application is running in lifespan
        assert not mock_engine.dispose.called

    # After exiting lifespan context (shutdown)
    mock_engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_lifespan_handles_none_engine_gracefully(monkeypatch):
    """Verify lifespan shutdown handles missing/uninitialized engine without raising errors."""
    monkeypatch.setattr(db_mod, "engine", None)

    async with app.router.lifespan_context(app):
        pass  # Startup and shutdown must succeed cleanly without raising AttributeError


@pytest.mark.asyncio
async def test_create_app_factory_includes_lifespan(monkeypatch):
    """Verify application factory attaches lifespan context to custom settings instances."""
    custom_cfg = Settings(
        ENVIRONMENT="testing",
        DATABASE_URL=settings.DATABASE_URL,
    )
    custom_app = create_app(custom_cfg)
    assert custom_app.router.lifespan_context is not None

    mock_engine = AsyncMock()
    monkeypatch.setattr(db_mod, "engine", mock_engine)

    async with custom_app.router.lifespan_context(custom_app):
        assert not mock_engine.dispose.called

    mock_engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_health_and_database_endpoints_healthy(client):
    """Verify that /api/v1/health and /api/v1/health/db remain healthy with resilient engine."""
    # 1. Health endpoint
    h_res = await client.get("/api/v1/health")
    assert h_res.status_code == 200
    assert h_res.json()["status"] == "ok"

    # 2. Database health connectivity check
    db_res = await client.get("/api/v1/health/db")
    assert db_res.status_code == 200
    assert db_res.json()["status"] == "ok"
    assert db_res.json()["database"] == "connected"
