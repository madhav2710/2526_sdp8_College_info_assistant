from uuid import UUID

from fastapi import HTTPException

from app.core.notifications import notification_manager
from app.models.notification import NotificationFilters, NotificationType


async def get_notifications_for_user(
    user_id: str,
    unread_only: bool | None = None,
    notification_type: str | None = None,
    limit: int | None = 50,
    offset: int | None = 0,
) -> dict:
    try:
        validated_type = None
        if notification_type:
            try:
                validated_type = NotificationType(notification_type)
            except ValueError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid notification type: {notification_type}",
                ) from exc

        filters = NotificationFilters(
            unread_only=unread_only,
            notification_type=validated_type,
            limit=min(limit or 50, 100),
            offset=max(offset or 0, 0),
        )

        notifications = await notification_manager.get_notifications(
            user_id=UUID(user_id), filters=filters
        )
        unread_count = await notification_manager.get_unread_count(
            user_id=UUID(user_id)
        )

        return {
            "notifications": notifications,
            "unread_count": unread_count,
            "total_count": len(notifications),
            "filters": {
                "unread_only": unread_only,
                "notification_type": notification_type,
                "limit": limit,
                "offset": offset,
            },
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve notifications: {str(exc)}"
        ) from exc


async def mark_notification_as_read(notification_id: UUID, user_id: str) -> dict:
    try:
        success = await notification_manager.mark_as_read(
            notification_id=notification_id, user_id=UUID(user_id)
        )

        if not success:
            raise HTTPException(
                status_code=404, detail="Notification not found or already read"
            )

        return {
            "status": "success",
            "message": "Notification marked as read",
            "notification_id": str(notification_id),
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to mark notification as read: {str(exc)}",
        ) from exc


async def delete_notification_for_user(notification_id: UUID, user_id: str) -> dict:
    try:
        success = await notification_manager.delete_notification(
            notification_id=notification_id, user_id=UUID(user_id)
        )

        if not success:
            raise HTTPException(status_code=404, detail="Notification not found")

        return {
            "status": "success",
            "message": "Notification deleted successfully",
            "notification_id": str(notification_id),
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete notification: {str(exc)}"
        ) from exc


async def get_unread_notification_count_for_user(user_id: str) -> dict:
    try:
        unread_count = await notification_manager.get_unread_count(
            user_id=UUID(user_id)
        )
        return {"unread_count": unread_count}

    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get unread count: {str(exc)}"
        ) from exc
