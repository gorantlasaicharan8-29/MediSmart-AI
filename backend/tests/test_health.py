import pytest


@pytest.mark.asyncio
async def test_root_endpoint(client):
    """Verify that root endpoint responds with API metadata."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "MediSmart API" in data["message"]
    assert data["docs"] == "/docs"
    assert "version" in data


@pytest.mark.asyncio
async def test_docs_endpoint(client):
    """Verify that Swagger UI documentation is accessible."""
    response = await client.get("/docs")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_api_health_endpoint(client):
    """Verify that /api/v1/health returns ok status."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_api_db_health_endpoint(client):
    """Verify that /api/v1/health/db successfully validates database connectivity."""
    response = await client.get("/api/v1/health/db")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
