import asyncio
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocketDisconnect, status
from sqlalchemy import text

from app.core.config import Settings
from app.core.database import AsyncSessionLocal
from app.core.websocket import (
    InMemoryBroadcastBackend,
    QueueConnectionManager,
    RedisBroadcastBackend,
    UserNotificationConnectionManager,
    user_ws_manager,
    queue_ws_manager,
    authenticate_websocket,
)
from app.models.notification import Notification
from app.models.user import User
from app.services.notification import notification_service


class MockWebSocket:
    """Mock WebSocket for simulating WebSocket client interactions."""

    def __init__(self, cookies=None, headers=None):
        self.accepted = False
        self.closed = False
        self.close_code = None
        self.sent_messages = []
        self.raise_on_send = None
        self.cookies = cookies or {}
        self.headers = headers or {}
        self._receive_queue = asyncio.Queue()

    async def accept(self):
        self.accepted = True

    async def send_json(self, data: dict):
        if self.raise_on_send:
            raise self.raise_on_send
        self.sent_messages.append(data)

    async def close(self, code=1000):
        self.closed = True
        self.close_code = code

    async def receive_text(self):
        return await self._receive_queue.get()

    async def deliver_client_message(self, text_msg: str):
        await self._receive_queue.put(text_msg)


# ---------------------------------------------------------------------------
# 1. Authentication & Rejection Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthenticated_websocket_is_rejected():
    """Verify WebSocket handshake fails with 1008 Policy Violation when no credentials are provided."""
    from app.api.v1.notifications import notification_websocket_endpoint

    unauth_ws = MockWebSocket()
    await notification_websocket_endpoint(unauth_ws)

    assert unauth_ws.closed is True
    assert unauth_ws.close_code == status.WS_1008_POLICY_VIOLATION
    assert unauth_ws.accepted is False


@pytest.mark.asyncio
async def test_websocket_rejects_unauthorized_origin():
    """Verify WebSocket rejects connections from unauthorized origins."""
    ws = MockWebSocket(headers={"origin": "http://malicious-site.com"})
    with patch("app.core.websocket.settings.CORS_ORIGINS", ["http://localhost:5173"]):
        user = await authenticate_websocket(ws)
        assert user is None


# ---------------------------------------------------------------------------
# 2. Scoped Delivery & Cross-User Isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_authenticated_user_receives_scoped_events_and_cross_isolation():
    """
    Verify:
    1. Authenticated user receives notification events intended for that user.
    2. Other users never receive events intended for another user (cross-user isolation).
    """
    mgr = UserNotificationConnectionManager(backend=InMemoryBroadcastBackend())
    await mgr.start()

    user_a_id = str(uuid.uuid4())
    user_b_id = str(uuid.uuid4())

    ws_a1 = MockWebSocket()
    ws_a2 = MockWebSocket()
    ws_b = MockWebSocket()

    await mgr.connect(user_a_id, ws_a1)
    await mgr.connect(user_a_id, ws_a2)
    await mgr.connect(user_b_id, ws_b)

    event_payload = {
        "event": "NOTIFICATION_CREATED",
        "notification": {
            "id": str(uuid.uuid4()),
            "category": "appointment",
            "event_type": "appointment_booked",
            "title": "Appointment Confirmed",
            "urgency": "normal",
            "is_read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    # Broadcast event intended specifically for User A
    await mgr.broadcast_to_user(user_a_id, event_payload)

    # User A sockets received the event
    assert len(ws_a1.sent_messages) == 1
    assert ws_a1.sent_messages[0] == event_payload
    assert len(ws_a2.sent_messages) == 1
    assert ws_a2.sent_messages[0] == event_payload

    # User B socket received NOTHING
    assert len(ws_b.sent_messages) == 0

    await mgr.stop()


# ---------------------------------------------------------------------------
# 3. Client Broadcast Prevention & Ping/Pong Keepalive
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clients_cannot_publish_arbitrary_events_to_other_users():
    """
    Verify client incoming text is handled for ping/pong keepalive only and
    clients cannot publish arbitrary notification events to other users.
    """
    from app.api.v1.notifications import notification_websocket_endpoint

    mock_user = MagicMock(spec=User)
    mock_user.id = uuid.uuid4()
    mock_user.is_active = True

    client_ws = MockWebSocket()

    # Pre-load client messages: a malicious broadcast attempt followed by a ping keepalive
    await client_ws.deliver_client_message(
        json.dumps({"event": "NOTIFICATION_CREATED", "target_user": "all", "title": "Spoofed"})
    )
    await client_ws.deliver_client_message(json.dumps({"type": "ping"}))

    # Run endpoint in background task and cancel after message processing
    with patch("app.api.v1.notifications.authenticate_websocket", AsyncMock(return_value=mock_user)):
        task = asyncio.create_task(notification_websocket_endpoint(client_ws))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # Malicious broadcast was discarded; ping received pong reply
    assert client_ws.accepted is True
    assert len(client_ws.sent_messages) == 1
    assert client_ws.sent_messages[0] == {"type": "pong"}


# ---------------------------------------------------------------------------
# 4. Disconnect Handling & Dead Socket Pruning
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_disconnect_removes_cleanly_and_unsubscribes_backend():
    """Verify user disconnect unregisters sockets and triggers backend unsubscription when last leaves."""
    backend_mock = MagicMock(spec=InMemoryBroadcastBackend)
    backend_mock.start = AsyncMock()
    backend_mock.stop = AsyncMock()
    backend_mock.publish = AsyncMock()
    backend_mock.subscribe_channel = AsyncMock()
    backend_mock.unsubscribe_channel = AsyncMock()

    mgr = UserNotificationConnectionManager(backend=backend_mock)
    await mgr.start()

    user_id = str(uuid.uuid4())
    ws1 = MockWebSocket()
    ws2 = MockWebSocket()

    # First client connects: triggers subscription to user:{user_id}
    await mgr.connect(user_id, ws1)
    backend_mock.subscribe_channel.assert_awaited_once_with(f"user:{user_id}")

    # Second client connects: no redundant subscription
    await mgr.connect(user_id, ws2)
    assert backend_mock.subscribe_channel.await_count == 1

    # First client disconnects: user still has ws2 active
    mgr.disconnect(user_id, ws1)
    assert user_id in mgr.active_users
    assert backend_mock.unsubscribe_channel.await_count == 0

    # Second client disconnects: active_users is now empty, triggers backend unsubscription
    mgr.disconnect(user_id, ws2)
    await asyncio.sleep(0.01)
    assert user_id not in mgr.active_users
    backend_mock.unsubscribe_channel.assert_awaited_once_with(f"user:{user_id}")

    await mgr.stop()


@pytest.mark.asyncio
async def test_dead_user_socket_pruning_on_broadcast():
    """Verify dead/broken sockets are pruned cleanly during broadcast without halting other sockets."""
    mgr = UserNotificationConnectionManager(backend=InMemoryBroadcastBackend())
    await mgr.start()

    user_id = str(uuid.uuid4())
    healthy_ws = MockWebSocket()
    broken_ws = MockWebSocket()
    broken_ws.raise_on_send = WebSocketDisconnect(code=1006)

    await mgr.connect(user_id, healthy_ws)
    await mgr.connect(user_id, broken_ws)
    assert len(mgr.active_users[user_id]) == 2

    event = {"event": "NOTIFICATION_CREATED", "title": "Check In"}
    await mgr.broadcast_to_user(user_id, event)

    assert len(healthy_ws.sent_messages) == 1
    assert len(mgr.active_users[user_id]) == 1
    assert broken_ws not in mgr.active_users[user_id]

    await mgr.stop()


# ---------------------------------------------------------------------------
# 5. Doctor Queue Broadcast Compatibility
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_doctor_queue_broadcast_remains_independent_and_compatible():
    """Verify public doctor queue broadcasts continue operating without cross-contaminating user channels."""
    queue_mgr = QueueConnectionManager(backend=InMemoryBroadcastBackend())
    user_mgr = UserNotificationConnectionManager(backend=InMemoryBroadcastBackend())

    await queue_mgr.start()
    await user_mgr.start()

    doc_ws = MockWebSocket()
    user_ws = MockWebSocket()

    doc_id = "doc-alpha"
    user_id = str(uuid.uuid4())

    await queue_mgr.connect(doc_id, doc_ws)
    await user_mgr.connect(user_id, user_ws)

    queue_event = {"event": "QUEUE_UPDATED", "action": "CALLED", "token_display": "A-01"}
    await queue_mgr.broadcast_to_doctor(doc_id, queue_event)

    # Doctor received queue broadcast; user received nothing
    assert len(doc_ws.sent_messages) == 1
    assert doc_ws.sent_messages[0] == queue_event
    assert len(user_ws.sent_messages) == 0

    await queue_mgr.stop()
    await user_mgr.stop()


# ---------------------------------------------------------------------------
# 6. Zero-PII Payload Verification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_private_notification_payload_contains_no_prohibited_clinical_data():
    """Verify WebSocket notification payloads contain zero clinical notes, diagnoses, or sensitive tokens."""
    ws = MockWebSocket()
    test_user_id = uuid.uuid4()
    await user_ws_manager.connect(str(test_user_id), ws)

    async with AsyncSessionLocal() as session:
        # Create user for DB foreign key
        new_user = User(
            id=test_user_id,
            email=f"pii_test_{uuid.uuid4().hex[:6]}@medismart.ai",
            hashed_password="hashed_pw_dummy",
            full_name="Confidential Patient",
            role="patient",
            is_active=True,
        )
        session.add(new_user)
        await session.commit()

        # Create notification with private metadata
        res = await notification_service.create_notification(
            db=session,
            user_id=test_user_id,
            category="appointment",
            event_type="appointment_booked",
            title="Appointment Confirmed",
            message="Your appointment is scheduled.",
            urgency="normal",
            idempotency_key=f"pii_check_{uuid.uuid4().hex[:8]}",
            metadata_json={
                "notes": "Patient has severe cardiovascular condition",
                "clinical_notes": "Prescription details attached",
                "token": "secret_jwt_token",
            },
            auto_commit=False,
        )
        assert res.created is True

        # Commit transaction to trigger after_commit hook
        await session.commit()

    # Allow event loop task to deliver message
    await asyncio.sleep(0.05)

    assert len(ws.sent_messages) == 1
    payload = ws.sent_messages[0]

    assert payload["event"] == "NOTIFICATION_CREATED"
    notif_data = payload["notification"]

    # Verify permitted fields
    assert notif_data["title"] == "Appointment Confirmed"
    assert notif_data["category"] == "appointment"
    assert notif_data["urgency"] == "normal"
    assert notif_data["is_read"] is False

    # Verify complete absence of sensitive keys
    msg_str = json.dumps(payload).lower()
    assert "cardiovascular" not in msg_str
    assert "prescription" not in msg_str
    assert "secret_jwt_token" not in msg_str
    assert "clinical_notes" not in msg_str
    assert "notes" not in notif_data

    user_ws_manager.disconnect(str(test_user_id), ws)


# ---------------------------------------------------------------------------
# 7. Post-Commit Transaction Delivery & Rollback Safety
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notification_event_emitted_only_after_commit_and_never_on_rollback():
    """
    Verify:
    1. Events are not emitted before transaction commit.
    2. Successful commit emits the event to WebSocket.
    3. Transaction rollback discards staged events with zero phantom emission.
    """
    test_user_id = uuid.uuid4()
    ws = MockWebSocket()
    await user_ws_manager.connect(str(test_user_id), ws)

    async with AsyncSessionLocal() as session:
        # Create user
        new_user = User(
            id=test_user_id,
            email=f"tx_test_{uuid.uuid4().hex[:6]}@medismart.ai",
            hashed_password="hashed_pw_dummy",
            full_name="Transaction Test Patient",
            role="patient",
            is_active=True,
        )
        session.add(new_user)
        await session.commit()

    # Part A: Rollback Test
    async with AsyncSessionLocal() as session:
        await notification_service.create_notification(
            db=session,
            user_id=test_user_id,
            category="queue",
            event_type="queue_checked_in",
            title="Checked In (Will Rollback)",
            message="Temporary token",
            auto_commit=False,
        )
        # Rollback the transaction
        await session.rollback()

    await asyncio.sleep(0.05)
    # Zero phantom events emitted on rollback
    assert len(ws.sent_messages) == 0

    # Part B: Commit Test
    async with AsyncSessionLocal() as session:
        await notification_service.create_notification(
            db=session,
            user_id=test_user_id,
            category="queue",
            event_type="queue_checked_in",
            title="Checked In (Will Commit)",
            message="Confirmed token",
            auto_commit=False,
        )
        # Verify not yet dispatched before commit
        assert len(ws.sent_messages) == 0

        # Now commit
        await session.commit()

    await asyncio.sleep(0.05)
    # Event emitted strictly after commit
    assert len(ws.sent_messages) == 1
    assert ws.sent_messages[0]["notification"]["title"] == "Checked In (Will Commit)"

    user_ws_manager.disconnect(str(test_user_id), ws)


@pytest.mark.asyncio
async def test_inner_savepoint_rollback_preserves_outer_staged_events():
    """
    Verify that rolling back an inner nested savepoint (begin_nested) does NOT
    discard notification events staged for the surrounding outer transaction.
    When the outer transaction subsequently commits, the notification is delivered.
    """
    test_user_id = uuid.uuid4()
    ws = MockWebSocket()
    await user_ws_manager.connect(str(test_user_id), ws)

    async with AsyncSessionLocal() as session:
        # Create user
        new_user = User(
            id=test_user_id,
            email=f"sp_keep_{uuid.uuid4().hex[:6]}@medismart.ai",
            hashed_password="hashed_pw_dummy",
            full_name="Savepoint Preservation Patient",
            role="patient",
            is_active=True,
        )
        session.add(new_user)
        await session.commit()

    async with AsyncSessionLocal() as session:
        # 1. Stage outer notification
        res = await notification_service.create_notification(
            db=session,
            user_id=test_user_id,
            category="appointment",
            event_type="appointment_booked",
            title="Booked Outer Notification",
            message="Confirmed slot",
            auto_commit=False,
        )
        assert res.created is True

        # 2. Execute an inner nested savepoint that rolls back
        try:
            async with session.begin_nested():
                # Perform inner work that trips an error and rolls back the savepoint
                await session.execute(text("SELECT 1"))
                raise RuntimeError("Simulated inner savepoint failure")
        except RuntimeError:
            pass  # Inner savepoint rolled back cleanly; outer transaction remains active

        # Verify not yet dispatched while outer transaction is open
        assert len(ws.sent_messages) == 0

        # 3. Outer transaction commits successfully
        await session.commit()

    await asyncio.sleep(0.05)
    # The outer notification event was preserved and delivered on root commit
    assert len(ws.sent_messages) == 1
    assert ws.sent_messages[0]["notification"]["title"] == "Booked Outer Notification"

    user_ws_manager.disconnect(str(test_user_id), ws)


@pytest.mark.asyncio
async def test_inner_savepoint_rollback_with_outer_rollback_emits_nothing():
    """
    Verify that if an inner savepoint rolls back AND the outer transaction subsequently
    rolls back, all staged events are discarded with zero phantom emission.
    """
    test_user_id = uuid.uuid4()
    ws = MockWebSocket()
    await user_ws_manager.connect(str(test_user_id), ws)

    async with AsyncSessionLocal() as session:
        new_user = User(
            id=test_user_id,
            email=f"sp_rb_{uuid.uuid4().hex[:6]}@medismart.ai",
            hashed_password="hashed_pw_dummy",
            full_name="Savepoint Rollback Patient",
            role="patient",
            is_active=True,
        )
        session.add(new_user)
        await session.commit()

    async with AsyncSessionLocal() as session:
        # 1. Stage notification
        await notification_service.create_notification(
            db=session,
            user_id=test_user_id,
            category="queue",
            event_type="queue_checked_in",
            title="Cancelled Queue Checkin",
            message="Temporary token",
            auto_commit=False,
        )

        # 2. Inner savepoint rolls back
        try:
            async with session.begin_nested():
                raise ValueError("Inner failure")
        except ValueError:
            pass

        # 3. Outer transaction rolls back
        await session.rollback()

    await asyncio.sleep(0.05)
    # Zero phantom events emitted
    assert len(ws.sent_messages) == 0

    user_ws_manager.disconnect(str(test_user_id), ws)


@pytest.mark.asyncio
async def test_inner_savepoint_commit_does_not_prematurely_dispatch():
    """
    Verify that an inner savepoint commit (release) does NOT prematurely dispatch
    staged notification events before the outer transaction commits.
    """
    test_user_id = uuid.uuid4()
    ws = MockWebSocket()
    await user_ws_manager.connect(str(test_user_id), ws)

    async with AsyncSessionLocal() as session:
        new_user = User(
            id=test_user_id,
            email=f"sp_prem_{uuid.uuid4().hex[:6]}@medismart.ai",
            hashed_password="hashed_pw_dummy",
            full_name="Premature Check Patient",
            role="patient",
            is_active=True,
        )
        session.add(new_user)
        await session.commit()

    async with AsyncSessionLocal() as session:
        # 1. Stage notification
        await notification_service.create_notification(
            db=session,
            user_id=test_user_id,
            category="system",
            event_type="general",
            title="System Alert",
            message="System update",
            auto_commit=False,
        )

        # 2. Inner savepoint commits successfully
        async with session.begin_nested():
            await session.execute(text("SELECT 1"))

        # Verify: inner savepoint commit did NOT trigger dispatch prematurely
        assert len(ws.sent_messages) == 0

        # 3. Outer transaction commits
        await session.commit()

    await asyncio.sleep(0.05)
    # Delivered strictly after outer transaction commits
    assert len(ws.sent_messages) == 1
    assert ws.sent_messages[0]["notification"]["title"] == "System Alert"

    user_ws_manager.disconnect(str(test_user_id), ws)


@pytest.mark.asyncio
async def test_session_reuse_across_multiple_transactions():
    """
    Verify that reusing the same AsyncSession instance across multiple distinct
    transactions maintains clean isolation:
    - Tx 1 commits: dispatches event 1.
    - Tx 2 commits with no notifications: dispatches nothing.
    - Tx 3 rolls back: dispatches nothing.
    - Tx 4 commits: dispatches event 4.
    """
    test_user_id = uuid.uuid4()
    ws = MockWebSocket()
    await user_ws_manager.connect(str(test_user_id), ws)

    async with AsyncSessionLocal() as session:
        new_user = User(
            id=test_user_id,
            email=f"reuse_{uuid.uuid4().hex[:6]}@medismart.ai",
            hashed_password="hashed_pw_dummy",
            full_name="Session Reuse Patient",
            role="patient",
            is_active=True,
        )
        session.add(new_user)
        await session.commit()

        # Tx 1: Stage and commit
        await notification_service.create_notification(
            db=session,
            user_id=test_user_id,
            category="appointment",
            event_type="appointment_booked",
            title="Tx 1 Booked",
            message="Confirmed",
            auto_commit=False,
        )
        await session.commit()
        await asyncio.sleep(0.05)
        assert len(ws.sent_messages) == 1
        assert ws.sent_messages[-1]["notification"]["title"] == "Tx 1 Booked"

        # Tx 2: Normal DB query and commit, NO notification staged
        await session.execute(text("SELECT 1"))
        await session.commit()
        await asyncio.sleep(0.05)
        assert len(ws.sent_messages) == 1  # No duplicate or phantom

        # Tx 3: Stage notification, then rollback
        await notification_service.create_notification(
            db=session,
            user_id=test_user_id,
            category="queue",
            event_type="queue_checked_in",
            title="Tx 3 Aborted",
            message="Aborted token",
            auto_commit=False,
        )
        await session.rollback()
        await asyncio.sleep(0.05)
        assert len(ws.sent_messages) == 1  # Still 1 (Tx 3 discarded)

        # Tx 4: Stage new notification and commit
        await notification_service.create_notification(
            db=session,
            user_id=test_user_id,
            category="appointment",
            event_type="appointment_cancelled",
            title="Tx 4 Cancelled",
            message="Cancelled",
            auto_commit=False,
        )
        await session.commit()
        await asyncio.sleep(0.05)
        assert len(ws.sent_messages) == 2
        assert ws.sent_messages[-1]["notification"]["title"] == "Tx 4 Cancelled"

    user_ws_manager.disconnect(str(test_user_id), ws)


# ---------------------------------------------------------------------------
# 8. Idempotency & Duplicate Event Suppression
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_duplicate_processing_does_not_emit_duplicate_ws_events():
    """Verify that repeated calls with the same idempotency_key suppress duplicate WebSocket emissions."""
    test_user_id = uuid.uuid4()
    ws = MockWebSocket()
    await user_ws_manager.connect(str(test_user_id), ws)

    async with AsyncSessionLocal() as session:
        new_user = User(
            id=test_user_id,
            email=f"idemp_{uuid.uuid4().hex[:6]}@medismart.ai",
            hashed_password="hashed_pw_dummy",
            full_name="Idempotency Patient",
            role="patient",
            is_active=True,
        )
        session.add(new_user)
        await session.commit()

    shared_idemp_key = f"token_repeat_{uuid.uuid4().hex[:8]}"

    # First attempt: succeeds and commits
    async with AsyncSessionLocal() as session:
        res1 = await notification_service.create_notification(
            db=session,
            user_id=test_user_id,
            category="appointment",
            event_type="appointment_booked",
            title="Initial Booking",
            message="Confirmed",
            idempotency_key=shared_idemp_key,
            auto_commit=False,
        )
        assert res1.created is True
        await session.commit()

    await asyncio.sleep(0.05)
    assert len(ws.sent_messages) == 1

    # Second attempt: duplicate collision suppressed
    async with AsyncSessionLocal() as session:
        res2 = await notification_service.create_notification(
            db=session,
            user_id=test_user_id,
            category="appointment",
            event_type="appointment_booked",
            title="Repeated Booking Attempt",
            message="Confirmed",
            idempotency_key=shared_idemp_key,
            auto_commit=False,
        )
        assert res2.is_duplicate is True
        assert res2.created is False
        await session.commit()

    await asyncio.sleep(0.05)
    # Message count remains strictly 1 (no duplicate push event emitted)
    assert len(ws.sent_messages) == 1

    user_ws_manager.disconnect(str(test_user_id), ws)


# ---------------------------------------------------------------------------
# 9. Redis Multi-Worker Scoped Routing & Deduplication
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_redis_multi_worker_scoped_user_routing_and_deduplication():
    """
    Simulate two backend worker instances connected to mock Redis pub/sub.
    Verifies:
    1. Event broadcast for User A on Worker 1 reaches User A on Worker 2.
    2. Local delivery to User A on Worker 1 happens immediately.
    3. User A on Worker 1 receives message exactly once (origin echo discarded).
    4. User B on Worker 2 receives 0 messages (scoped channel user:{user_id}).
    """
    broker_subscribers = []

    class MockPubSub:
        def __init__(self, owner_backend):
            self.owner = owner_backend
            self.queue = asyncio.Queue()
            broker_subscribers.append(self)

        async def subscribe(self, channel):
            pass

        async def unsubscribe(self, channel):
            pass

        async def close(self):
            if self in broker_subscribers:
                broker_subscribers.remove(self)

        async def get_message(self, ignore_subscribe_messages=True, timeout=1.0):
            try:
                return await asyncio.wait_for(self.queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                return None

    def create_mock_redis(backend_instance):
        mock = AsyncMock()
        mock.ping = AsyncMock(return_value=True)
        mock.pubsub = MagicMock(return_value=MockPubSub(backend_instance))
        mock.aclose = AsyncMock()

        async def mock_publish(channel, message_str):
            for sub in list(broker_subscribers):
                await sub.queue.put({"type": "message", "channel": channel, "data": message_str})

        mock.publish = AsyncMock(side_effect=mock_publish)
        return mock

    backend_w1 = RedisBroadcastBackend("redis://simulated:6379/0")
    backend_w2 = RedisBroadcastBackend("redis://simulated:6379/0")

    mock_r1 = create_mock_redis(backend_w1)
    mock_r2 = create_mock_redis(backend_w2)

    with patch("redis.asyncio.from_url", side_effect=[mock_r1, mock_r2]):
        mgr_w1 = UserNotificationConnectionManager(backend=backend_w1)
        mgr_w2 = UserNotificationConnectionManager(backend=backend_w2)

        await mgr_w1.start()
        await mgr_w2.start()

        user_a_id = str(uuid.uuid4())
        user_b_id = str(uuid.uuid4())

        ws_user_a_w1 = MockWebSocket()
        ws_user_a_w2 = MockWebSocket()
        ws_user_b_w2 = MockWebSocket()

        await mgr_w1.connect(user_a_id, ws_user_a_w1)
        await mgr_w2.connect(user_a_id, ws_user_a_w2)
        await mgr_w2.connect(user_b_id, ws_user_b_w2)

        event = {
            "event": "NOTIFICATION_CREATED",
            "notification": {
                "id": str(uuid.uuid4()),
                "category": "queue",
                "title": "Your Turn Called",
            },
        }

        # Worker 1 broadcasts event for User A
        await mgr_w1.broadcast_to_user(user_a_id, event)

        await asyncio.sleep(0.15)

        # 1. User A on Worker 1 received message locally
        assert len(ws_user_a_w1.sent_messages) == 1
        assert ws_user_a_w1.sent_messages[0] == event

        # 2. User A on Worker 2 received message across workers via Redis
        assert len(ws_user_a_w2.sent_messages) == 1
        assert ws_user_a_w2.sent_messages[0] == event

        # 3. Deduplication: User A on Worker 1 received it once (not twice)
        assert len(ws_user_a_w1.sent_messages) == 1

        # 4. Isolation: User B on Worker 2 received nothing
        assert len(ws_user_b_w2.sent_messages) == 0

        await mgr_w1.stop()
        await mgr_w2.stop()


# ---------------------------------------------------------------------------
# 10. REST Polling Fallback Robustness
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rest_polling_fallback_operates_when_websocket_is_offline(client):
    """
    Verify that REST endpoints continue to serve authoritative notification data
    and unread counts even when WebSocket delivery is completely unavailable.
    """
    test_user_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        new_user = User(
            id=test_user_id,
            email=f"rest_poll_{uuid.uuid4().hex[:6]}@medismart.ai",
            hashed_password="hashed_pw_dummy",
            full_name="Polling Patient",
            role="patient",
            is_active=True,
        )
        session.add(new_user)
        await session.commit()

        # Seed 2 unread notifications
        n1 = Notification(
            user_id=test_user_id,
            category="system",
            event_type="general",
            title="Poll Alert 1",
            message="System notice",
            urgency="normal",
            is_read=False,
        )
        n2 = Notification(
            user_id=test_user_id,
            category="appointment",
            event_type="appointment_booked",
            title="Poll Alert 2",
            message="Appointment confirmed",
            urgency="normal",
            is_read=False,
        )
        session.add_all([n1, n2])
        await session.commit()

    # Query REST API via client with mocked current user (simulating 30s background poll)
    from app.core.deps import get_current_active_user
    app_instance = client._transport.app

    async def mock_get_user():
        return new_user

    app_instance.dependency_overrides[get_current_active_user] = mock_get_user
    try:
        response = await client.get("/api/v1/notifications?limit=1")
        assert response.status_code == 200
        data = response.json()
        assert data["unread_count"] == 2
        assert data["total"] == 2
        assert len(data["items"]) == 1
    finally:
        app_instance.dependency_overrides.pop(get_current_active_user, None)

