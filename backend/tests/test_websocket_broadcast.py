import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import WebSocketDisconnect

from app.core.config import Settings, settings
from app.core.websocket import (
    InMemoryBroadcastBackend,
    QueueConnectionManager,
    RedisBroadcastBackend,
)


class MockWebSocket:
    """Mock WebSocket for simulating client connections."""

    def __init__(self):
        self.accepted = False
        self.closed = False
        self.sent_messages = []
        self.raise_on_send = None

    async def accept(self):
        self.accepted = True

    async def send_json(self, data: dict):
        if self.raise_on_send:
            raise self.raise_on_send
        self.sent_messages.append(data)

    async def close(self, code=1000):
        self.closed = True


# ---------------------------------------------------------------------------
# 1. In-Memory Broadcasting Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_in_memory_broadcasting_delivers_to_subscribed_clients():
    """Verify in-memory backend delivers events to matching doctor rooms without cross-leakage."""
    mgr = QueueConnectionManager(backend=InMemoryBroadcastBackend())
    await mgr.start()

    ws_doc1_a = MockWebSocket()
    ws_doc1_b = MockWebSocket()
    ws_doc2 = MockWebSocket()

    await mgr.connect("doc-1", ws_doc1_a)
    await mgr.connect("doc-1", ws_doc1_b)
    await mgr.connect("doc-2", ws_doc2)

    event_doc1 = {
        "event": "QUEUE_UPDATED",
        "action": "CALLED",
        "token_display": "T-01",
        "token_number": 1,
        "room_number": "101",
    }

    await mgr.broadcast_to_doctor("doc-1", event_doc1)

    # doc-1 clients received the event
    assert len(ws_doc1_a.sent_messages) == 1
    assert ws_doc1_a.sent_messages[0] == event_doc1
    assert len(ws_doc1_b.sent_messages) == 1
    assert ws_doc1_b.sent_messages[0] == event_doc1

    # doc-2 client received nothing
    assert len(ws_doc2.sent_messages) == 0

    await mgr.stop()


# ---------------------------------------------------------------------------
# 2. Redis Message Publishing and Subscription (Mock-Based)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_redis_broadcast_backend_publish_and_subscribe():
    """Verify Redis backend starts ping healthcheck, subscribes to channels, and publishes envelopes."""
    backend = RedisBroadcastBackend(redis_url="redis://localhost:6379/0")

    mock_client = AsyncMock()
    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()
    mock_pubsub.get_message = AsyncMock(return_value=None)
    mock_client.pubsub = MagicMock(return_value=mock_pubsub)
    mock_client.ping = AsyncMock(return_value=True)
    mock_client.publish = AsyncMock()
    mock_client.aclose = AsyncMock()

    with patch("redis.asyncio.from_url", return_value=mock_client):
        dispatch_mock = AsyncMock()
        await backend.start(dispatch_fn=dispatch_mock)

        # Verified ping healthcheck
        mock_client.ping.assert_awaited_once()

        # Subscribe to a doctor channel
        await backend.subscribe_channel("doc-100")
        mock_pubsub.subscribe.assert_awaited_once_with("medismart:ws:doc-100")

        # Publish an event
        payload = {"event": "QUEUE_UPDATED", "action": "CHECK_IN", "token_display": "T-05"}
        await backend.publish("doc-100", payload)

        mock_client.publish.assert_awaited_once()
        published_channel, published_body = mock_client.publish.await_args.args
        assert published_channel == "medismart:ws:doc-100"

        envelope = json.loads(published_body)
        assert envelope["origin_worker"] == backend.worker_id
        assert envelope["channel"] == "doc-100"
        assert envelope["payload"] == payload

        # Unsubscribe
        await backend.unsubscribe_channel("doc-100")
        mock_pubsub.unsubscribe.assert_awaited_once_with("medismart:ws:doc-100")

        # Graceful shutdown
        await backend.stop()
        mock_pubsub.close.assert_awaited_once()
        mock_client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_redis_backend_fails_clearly_when_unreachable():
    """Verify Redis backend fails fast with informative RuntimeError if Redis is unreachable."""
    backend = RedisBroadcastBackend(redis_url="redis://invalid-host:6379/0")

    mock_client = AsyncMock()
    mock_client.ping.side_effect = ConnectionError("Connection refused")

    with patch("redis.asyncio.from_url", return_value=mock_client):
        with pytest.raises(RuntimeError) as exc_info:
            await backend.start(dispatch_fn=AsyncMock())

        err = str(exc_info.value)
        assert "Failed to connect to Redis broadcast backend" in err
        assert "redis://invalid-host:6379/0" in err


# ---------------------------------------------------------------------------
# 3. Delivery Between Simulated Worker Instances & Deduplication
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_simulated_multi_worker_delivery_and_deduplication():
    """
    Simulate two backend worker instances (Worker 1 and Worker 2) connected via
    a mock Redis Pub/Sub message broker.

    Verifies:
    1. Cross-worker delivery: Event broadcast on Worker 1 reaches client on Worker 2.
    2. Local delivery: Client on Worker 1 receives event immediately.
    3. Deduplication: Client on Worker 1 receives message exactly once (origin echo discarded).
    """
    # Shared simulated message bus representing Redis pub/sub
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
            # Deliver to all subscriber queues on this broker
            for sub in list(broker_subscribers):
                await sub.queue.put({"type": "message", "channel": channel, "data": message_str})

        mock.publish = AsyncMock(side_effect=mock_publish)
        return mock

    backend_worker1 = RedisBroadcastBackend("redis://simulated:6379/0")
    backend_worker2 = RedisBroadcastBackend("redis://simulated:6379/0")

    mock_r1 = create_mock_redis(backend_worker1)
    mock_r2 = create_mock_redis(backend_worker2)

    with patch("redis.asyncio.from_url", side_effect=[mock_r1, mock_r2]):
        mgr1 = QueueConnectionManager(backend=backend_worker1)
        mgr2 = QueueConnectionManager(backend=backend_worker2)

        await mgr1.start()
        await mgr2.start()

        ws_client_on_worker1 = MockWebSocket()
        ws_client_on_worker2 = MockWebSocket()

        # Connect clients on different workers to same doctor room
        await mgr1.connect("doc-A", ws_client_on_worker1)
        await mgr2.connect("doc-A", ws_client_on_worker2)

        event = {
            "event": "QUEUE_UPDATED",
            "action": "CALLED",
            "token_display": "T-10",
            "token_number": 10,
        }

        # Action: Doctor calls next patient on Worker 1
        await mgr1.broadcast_to_doctor("doc-A", event)

        # Allow async queue message delivery across simulated worker loop
        await asyncio.sleep(0.15)

        # 1. Client on Worker 1 received message locally
        assert len(ws_client_on_worker1.sent_messages) == 1
        assert ws_client_on_worker1.sent_messages[0] == event

        # 2. Client on Worker 2 received message across worker boundary via Pub/Sub
        assert len(ws_client_on_worker2.sent_messages) == 1
        assert ws_client_on_worker2.sent_messages[0] == event

        # 3. Deduplication check: Worker 1 discarded its own reflected message from Redis
        # (Client 1 message count is exactly 1, NOT 2)
        assert len(ws_client_on_worker1.sent_messages) == 1

        await mgr1.stop()
        await mgr2.stop()


# ---------------------------------------------------------------------------
# 4. Disconnect Handling & Dead Socket Pruning
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_subscription_cleanup_on_last_disconnect():
    """Verify backend unsubscribe is triggered when the final local client leaves a room."""
    backend_mock = MagicMock(spec=InMemoryBroadcastBackend)
    backend_mock.start = AsyncMock()
    backend_mock.stop = AsyncMock()
    backend_mock.publish = AsyncMock()
    backend_mock.subscribe_channel = AsyncMock()
    backend_mock.unsubscribe_channel = AsyncMock()

    mgr = QueueConnectionManager(backend=backend_mock)
    await mgr.start()

    ws1 = MockWebSocket()
    ws2 = MockWebSocket()

    # First client connects: triggers subscription
    await mgr.connect("doc-clean", ws1)
    backend_mock.subscribe_channel.assert_awaited_once_with("doc-clean")

    # Second client connects: does not trigger redundant subscription
    await mgr.connect("doc-clean", ws2)
    assert backend_mock.subscribe_channel.await_count == 1

    # First client disconnects: room still has ws2
    mgr.disconnect("doc-clean", ws1)
    assert "doc-clean" in mgr.active_rooms
    assert backend_mock.unsubscribe_channel.await_count == 0

    # Second client disconnects: room is empty, triggers unsubscribe
    mgr.disconnect("doc-clean", ws2)
    await asyncio.sleep(0.01)  # allow loop task to run
    assert "doc-clean" not in mgr.active_rooms
    backend_mock.unsubscribe_channel.assert_awaited_once_with("doc-clean")

    await mgr.stop()


@pytest.mark.asyncio
async def test_dead_socket_pruning_on_broadcast():
    """Verify broken/disconnected sockets are pruned during broadcast without halting other clients."""
    mgr = QueueConnectionManager(backend=InMemoryBroadcastBackend())
    await mgr.start()

    healthy_ws = MockWebSocket()
    broken_ws = MockWebSocket()
    broken_ws.raise_on_send = WebSocketDisconnect(code=1006)

    await mgr.connect("doc-prune", healthy_ws)
    await mgr.connect("doc-prune", broken_ws)
    assert len(mgr.active_rooms["doc-prune"]) == 2

    event = {"event": "QUEUE_UPDATED", "action": "IN_CONSULTATION"}
    await mgr.broadcast_to_doctor("doc-prune", event)

    # Healthy client received event
    assert len(healthy_ws.sent_messages) == 1

    # Broken client was pruned from active room
    assert len(mgr.active_rooms["doc-prune"]) == 1
    assert broken_ws not in mgr.active_rooms["doc-prune"]

    await mgr.stop()


# ---------------------------------------------------------------------------
# 5. Zero-PII Message Preservation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_event_payload_preserves_zero_pii():
    """Verify broadcast payloads contain only token/status identifiers without personal health data."""
    mgr = QueueConnectionManager(backend=InMemoryBroadcastBackend())
    await mgr.start()

    ws = MockWebSocket()
    await mgr.connect("doc-pii", ws)

    public_event = {
        "event": "QUEUE_UPDATED",
        "action": "CALLED",
        "token_display": "A-001",
        "token_number": 1,
        "room_number": "101",
        "timestamp": "2026-10-24T10:00:00",
    }

    await mgr.broadcast_to_doctor("doc-pii", public_event)

    msg = ws.sent_messages[0]
    assert msg["token_display"] == "A-001"
    assert "patient_name" not in msg
    assert "phone" not in msg
    assert "notes" not in msg
    assert "clinical_notes" not in msg
    assert "email" not in msg

    await mgr.stop()


# ---------------------------------------------------------------------------
# 6. Settings Validation for Broadcast Backend
# ---------------------------------------------------------------------------

def test_settings_ws_broadcast_backend_validation():
    """Verify Settings validates WS_BROADCAST_BACKEND and REDIS_URL correctly."""
    # Valid default
    s_default = Settings()
    assert s_default.WS_BROADCAST_BACKEND == "memory"

    # Valid Redis
    s_redis = Settings(
        WS_BROADCAST_BACKEND="redis",
        REDIS_URL="redis://custom:6379/1",
    )
    assert s_redis.WS_BROADCAST_BACKEND == "redis"
    assert s_redis.REDIS_URL == "redis://custom:6379/1"

    # Invalid backend name
    with pytest.raises(ValueError) as exc:
        Settings(WS_BROADCAST_BACKEND="rabbitmq")
    assert "WS_BROADCAST_BACKEND must be either 'memory' or 'redis'" in str(exc.value)

    # Empty REDIS_URL when backend is redis
    with pytest.raises(ValueError) as exc:
        Settings(WS_BROADCAST_BACKEND="redis", REDIS_URL="   ")
    assert "REDIS_URL must be defined" in str(exc.value)
