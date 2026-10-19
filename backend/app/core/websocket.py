import logging
import uuid
from typing import Dict, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import decode_access_token
from app.models.user import User

logger = logging.getLogger(__name__)


class QueueConnectionManager:
    """
    Manages live WebSocket subscriptions for real-time queue updates.
    Scoped by doctor_id to prevent cross-doctor event leakage.
    """

    def __init__(self):
        # doctor_id -> Set of active WebSockets
        self.active_rooms: Dict[str, Set[WebSocket]] = {}

    async def connect(self, doctor_id: str, websocket: WebSocket) -> None:
        """Accepts WebSocket connection and subscribes it to the doctor's channel."""
        await websocket.accept()
        if doctor_id not in self.active_rooms:
            self.active_rooms[doctor_id] = set()
        self.active_rooms[doctor_id].add(websocket)
        logger.info(f"WebSocket connected to doctor room {doctor_id}. Active: {len(self.active_rooms[doctor_id])}")

    def disconnect(self, doctor_id: str, websocket: WebSocket) -> None:
        """Removes a disconnected WebSocket from the doctor's channel."""
        if doctor_id in self.active_rooms:
            self.active_rooms[doctor_id].discard(websocket)
            if not self.active_rooms[doctor_id]:
                del self.active_rooms[doctor_id]
        logger.info(f"WebSocket disconnected from doctor room {doctor_id}")

    async def broadcast_to_doctor(self, doctor_id: str, message: dict) -> None:
        """
        Broadcasts an event message to all clients subscribed to the specific doctor's room.
        Safely purges dead/broken sockets without interrupting the event loop.
        """
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
