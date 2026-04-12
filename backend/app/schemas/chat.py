from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ChatMessage(BaseModel):
    conversation_id: UUID
    user_id: UUID
    role: str
    content: str
    created_at: Optional[datetime] = None


class ChatRequest(BaseModel):
    user_id: UUID
    title: str


class GuestChatRequest(BaseModel):
    content: str
    college_id: Optional[str] = None
