import abc
import asyncio
import json
import logging
import uuid
from typing import Callable, Coroutine, Dict, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import decode_access_token
from app.models.user import User

logger = logging.getLogger(__name__)


class BaseBroadcastBackend(abc.ABC):
    """Abstract interface for WebSocket event broadcasting across workers."""

    @abc.abstractmethod
    async def start(self, dispatch_fn: Callable[[str, dict], Coroutine]) -> None:
        """Initializes backend listeners and connection pools."""
        pass

    @abc.abstractmethod
    async def stop(self) -> None:
        """Gracefully terminates subscriptions, background tasks, and connections."""
        pass

    @abc.abstractmethod
    async def publish(self, channel: str, message: dict) -> None:
        """Publishes an event to a specified channel."""
        pass

    @abc.abstractmethod
    async def subscribe_channel(self, channel: str) -> None:
        """Subscribes this worker process to a channel."""
        pass

    @abc.abstractmethod
    async def unsubscribe_channel(self, channel: str) -> None:
        """Unsubscribes this worker process from a channel."""
        pass


class InMemoryBroadcastBackend(BaseBroadcastBackend):
    """
    In-memory broadcast backend for local single-process development and tests.
    Dispatches directly without external network or broker overhead.
    """

    def __init__(self):
        self._dispatch_fn: Optional[Callable[[str, dict], Coroutine]] = None

    async def start(self, dispatch_fn: Callable[[str, dict], Coroutine]) -> None:
        self._dispatch_fn = dispatch_fn
        logger.info("InMemory WebSocket broadcast backend initialized")

    async def stop(self) -> None:
        self._dispatch_fn = None

    async def publish(self, channel: str, message: dict) -> None:
        # In single-process mode, local dispatch is handled directly by QueueConnectionManager
        pass

    async def subscribe_channel(self, channel: str) -> None:
        pass

    async def unsubscribe_channel(self, channel: str) -> None:
        pass


class RedisBroadcastBackend(BaseBroadcastBackend):
    """
    Redis Pub/Sub broadcast backend for multi-worker / multi-instance scaling.
    Publishes events to Redis and relays messages between worker nodes while
    strictly preventing duplicate delivery to local clients.
    """

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.worker_id = uuid.uuid4().hex[:8]
        self._redis_client = None
        self._pubsub = None
        self._listener_task: Optional[asyncio.Task] = None
        self._subscribed_channels: Set[str] = set()
        self._dispatch_fn: Optional[Callable[[str, dict], Coroutine]] = None
        self._is_running = False

    async def start(self, dispatch_fn: Callable[[str, dict], Coroutine]) -> None:
        import redis.asyncio as aioredis

        self._dispatch_fn = dispatch_fn
        try:
            self._redis_client = aioredis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=5.0,
            )
            # Fail-fast healthcheck: fail clearly if Redis is selected but unreachable
            await self._redis_client.ping()
        except Exception as exc:
            raise RuntimeError(
                f"Failed to connect to Redis broadcast backend at {self.redis_url}: {exc}"
            ) from exc

        self._pubsub = self._redis_client.pubsub()
        self._is_running = True
        self._listener_task = asyncio.create_task(self._listen_loop())
        logger.info(
            f"Redis WebSocket broadcast backend started on worker {self.worker_id} ({self.redis_url})"
        )

    async def stop(self) -> None:
        self._is_running = False
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None

        if self._pubsub:
            try:
                await self._pubsub.close()
            except Exception as e:
                logger.debug(f"Error closing pubsub: {e}")
            self._pubsub = None

        if self._redis_client:
            try:
                await self._redis_client.aclose()
            except Exception as e:
                logger.debug(f"Error closing redis client: {e}")
            self._redis_client = None

        self._subscribed_channels.clear()
        self._dispatch_fn = None
        logger.info(f"Redis broadcast backend stopped on worker {self.worker_id}")

    async def publish(self, channel: str, message: dict) -> None:
        if not self._redis_client:
            return

        redis_channel = f"medismart:ws:{channel}"
        envelope = {
            "origin_worker": self.worker_id,
            "channel": channel,
            "payload": message,
        }
        try:
            await self._redis_client.publish(redis_channel, json.dumps(envelope))
        except Exception as exc:
            logger.error(f"Failed to publish WebSocket event to Redis on {redis_channel}: {exc}")

    async def subscribe_channel(self, channel: str) -> None:
        if not self._pubsub or channel in self._subscribed_channels:
            return

        redis_channel = f"medismart:ws:{channel}"
        try:
            await self._pubsub.subscribe(redis_channel)
            self._subscribed_channels.add(channel)
            logger.debug(f"Worker {self.worker_id} subscribed to Redis channel {redis_channel}")
        except Exception as exc:
            logger.error(f"Failed to subscribe to Redis channel {redis_channel}: {exc}")

    async def unsubscribe_channel(self, channel: str) -> None:
        if not self._pubsub or channel not in self._subscribed_channels:
            return

        redis_channel = f"medismart:ws:{channel}"
        try:
            await self._pubsub.unsubscribe(redis_channel)
            self._subscribed_channels.discard(channel)
            logger.debug(f"Worker {self.worker_id} unsubscribed from Redis channel {redis_channel}")
        except Exception as exc:
            logger.debug(f"Failed to unsubscribe from Redis channel {redis_channel}: {exc}")

    async def _listen_loop(self) -> None:
        """Background coroutine listening for cross-worker messages from Redis Pub/Sub."""
        try:
            while self._is_running and self._pubsub:
                try:
                    raw_msg = await self._pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    )
                    if raw_msg is None:
                        await asyncio.sleep(0.01)
                        continue

                    if raw_msg.get("type") == "message":
                        data_str = raw_msg.get("data")
                        if not data_str:
                            continue

                        envelope = json.loads(data_str)
                        origin_worker = envelope.get("origin_worker")

                        # Deduplication safeguard: If this worker sent the message,
                        # ignore it because local sockets already received the direct broadcast
                        if origin_worker == self.worker_id:
                            continue

                        channel = envelope.get("channel")
                        payload = envelope.get("payload")

                        if channel and payload and self._dispatch_fn:
                            await self._dispatch_fn(channel, payload)
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    if self._is_running:
                        logger.warning(f"Error in Redis pubsub listener: {exc}")
                        await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            pass


class QueueConnectionManager:
    """
    Manages live WebSocket subscriptions for real-time queue updates.
    Scoped by doctor_id to prevent cross-doctor event leakage.
    Supports pluggable broadcast backends (in-memory for dev, Redis for multi-worker).
    """

    def __init__(self, backend: Optional[BaseBroadcastBackend] = None):
        # doctor_id -> Set of active WebSockets on this worker process
        self.active_rooms: Dict[str, Set[WebSocket]] = {}
        self.backend: BaseBroadcastBackend = backend or self._build_default_backend()

    @staticmethod
    def _build_default_backend() -> BaseBroadcastBackend:
        backend_type = getattr(settings, "WS_BROADCAST_BACKEND", "memory").lower().strip()
        if backend_type == "redis":
            return RedisBroadcastBackend(redis_url=settings.REDIS_URL)
        return InMemoryBroadcastBackend()

    async def start(self) -> None:
        """Initializes the broadcast backend and registers the local dispatch callback."""
        await self.backend.start(dispatch_fn=self._dispatch_remote_message)

    async def stop(self) -> None:
        """Gracefully shuts down the broadcast backend."""
        await self.backend.stop()

    async def connect(self, doctor_id: str, websocket: WebSocket) -> None:
        """Accepts WebSocket connection and subscribes it to the doctor's channel."""
        await websocket.accept()
        is_first = doctor_id not in self.active_rooms or len(self.active_rooms[doctor_id]) == 0
        if doctor_id not in self.active_rooms:
            self.active_rooms[doctor_id] = set()
        self.active_rooms[doctor_id].add(websocket)

        if is_first:
            await self.backend.subscribe_channel(doctor_id)

        logger.info(
            f"WebSocket connected to doctor room {doctor_id}. Local active: {len(self.active_rooms[doctor_id])}"
        )

    def disconnect(self, doctor_id: str, websocket: WebSocket) -> None:
        """Removes a disconnected WebSocket from the doctor's channel."""
        if doctor_id in self.active_rooms:
            self.active_rooms[doctor_id].discard(websocket)
            if not self.active_rooms[doctor_id]:
                del self.active_rooms[doctor_id]
                # If channel is now empty on this worker, schedule unsubscribe on backend
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.backend.unsubscribe_channel(doctor_id))
                except RuntimeError:
                    pass
        logger.info(f"WebSocket disconnected from doctor room {doctor_id}")

    async def broadcast_to_doctor(self, doctor_id: str, message: dict) -> None:
        """
        Broadcasts an event message to all clients subscribed to the specific doctor's room.
        Delivers locally immediately, and publishes to Redis for cross-worker delivery.
        """
        # 1. Local delivery to all sockets connected to this worker
        await self._send_to_local_room(doctor_id, message)

        # 2. Publish to broadcast backend for cross-worker delivery (Redis)
        await self.backend.publish(doctor_id, message)

    async def _dispatch_remote_message(self, doctor_id: str, message: dict) -> None:
        """Callback invoked when a message is received from a remote worker via Redis."""
        await self._send_to_local_room(doctor_id, message)

    async def _send_to_local_room(self, doctor_id: str, message: dict) -> None:
        """Safely delivers a message to all locally connected WebSockets in a doctor room."""
        if doctor_id not in self.active_rooms:
            return

        dead_sockets = set()
        for ws in list(self.active_rooms[doctor_id]):
            try:
                await ws.send_json(message)
            except (WebSocketDisconnect, RuntimeError, Exception) as exc:
                logger.debug(f"Failed to send to client in room {doctor_id}: {exc}")
                dead_sockets.add(ws)

        for dead_ws in dead_sockets:
            self.disconnect(doctor_id, dead_ws)


queue_ws_manager = QueueConnectionManager()


class UserNotificationConnectionManager:
    """
    Manages live WebSocket subscriptions for private user notifications.
    Scoped strictly by user_id to prevent cross-user data leakage.
    Supports pluggable broadcast backends (in-memory for dev, Redis for multi-worker).
    """

    def __init__(self, backend: Optional[BaseBroadcastBackend] = None):
        # user_id (str) -> Set of active WebSockets on this worker process
        self.active_users: Dict[str, Set[WebSocket]] = {}
        self.backend: BaseBroadcastBackend = backend or self._build_default_backend()

    @staticmethod
    def _build_default_backend() -> BaseBroadcastBackend:
        backend_type = getattr(settings, "WS_BROADCAST_BACKEND", "memory").lower().strip()
        if backend_type == "redis":
            return RedisBroadcastBackend(redis_url=settings.REDIS_URL)
        return InMemoryBroadcastBackend()

    async def start(self) -> None:
        """Initializes the broadcast backend and registers the local dispatch callback."""
        await self.backend.start(dispatch_fn=self._dispatch_remote_message)

    async def stop(self) -> None:
        """Gracefully shuts down the broadcast backend."""
        await self.backend.stop()

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        """Accepts WebSocket connection and subscribes it to the user's private channel."""
        uid = str(user_id)
        await websocket.accept()
        is_first = uid not in self.active_users or len(self.active_users[uid]) == 0
        if uid not in self.active_users:
            self.active_users[uid] = set()
        self.active_users[uid].add(websocket)

        if is_first:
            await self.backend.subscribe_channel(f"user:{uid}")

        logger.info(
            f"Notification WebSocket connected for user {uid}. Local active: {len(self.active_users[uid])}"
        )

    def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        """Removes a disconnected WebSocket from the user's private channel."""
        uid = str(user_id)
        if uid in self.active_users:
            self.active_users[uid].discard(websocket)
            if not self.active_users[uid]:
                del self.active_users[uid]
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.backend.unsubscribe_channel(f"user:{uid}"))
                except RuntimeError:
                    pass
        logger.info(f"Notification WebSocket disconnected for user {uid}")

    async def broadcast_to_user(self, user_id: str, message: dict) -> None:
        """
        Broadcasts an event message strictly to the specified user.
        Delivers locally immediately, and publishes to Redis for cross-worker delivery.
        """
        uid = str(user_id)
        # 1. Local delivery to all sockets connected to this worker for this user
        await self._send_to_local_user(uid, message)

        # 2. Publish to broadcast backend for cross-worker delivery (Redis)
        await self.backend.publish(f"user:{uid}", message)

    async def _dispatch_remote_message(self, channel: str, message: dict) -> None:
        """Callback invoked when a message is received from a remote worker via Redis."""
        if channel.startswith("user:"):
            uid = channel.split("user:", 1)[1]
            await self._send_to_local_user(uid, message)

    async def _send_to_local_user(self, user_id: str, message: dict) -> None:
        """Safely delivers a message to all locally connected WebSockets for a user."""
        uid = str(user_id)
        if uid not in self.active_users:
            return

        dead_sockets = set()
        for ws in list(self.active_users[uid]):
            try:
                await ws.send_json(message)
            except (WebSocketDisconnect, RuntimeError, Exception) as exc:
                logger.debug(f"Failed to send to client for user {uid}: {exc}")
                dead_sockets.add(ws)

        for dead_ws in dead_sockets:
            self.disconnect(uid, dead_ws)


user_ws_manager = UserNotificationConnectionManager()


async def authenticate_websocket(websocket: WebSocket) -> Optional[User]:
    """
    Validates origin and authenticates user during WebSocket handshake.
    Dual transport:
    1. HttpOnly cookie 'access_token' (browser standard).
    2. 'Authorization: Bearer <token>' header or Sec-WebSocket-Protocol.
    Returns authenticated active User or None.
    """
    # 1. Validate Origin if header present
    origin = websocket.headers.get("origin")
    if origin and settings.CORS_ORIGINS != ["*"]:
        allowed = any(
            origin == allowed_origin or allowed_origin == "*"
            for allowed_origin in settings.CORS_ORIGINS
        )
        if not allowed:
            logger.warning(f"WebSocket rejected: unauthorized origin {origin}")
            return None

    # 2. Extract Token
    token = None
    # Check Cookie
    cookie_token = websocket.cookies.get("access_token")
    if cookie_token:
        token = cookie_token
    else:
        # Check Authorization header
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()

    if not token:
        logger.debug("WebSocket rejected: missing authentication credentials")
        return None

    # 3. Decode and validate JWT
    payload = decode_access_token(token)
    if not payload:
        logger.debug("WebSocket rejected: invalid token payload")
        return None

    if payload.get("iss") != settings.JWT_ISSUER:
        logger.debug("WebSocket rejected: invalid token issuer")
        return None

    user_id_str = payload.get("sub")
    if not user_id_str:
        return None

    try:
        user_uuid = uuid.UUID(user_id_str)
    except (ValueError, TypeError):
        return None

    # 4. Verify user exists and is active in database
    async with AsyncSessionLocal() as session:
        query = select(User).where(User.id == user_uuid)
        res = await session.execute(query)
        user = res.scalar_one_or_none()

        if user and user.is_active:
            return user

    logger.debug(f"WebSocket rejected: user {user_id_str} not found or inactive")
    return None
