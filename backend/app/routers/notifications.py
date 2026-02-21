from fastapi import APIRouter

from app import legacy_main as legacy

router = APIRouter()
router.add_api_route("/notifications", legacy.get_notifications, methods=["GET"])
router.add_api_route(
    "/notifications/{notification_id}/read",
    legacy.mark_notification_read,
    methods=["PUT"],
)
router.add_api_route(
    "/notifications/{notification_id}",
    legacy.delete_notification,
    methods=["DELETE"],
)
router.add_api_route(
    "/notifications/unread-count",
    legacy.get_unread_notification_count,
    methods=["GET"],
)
