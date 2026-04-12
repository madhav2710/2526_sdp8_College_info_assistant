from app.schemas.admin import AdminCreateRequest, AdminStatusUpdateRequest, AdminUpdateRequest
from app.schemas.auth import LoginRequest, SetCollegeRequest, SignupRequest
from app.schemas.chat import ChatMessage, ChatRequest, GuestChatRequest
from app.schemas.college import CollegeCreateRequest, CollegeUpdateRequest
from app.schemas.document import (
    DocumentApprovalRequest,
    DocumentRejectionRequest,
    ScheduleProcessingRequest,
    TriggerProcessingRequest,
)

__all__ = [
    "AdminCreateRequest",
    "AdminStatusUpdateRequest",
    "AdminUpdateRequest",
    "ChatMessage",
    "ChatRequest",
    "CollegeCreateRequest",
    "CollegeUpdateRequest",
    "DocumentApprovalRequest",
    "DocumentRejectionRequest",
    "GuestChatRequest",
    "LoginRequest",
    "ScheduleProcessingRequest",
    "SetCollegeRequest",
    "SignupRequest",
    "TriggerProcessingRequest",
]
