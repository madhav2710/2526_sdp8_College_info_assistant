from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class NotificationType(str, Enum):
    """Enumeration of notification types"""
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_APPROVED = "document_approved"
    DOCUMENT_REJECTED = "document_rejected"
    DOCUMENT_PROCESSED = "document_processed"
    DOCUMENT_FAILED = "document_failed"


class NotificationBase(BaseModel):
    """Base notification model with common fields"""
    recipient_id: UUID
    type: NotificationType
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=1000)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NotificationCreate(NotificationBase):
    """Model for creating new notifications"""
    pass


class NotificationUpdate(BaseModel):
    """Model for updating notification properties"""
    is_read: Optional[bool] = None
    read_at: Optional[datetime] = None


class Notification(NotificationBase):
    """Complete notification model with all database fields"""
    id: UUID
    is_read: bool = False
    created_at: datetime
    read_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NotificationResponse(BaseModel):
    """Response model for notification API endpoints"""
    notifications: list[Notification]
    unread_count: int
    total_count: int


class NotificationFilters(BaseModel):
    """Model for notification filtering parameters"""
    unread_only: Optional[bool] = None
    notification_type: Optional[NotificationType] = None
    limit: Optional[int] = Field(default=50, ge=1, le=100)
    offset: Optional[int] = Field(default=0, ge=0)