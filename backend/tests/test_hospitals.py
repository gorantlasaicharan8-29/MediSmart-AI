import uuid
import pytest
from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models.hospital import Hospital
from app.models.user import User


@pytest.fixture(autouse=True)
async def cleanup_test_hospital_data():
    """Non-destructive fixture: deletes only test-generated hospital and auth records."""
    yield
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Hospital).where(Hospital.name.like("test_hospital_%")))
        await session.execute(delete(User).where(User.email.like("test_hosp_auth_%")))
        await session.commit()


async def get_test_auth_headers(role: str) -> dict:
    """Helper to create a temporary test user and return Authorization header."""
    user_id = uuid.uuid4()
    email = f"test_hosp_auth_{role}_{uuid.uuid4().hex[:6]}@example.com"
    async with AsyncSessionLocal() as session:
        user = User(
            id=user_id,
            email=email,
            hashed_password="$argon2id$v=19$m=65536,t=2,p=1$fakehashfakehashfakehashfakehash",
            full_name=f"Test {role.title()}",
            role=role,
            is_active=True,
        )
        session.add(user)
        await session.commit()

    token = create_access_token(user_id=user_id, role=role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_hospitals_public(client):
    """Verify public access to /api/v1/hospitals without authentication."""
    response = await client.get("/api/v1/hospitals")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    first = data["items"][0]
    assert "id" in first
    assert "name" in first
    assert "city" in first
    assert isinstance(first["specialties"], list)
    assert "has_coordinates" in first
    assert "data_source" in first


@pytest.mark.asyncio
async def test_search_hospitals_by_name(client):
    """Verify search filter matches hospital name case-insensitively."""
    response = await client.get("/api/v1/hospitals?search=AIIMS")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any("AIIMS" in h["name"] for h in data["items"])


@pytest.mark.asyncio
async def test_filter_hospitals_by_city(client):
    """Verify city filter matches city name."""
    response = await client.get("/api/v1/hospitals?city=Hyderabad")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert all(h["city"] == "Hyderabad" for h in data["items"])


@pytest.mark.asyncio
async def test_filter_hospitals_by_specialty(client):
    """Verify PostgreSQL array filtering for clinical specialties."""
    response = await client.get("/api/v1/hospitals?specialty=Oncology")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    for h in data["items"]:
        assert "Oncology" in h["specialties"]


@pytest.mark.asyncio
async def test_filter_hospitals_by_facility(client):
    """Verify PostgreSQL array filtering for facilities."""
    response = await client.get("/api/v1/hospitals?facility=ICU")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    for h in data["items"]:
        assert "ICU" in h["facilities"]


@pytest.mark.asyncio
async def test_missing_coordinates_resilience(client):
    """
    Verify that records with null coordinates return valid JSON with
    has_coordinates=false, and never trigger a 500 error or crash map queries.
    """
    unique_name = f"test_hospital_nocoord_{uuid.uuid4().hex[:6]}"
    admin_headers = await get_test_auth_headers("system_admin")

    # Create hospital with null coordinates
    payload = {
        "name": unique_name,
        "address": "Survey Pending Road",
        "city": "TestCity",
        "state": "TestState",
        "latitude": None,
        "longitude": None,
        "specialties": ["General Medicine"],
        "facilities": ["Outpatient Clinic"],
        "data_source": "sample",
        "source_attribution": "Missing GPS demonstration test",
    }
    create_res = await client.post("/api/v1/hospitals", json=payload, headers=admin_headers)
    assert create_res.status_code == 201
    created_id = create_res.json()["id"]

    # Fetch individual record
    detail_res = await client.get(f"/api/v1/hospitals/{created_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["latitude"] is None
    assert detail["longitude"] is None
    assert detail["has_coordinates"] is False

    # Fetch list with has_coords=false
    nocoords_res = await client.get("/api/v1/hospitals?has_coords=false")
    assert nocoords_res.status_code == 200
    assert any(h["id"] == created_id for h in nocoords_res.json()["items"])


@pytest.mark.asyncio
async def test_has_coords_filter(client):
    """Verify filtering exclusively for mapped facilities."""
    response = await client.get("/api/v1/hospitals?has_coords=true")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    for h in data["items"]:
        assert h["latitude"] is not None
        assert h["longitude"] is not None
        assert h["has_coordinates"] is True


@pytest.mark.asyncio
async def test_geo_proximity_filter(client):
    """Verify Haversine spatial proximity filter around Delhi region."""
    # Delhi approx center: 28.6139, 77.2090
    response = await client.get(
        "/api/v1/hospitals?lat=28.6139&lng=77.2090&radius_km=30"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    # AIIMS and Ganga Ram should be within 30km of Delhi center
    delhi_hospitals = [h["name"] for h in data["items"]]
    assert any("AIIMS" in name or "Ganga Ram" in name for name in delhi_hospitals)


@pytest.mark.asyncio
async def test_get_hospital_by_id_success(client):
    """Verify fetching single hospital by UUID."""
    list_res = await client.get("/api/v1/hospitals?limit=1")
    first_id = list_res.json()["items"][0]["id"]

    res = await client.get(f"/api/v1/hospitals/{first_id}")
    assert res.status_code == 200
    assert res.json()["id"] == first_id


@pytest.mark.asyncio
async def test_get_hospital_by_id_not_found(client):
    """Verify fetching non-existent UUID returns 404."""
    random_id = uuid.uuid4()
    res = await client.get(f"/api/v1/hospitals/{random_id}")
    assert res.status_code == 404
    assert res.json()["detail"] == "Hospital not found"


@pytest.mark.asyncio
async def test_create_hospital_rbac(client):
    """
    Verify RBAC enforcement on POST /api/v1/hospitals:
    - Anonymous -> 401
    - Patient -> 403
    - Doctor -> 403
    - Hospital Admin -> 201 Created
    - System Admin -> 201 Created
    """
    base_payload = {
        "name": f"test_hospital_rbac_{uuid.uuid4().hex[:6]}",
        "address": "123 Healthcare Blvd",
        "city": "Pune",
        "state": "Maharashtra",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "specialties": ["Cardiology"],
        "facilities": ["ICU"],
        "data_source": "verified",
    }

    # 1. Anonymous request
    res_anon = await client.post("/api/v1/hospitals", json=base_payload)
    assert res_anon.status_code == 401

    # 2. Patient request
    patient_headers = await get_test_auth_headers("patient")
    res_patient = await client.post("/api/v1/hospitals", json=base_payload, headers=patient_headers)
    assert res_patient.status_code == 403

    # 3. Doctor request
    doc_headers = await get_test_auth_headers("doctor")
    res_doc = await client.post("/api/v1/hospitals", json=base_payload, headers=doc_headers)
    assert res_doc.status_code == 403

    # 4. Hospital Admin request
    hosp_admin_headers = await get_test_auth_headers("hospital_admin")
    ha_payload = {**base_payload, "name": f"test_hospital_ha_{uuid.uuid4().hex[:6]}"}
    res_ha = await client.post("/api/v1/hospitals", json=ha_payload, headers=hosp_admin_headers)
    assert res_ha.status_code == 201
    assert res_ha.json()["name"] == ha_payload["name"]

    # 5. System Admin request
    sys_admin_headers = await get_test_auth_headers("system_admin")
    sa_payload = {**base_payload, "name": f"test_hospital_sa_{uuid.uuid4().hex[:6]}"}
    res_sa = await client.post("/api/v1/hospitals", json=sa_payload, headers=sys_admin_headers)
    assert res_sa.status_code == 201


@pytest.mark.asyncio
async def test_update_hospital_rbac(client):
    """
    Verify RBAC enforcement on PUT /api/v1/hospitals/{id}:
    - Patient -> 403
    - Hospital Admin -> 200 OK
    """
    sys_admin_headers = await get_test_auth_headers("system_admin")
    create_res = await client.post("/api/v1/hospitals", json={
        "name": f"test_hospital_update_{uuid.uuid4().hex[:6]}",
        "address": "456 Update Ave",
        "city": "Chennai",
        "state": "Tamil Nadu",
        "latitude": 13.0827,
        "longitude": 80.2707,
    }, headers=sys_admin_headers)
    hospital_id = create_res.json()["id"]

    # Patient attempt
    patient_headers = await get_test_auth_headers("patient")
    res_p = await client.put(f"/api/v1/hospitals/{hospital_id}", json={"phone": "+91 999 888 7777"}, headers=patient_headers)
    assert res_p.status_code == 403

    # Hospital Admin attempt
    ha_headers = await get_test_auth_headers("hospital_admin")
    res_ha = await client.put(f"/api/v1/hospitals/{hospital_id}", json={"phone": "+91 999 888 7777"}, headers=ha_headers)
    assert res_ha.status_code == 200
    assert res_ha.json()["phone"] == "+91 999 888 7777"


@pytest.mark.asyncio
async def test_delete_hospital_rbac(client):
    """
    Verify RBAC enforcement on DELETE /api/v1/hospitals/{id}:
    - Patient -> 403
    - Hospital Admin -> 403
    - System Admin -> 200 OK
    """
    sys_admin_headers = await get_test_auth_headers("system_admin")
    create_res = await client.post("/api/v1/hospitals", json={
        "name": f"test_hospital_delete_{uuid.uuid4().hex[:6]}",
        "address": "789 Deletion Blvd",
        "city": "Kolkata",
        "state": "West Bengal",
        "latitude": 22.5726,
        "longitude": 88.3639,
    }, headers=sys_admin_headers)
    hospital_id = create_res.json()["id"]

    # Patient attempt
    patient_headers = await get_test_auth_headers("patient")
    res_p = await client.delete(f"/api/v1/hospitals/{hospital_id}", headers=patient_headers)
    assert res_p.status_code == 403

    # Hospital Admin attempt
    ha_headers = await get_test_auth_headers("hospital_admin")
    res_ha = await client.delete(f"/api/v1/hospitals/{hospital_id}", headers=ha_headers)
    assert res_ha.status_code == 403

    # System Admin attempt
    res_sa = await client.delete(f"/api/v1/hospitals/{hospital_id}", headers=sys_admin_headers)
    assert res_sa.status_code == 200
    assert res_sa.json()["message"] == "Hospital removed successfully"
