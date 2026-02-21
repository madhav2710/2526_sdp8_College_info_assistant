from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class DocumentApprovalRequest(BaseModel):
    document_id: UUID
    comments: Optional[str] = None
    process_schedule: Optional[str] = "immediate"
    scheduled_at: Optional[datetime] = None


class DocumentRejectionRequest(BaseModel):
    document_id: UUID
    reason: str


class ScheduleProcessingRequest(BaseModel):
    document_id: UUID
    scheduled_at: datetime


class TriggerProcessingRequest(BaseModel):
    document_id: UUID
