from fastapi import APIRouter

from app import legacy_main as legacy

router = APIRouter()
router.add_api_route("/chat/", legacy.create_chat, methods=["POST"])
router.add_api_route("/guest-chat", legacy.guest_chat, methods=["POST"])
router.add_api_route("/chat/history/", legacy.get_chat_history, methods=["GET"])
router.add_api_route(
    "/chat/conversation/{conversation_id}/messages",
    legacy.get_conversation_messages,
    methods=["GET"],
)
