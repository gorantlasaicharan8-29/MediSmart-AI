import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.core.websocket import authenticate_websocket, user_ws_manager
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import (
    NotificationListResponse,
    NotificationReadAllResponse,
    NotificationResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=NotificationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List authenticated user notifications",
    description="Retrieve paginated notifications for the current authenticated user, ordered newest first.",
)
async def list_notifications(
    limit: int = Query(20, ge=1, le=100, description="Maximum notifications to return (1-100)"),
    offset: int = Query(0, ge=0, description="Number of notifications to skip (>=0)"),
    is_read: Optional[bool] = Query(None, description="Filter by read status (true/false)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> NotificationListResponse:
    """
    List notifications scoped strictly to the authenticated user.
    - Guaranteed patient privacy and multi-tenant isolation.
    - Evaluates total count and retrieves paginated slice.
    - Avoids unnecessary items retrieval query when total matching records is 0.
    """
    # 1. Base filter strictly scoped to the authenticated user
    base_filters = [Notification.user_id == current_user.id]
    if is_read is not None:
        base_filters.append(Notification.is_read.is_(is_read))

    # 2. Count total matching items for pagination metadata
    count_stmt = select(func.count()).select_from(Notification).where(*base_filters)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # 3. Retrieve user's overall unread count for badge/drawer status
    if is_read is False:
        unread_count = total
    elif is_read is None and total == 0:
        unread_count = 0
    else:
        unread_stmt = select(func.count()).select_from(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        unread_result = await db.execute(unread_stmt)
        unread_count = unread_result.scalar_one()

    # 4. Fetch paginated records only if there are items to return
    items = []
    if total > 0 and offset < total:
        items_stmt = (
            select(Notification)
            .where(*base_filters)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset(offset)
            .limit(limit)
        )
        items_result = await db.execute(items_stmt)
        items = list(items_result.scalars().all())

    return NotificationListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        unread_count=unread_count,
    )


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark a notification as read",
    description="Marks a specific notification as read. Repeated requests are safe and idempotent.",
)
async def mark_notification_as_read(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> NotificationResponse:
    """
    Marks a single notification as read.
    - Strictly scoped to the authenticated user's records.
    - Returns 404 for non-existent OR other users' notifications to prevent IDOR existence leakage.
    - Idempotent: repeated calls safely return the notification without overwriting read_at.
    """
    stmt = select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    # Idempotent mutation: only write if not already marked read or missing read_at
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(notification)
    elif notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(notification)

    return notification


@router.post(
    "/read-all",
    response_model=NotificationReadAllResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark all unread notifications as read",
    description="Marks all unread notifications for the authenticated user as read.",
)
async def mark_all_notifications_as_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> NotificationReadAllResponse:
    """
    Batch-marks all unread notifications belonging to the current user as read.
    - Restricts update to records where is_read is False, preventing unnecessary writes.
    - Returns the count of records updated.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .values(
            is_read=True,
            read_at=now,
        )
    )
    result = await db.execute(stmt)
    await db.commit()
    updated_count = result.rowcount or 0

    return NotificationReadAllResponse(
        updated_count=updated_count,
        message=f"Successfully marked {updated_count} notification(s) as read.",
    )


@router.websocket("/ws")
async def notification_websocket_endpoint(
    websocket: WebSocket,
):
    """
    Private WebSocket endpoint for delivering real-time patient notifications.
    - Requires authenticated user via cookie ('access_token') or 'Authorization: Bearer <token>' header.
    - Strictly scoped to the authenticated user's ID.
    - Rejects unauthenticated connections with WS_1008_POLICY_VIOLATION.
    - Server-push only: client cannot broadcast arbitrary events to other users.
    - Supports heartbeat ping/pong to keep connection alive.
    """
    user = await authenticate_websocket(websocket)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id_str = str(user.id)
    await user_ws_manager.connect(user_id_str, websocket)

    try:
        while True:
            # Notifications channel is server-to-client push only.
            # Client messages are handled for keepalive (ping/pong) and disconnect detection.
            # Clients are strictly prohibited from broadcasting events to other users.
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if isinstance(msg, dict) and msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except Exception:
                pass
    except WebSocketDisconnect:
        user_ws_manager.disconnect(user_id_str, websocket)
    except Exception as exc:
        logger.debug(f"Notification WebSocket error for user {user_id_str}: {exc}")
        user_ws_manager.disconnect(user_id_str, websocket)


