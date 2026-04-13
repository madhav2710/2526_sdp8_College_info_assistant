from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.schemas.chat import ChatMessage, GuestChatRequest
from app.services.chat_service import (
    create_chat_response,
    create_guest_chat_response,
    get_chat_history_for_user,
    get_conversation_messages_for_user,
)

router = APIRouter()


@router.post("/chat/")
async def create_chat(
    message: ChatMessage, current_user: dict = Depends(get_current_user)
):
    return await create_chat_response(message=message, current_user=current_user)


@router.post("/guest-chat")
async def guest_chat(request: GuestChatRequest):
    return await create_guest_chat_response(request=request)


@router.get("/chat/history/")
async def get_chat_history(current_user: dict = Depends(get_current_user)):
    return await get_chat_history_for_user(user_id=current_user["user_id"])


@router.get("/chat/conversation/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: UUID, current_user: dict = Depends(get_current_user)
):
    return await get_conversation_messages_for_user(
        conversation_id=str(conversation_id),
        user_id=current_user["user_id"],
    )
