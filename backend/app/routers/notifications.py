from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.services.notification_service import (
    delete_notification_for_user,
    get_notifications_for_user,
    get_unread_notification_count_for_user,
    mark_notification_as_read,
)

router = APIRouter()


@router.get("/notifications")
async def get_notifications(
    unread_only: Optional[bool] = None,
    notification_type: Optional[str] = None,
    limit: Optional[int] = 50,
    offset: Optional[int] = 0,
    current_user: dict = Depends(get_current_user),
):
    return await get_notifications_for_user(
        user_id=current_user["user_id"],
        unread_only=unread_only,
        notification_type=notification_type,
        limit=limit,
        offset=offset,
    )


@router.put("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID, current_user: dict = Depends(get_current_user)
):
    return await mark_notification_as_read(
        notification_id=notification_id, user_id=current_user["user_id"]
    )


@router.delete("/notifications/{notification_id}")
async def delete_notification(
    notification_id: UUID, current_user: dict = Depends(get_current_user)
):
    return await delete_notification_for_user(
        notification_id=notification_id, user_id=current_user["user_id"]
    )


@router.get("/notifications/unread-count")
async def get_unread_notification_count(current_user: dict = Depends(get_current_user)):
    return await get_unread_notification_count_for_user(user_id=current_user["user_id"])
