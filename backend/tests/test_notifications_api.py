import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.notification import Notification
from app.models.user import User


@pytest.fixture
async def test_user_factory():
    """Factory fixture to create test users with bearer auth headers."""
    created_user_ids = []

    async def _create_user(role: str = "patient") -> tuple[User, dict]:
        user_id = uuid.uuid4()
        async with AsyncSessionLocal() as session:
            user = User(
                id=user_id,
                email=f"notif_api_{uuid.uuid4().hex[:8]}@example.com",
                hashed_password=get_password_hash("ValidPass123!"),
                full_name=f"Test Notification User {uuid.uuid4().hex[:4]}",
                role=role,
                is_active=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            created_user_ids.append(user.id)

        token = create_access_token(user_id=user.id, role=user.role)
        headers = {"Authorization": f"Bearer {token}"}
        return user, headers

    yield _create_user

    # Cleanup: cascade deletes all notifications created by these users
    async with AsyncSessionLocal() as session:
        for uid in created_user_ids:
            await session.execute(delete(User).where(User.id == uid))
        await session.commit()


@pytest.fixture
async def create_test_notification():
    """Helper to insert test notifications directly into test DB."""
    async def _create(
        user_id: uuid.UUID,
        title: str = "Test Title",
        message: str = "Test Message",
        category: str = "appointment",
        event_type: str = "appointment_booked",
        urgency: str = "normal",
        is_read: bool = False,
        read_at: datetime = None,
        idempotency_key: str = None,
        metadata_json: dict = None,
    ) -> Notification:
        async with AsyncSessionLocal() as session:
            notif = Notification(
                user_id=user_id,
                title=title,
                message=message,
                category=category,
                event_type=event_type,
                urgency=urgency,
                is_read=is_read,
                read_at=read_at,
                idempotency_key=idempotency_key,
                metadata_json=metadata_json,
            )
            session.add(notif)
            await session.commit()
            await session.refresh(notif)
            return notif

    return _create


# ---------------------------------------------------------------------------
# Route and Schema Exact Path Verification
# ---------------------------------------------------------------------------

def test_exact_notification_route_paths():
    """Confirm the resulting paths are exactly /api/v1/notifications, /read, and /read-all."""
    paths = app.openapi()["paths"]

    assert "/api/v1/notifications" in paths
    assert "get" in paths["/api/v1/notifications"]

    assert "/api/v1/notifications/{notification_id}/read" in paths
    assert "patch" in paths["/api/v1/notifications/{notification_id}/read"]

    assert "/api/v1/notifications/read-all" in paths
    assert "post" in paths["/api/v1/notifications/read-all"]


# ---------------------------------------------------------------------------
# Requirement 1: Unauthenticated Requests are Rejected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthenticated_requests_rejected(client: AsyncClient):
    """Verify all notification endpoints reject unauthenticated requests with 401."""
    random_id = uuid.uuid4()

    # 1. GET /api/v1/notifications
    r1 = await client.get("/api/v1/notifications")
    assert r1.status_code == 401
    assert "detail" in r1.json()

    # 2. PATCH /api/v1/notifications/{id}/read
    r2 = await client.patch(f"/api/v1/notifications/{random_id}/read")
    assert r2.status_code == 401

    # 3. POST /api/v1/notifications/read-all
    r3 = await client.post("/api/v1/notifications/read-all")
    assert r3.status_code == 401


# ---------------------------------------------------------------------------
# Requirement 2: Authenticated Users Can List Their Own Notifications
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_authenticated_user_can_list_own_notifications(
    client: AsyncClient, test_user_factory, create_test_notification
):
    """Verify authenticated user receives their own notifications ordered newest first."""
    user, headers = await test_user_factory()

    # Create 2 notifications
    n1 = await create_test_notification(
        user_id=user.id,
        title="First Notice",
        message="Notice body 1",
    )
    n2 = await create_test_notification(
        user_id=user.id,
        title="Second Notice",
        message="Notice body 2",
    )

    resp = await client.get("/api/v1/notifications", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["total"] == 2
    assert data["unread_count"] == 2
    assert len(data["items"]) == 2

    # Newest first ordering
    retrieved_ids = [item["id"] for item in data["items"]]
    assert str(n2.id) == retrieved_ids[0]
    assert str(n1.id) == retrieved_ids[1]


# ---------------------------------------------------------------------------
# Requirement 3: Multi-tenant Privacy — No Cross-User Leakage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_cannot_retrieve_another_users_notifications(
    client: AsyncClient, test_user_factory, create_test_notification
):
    """Verify User A and User B cannot access each other's notifications."""
    user_a, headers_a = await test_user_factory()
    user_b, headers_b = await test_user_factory()

    await create_test_notification(user_id=user_a.id, title="User A Private Alert")
    await create_test_notification(user_id=user_a.id, title="User A Confidential")
    await create_test_notification(user_id=user_b.id, title="User B Private Record")

    # User A lists
    resp_a = await client.get("/api/v1/notifications", headers=headers_a)
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    assert data_a["total"] == 2
    titles_a = [item["title"] for item in data_a["items"]]
    assert "User B Private Record" not in titles_a

    # User B lists
    resp_b = await client.get("/api/v1/notifications", headers=headers_b)
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    assert data_b["total"] == 1
    assert data_b["items"][0]["title"] == "User B Private Record"


# ---------------------------------------------------------------------------
# Requirement 4: Pagination Works Correctly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pagination_works_correctly(
    client: AsyncClient, test_user_factory, create_test_notification
):
    """Verify limit, offset, and stable ordering across pages."""
    user, headers = await test_user_factory()

    # Create 5 notifications with deterministic sequential timestamps
    created_notifs = []
    for i in range(5):
        notif = await create_test_notification(
            user_id=user.id,
            title=f"Paged Notice #{i + 1}",
        )
        created_notifs.append(notif)

    # Page 1: limit 2, offset 0
    p1 = await client.get("/api/v1/notifications?limit=2&offset=0", headers=headers)
    assert p1.status_code == 200
    d1 = p1.json()
    assert d1["total"] == 5
    assert d1["limit"] == 2
    assert d1["offset"] == 0
    assert len(d1["items"]) == 2
    p1_ids = [item["id"] for item in d1["items"]]

    # Page 2: limit 2, offset 2
    p2 = await client.get("/api/v1/notifications?limit=2&offset=2", headers=headers)
    assert p2.status_code == 200
    d2 = p2.json()
    assert d2["total"] == 5
    assert len(d2["items"]) == 2
    p2_ids = [item["id"] for item in d2["items"]]

    # Page 3: limit 2, offset 4
    p3 = await client.get("/api/v1/notifications?limit=2&offset=4", headers=headers)
    assert p3.status_code == 200
    d3 = p3.json()
    assert d3["total"] == 5
    assert len(d3["items"]) == 1
    p3_ids = [item["id"] for item in d3["items"]]

    # Verify no overlap across pages
    all_seen_ids = p1_ids + p2_ids + p3_ids
    assert len(all_seen_ids) == 5
    assert len(set(all_seen_ids)) == 5

    # Out of bounds offset
    p_empty = await client.get("/api/v1/notifications?limit=2&offset=10", headers=headers)
    assert p_empty.status_code == 200
    d_empty = p_empty.json()
    assert d_empty["total"] == 5
    assert d_empty["items"] == []


# ---------------------------------------------------------------------------
# Requirement 5: Filtering by is_read Works
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_filtering_by_is_read_works(
    client: AsyncClient, test_user_factory, create_test_notification
):
    """Verify is_read=true and is_read=false filters."""
    user, headers = await test_user_factory()

    # 2 unread, 1 read
    await create_test_notification(user_id=user.id, title="Unread 1", is_read=False)
    await create_test_notification(user_id=user.id, title="Unread 2", is_read=False)
    await create_test_notification(
        user_id=user.id,
        title="Already Read",
        is_read=True,
        read_at=datetime.now(timezone.utc),
    )

    # Filter unread
    r_unread = await client.get("/api/v1/notifications?is_read=false", headers=headers)
    assert r_unread.status_code == 200
    d_unread = r_unread.json()
    assert d_unread["total"] == 2
    assert d_unread["unread_count"] == 2
    assert all(item["is_read"] is False for item in d_unread["items"])

    # Filter read
    r_read = await client.get("/api/v1/notifications?is_read=true", headers=headers)
    assert r_read.status_code == 200
    d_read = r_read.json()
    assert d_read["total"] == 1
    assert d_read["unread_count"] == 2  # Total unread for user remains 2
    assert d_read["items"][0]["is_read"] is True

    # No filter: all 3
    r_all = await client.get("/api/v1/notifications", headers=headers)
    assert r_all.status_code == 200
    assert r_all.json()["total"] == 3


# ---------------------------------------------------------------------------
# Requirement 6: User Can Mark Their Own Notification as Read
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_can_mark_own_notification_as_read(
    client: AsyncClient, test_user_factory, create_test_notification
):
    """Verify PATCH marks notification as read and sets timezone-aware read_at."""
    user, headers = await test_user_factory()

    notif = await create_test_notification(
        user_id=user.id,
        title="Check-in Alert",
        is_read=False,
    )
    assert notif.is_read is False
    assert notif.read_at is None

    resp = await client.patch(
        f"/api/v1/notifications/{notif.id}/read",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["id"] == str(notif.id)
    assert data["is_read"] is True
    assert data["read_at"] is not None

    # Verify persisted in database
    async with AsyncSessionLocal() as session:
        db_notif = (
            await session.execute(
                select(Notification).where(Notification.id == notif.id)
            )
        ).scalar_one()
        assert db_notif.is_read is True
        assert db_notif.read_at is not None


# ---------------------------------------------------------------------------
# Requirement 7: Repeated Mark-as-Read Requests are Safe and Idempotent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_repeated_mark_as_read_requests_are_safe_and_idempotent(
    client: AsyncClient, test_user_factory, create_test_notification
):
    """Verify calling read endpoint multiple times does not error or change original read_at."""
    user, headers = await test_user_factory()

    notif = await create_test_notification(user_id=user.id, title="Idempotent Check")

    # First call
    r1 = await client.patch(f"/api/v1/notifications/{notif.id}/read", headers=headers)
    assert r1.status_code == 200
    first_read_at = r1.json()["read_at"]
    assert first_read_at is not None

    # Second call
    r2 = await client.patch(f"/api/v1/notifications/{notif.id}/read", headers=headers)
    assert r2.status_code == 200
    second_read_at = r2.json()["read_at"]

    # Idempotent: timestamp should not be overwritten
    assert first_read_at == second_read_at


# ---------------------------------------------------------------------------
# Requirement 8: Anti-IDOR — Another User Cannot Mark Someone Else's Notification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_another_user_cannot_mark_someone_elses_notification_as_read(
    client: AsyncClient, test_user_factory, create_test_notification
):
    """Verify 404 is returned when attempting to mark another user's notification as read."""
    user_a, headers_a = await test_user_factory()
    user_b, headers_b = await test_user_factory()

    notif_a = await create_test_notification(
        user_id=user_a.id,
        title="User A Secret Alert",
        is_read=False,
    )

    # User B tries to mark User A's notification as read
    resp = await client.patch(
        f"/api/v1/notifications/{notif_a.id}/read",
        headers=headers_b,
    )
    # Must return 404 to avoid leaking existence of user A's notification
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Notification not found"

    # Verify User A's notification in database remains unread
    async with AsyncSessionLocal() as session:
        db_notif = (
            await session.execute(
                select(Notification).where(Notification.id == notif_a.id)
            )
        ).scalar_one()
        assert db_notif.is_read is False
        assert db_notif.read_at is None


# ---------------------------------------------------------------------------
# Requirement 9: Mark-All-Read Affects Only Current User's Unread Notifications
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_all_read_affects_only_current_users_unread_notifications(
    client: AsyncClient, test_user_factory, create_test_notification
):
    """Verify POST /read-all mutates only authenticated user's unread records."""
    user_a, headers_a = await test_user_factory()
    user_b, headers_b = await test_user_factory()

    # User A: 2 unread, 1 already read
    a_old_read_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    na1 = await create_test_notification(user_id=user_a.id, title="A unread 1")
    na2 = await create_test_notification(user_id=user_a.id, title="A unread 2")
    na3 = await create_test_notification(
        user_id=user_a.id,
        title="A already read",
        is_read=True,
        read_at=a_old_read_at,
    )

    # User B: 2 unread
    nb1 = await create_test_notification(user_id=user_b.id, title="B unread 1")
    nb2 = await create_test_notification(user_id=user_b.id, title="B unread 2")

    # User A executes mark-all-read
    resp = await client.post("/api/v1/notifications/read-all", headers=headers_a)
    assert resp.status_code == 200
    data = resp.json()
    assert data["updated_count"] == 2

    # Verify User A's previously read notification was untouched
    async with AsyncSessionLocal() as session:
        reloaded_na3 = (
            await session.execute(
                select(Notification).where(Notification.id == na3.id)
            )
        ).scalar_one()
        assert reloaded_na3.read_at == a_old_read_at

        # Verify User B's notifications remain unread
        reloaded_nb1 = (
            await session.execute(
                select(Notification).where(Notification.id == nb1.id)
            )
        ).scalar_one()
        reloaded_nb2 = (
            await session.execute(
                select(Notification).where(Notification.id == nb2.id)
            )
        ).scalar_one()
        assert reloaded_nb1.is_read is False
        assert reloaded_nb2.is_read is False


# ---------------------------------------------------------------------------
# Requirement 10: Empty Notification Lists and Zero Read Handled Correctly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_notification_lists_handled_correctly(
    client: AsyncClient, test_user_factory
):
    """Verify clean response when user has 0 notifications."""
    user, headers = await test_user_factory()

    # List empty
    r_list = await client.get("/api/v1/notifications", headers=headers)
    assert r_list.status_code == 200
    d_list = r_list.json()
    assert d_list["items"] == []
    assert d_list["total"] == 0
    assert d_list["unread_count"] == 0

    # Mark all read with 0 unread
    r_read_all = await client.post("/api/v1/notifications/read-all", headers=headers)
    assert r_read_all.status_code == 200
    assert r_read_all.json()["updated_count"] == 0


# ---------------------------------------------------------------------------
# Requirement 11: Invalid UUIDs and Invalid Pagination Values Handled Correctly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_uuids_and_pagination_values_handled_correctly(
    client: AsyncClient, test_user_factory
):
    """Verify validation errors (422) for bad UUIDs and out-of-range pagination."""
    user, headers = await test_user_factory()

    # Invalid UUID in path
    r_bad_uuid = await client.patch(
        "/api/v1/notifications/invalid-not-a-uuid/read",
        headers=headers,
    )
    assert r_bad_uuid.status_code == 422

    # Negative limit
    r_neg_lim = await client.get("/api/v1/notifications?limit=-1", headers=headers)
    assert r_neg_lim.status_code == 422

    # Zero limit (minimum is 1)
    r_zero_lim = await client.get("/api/v1/notifications?limit=0", headers=headers)
    assert r_zero_lim.status_code == 422

    # Limit exceeding max (100)
    r_over_lim = await client.get("/api/v1/notifications?limit=101", headers=headers)
    assert r_over_lim.status_code == 422

    # Negative offset
    r_neg_off = await client.get("/api/v1/notifications?offset=-1", headers=headers)
    assert r_neg_off.status_code == 422


# ---------------------------------------------------------------------------
# Requirement 12: Response Schemas Do Not Leak Sensitive Metadata
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_response_schemas_do_not_leak_sensitive_metadata(
    client: AsyncClient, test_user_factory, create_test_notification
):
    """Verify sensitive auth/clinical keys and idempotency_key are never returned in responses."""
    user, headers = await test_user_factory()

    sensitive_meta = {
        "appointment_id": str(uuid.uuid4()),
        "token": "secret_jwt_access_token_12345",
        "password": "plaintext_password_leak",
        "clinical_notes": "Patient diagnosed with confidential medical condition.",
        "doctor_notes": "Prescribed strong narcotic sedative.",
        "patient_notes": "Patient reports severe anxiety.",
        "safe_field": "public_reference_value",
    }

    notif = await create_test_notification(
        user_id=user.id,
        title="Privacy Test Notice",
        message="Notice content",
        idempotency_key="internal_dedup_key_98765",
        metadata_json=sensitive_meta,
    )

    # 1. Check GET response
    resp = await client.get("/api/v1/notifications", headers=headers)
    assert resp.status_code == 200
    item = resp.json()["items"][0]

    # Internal database fields omitted from schema
    assert "idempotency_key" not in item
    assert "updated_at" not in item

    # Sanitized metadata
    meta = item["metadata_json"]
    assert "token" not in meta
    assert "password" not in meta
    assert "clinical_notes" not in meta
    assert "doctor_notes" not in meta
    assert "patient_notes" not in meta
    assert meta["safe_field"] == "public_reference_value"
    assert "appointment_id" in meta

    # 2. Check PATCH read response
    patch_resp = await client.patch(
        f"/api/v1/notifications/{notif.id}/read",
        headers=headers,
    )
    assert patch_resp.status_code == 200
    patch_item = patch_resp.json()
    assert "idempotency_key" not in patch_item
    patch_meta = patch_item["metadata_json"]
    assert "clinical_notes" not in patch_meta
    assert "token" not in patch_meta
    assert patch_meta["safe_field"] == "public_reference_value"
