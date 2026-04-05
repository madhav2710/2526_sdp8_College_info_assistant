from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.core.auth import get_current_user
from app.schemas.admin import (
    AdminCreateRequest,
    AdminStatusUpdateRequest,
    AdminUpdateRequest,
)
from app.schemas.college import CollegeCreateRequest, CollegeUpdateRequest
from app.schemas.document import (
    DocumentApprovalRequest,
    DocumentRejectionRequest,
    ScheduleProcessingRequest,
    TriggerProcessingRequest,
)
from app.services.document_service import (
    approve_document_for_superadmin,
    get_pending_documents_for_superadmin,
    get_scheduled_documents_for_superadmin,
    reject_document_for_superadmin,
    schedule_document_processing_for_superadmin,
    trigger_document_processing_for_superadmin,
)
from app.services.governance_service import (
    create_superadmin_admin_account,
    create_superadmin_college_record,
    delete_superadmin_admin_account,
    delete_superadmin_college_record,
    get_superadmin_admin_directory,
    get_superadmin_college_directory,
    get_superadmin_dashboard_stats,
    get_superadmin_document_groups,
    toggle_superadmin_admin_account_status,
    update_superadmin_admin_account,
    update_superadmin_college_record,
)

router = APIRouter()


def _require_super_admin(current_user: dict, action: str) -> None:
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail=f"Not authorized to {action}")


@router.get("/super-admin/pending-documents")
async def get_pending_documents(current_user: dict = Depends(get_current_user)):
    _require_super_admin(current_user, "view pending documents")
    return get_pending_documents_for_superadmin()


@router.post("/super-admin/approve-document")
async def approve_document(
    request: DocumentApprovalRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    _require_super_admin(current_user, "approve documents")
    return await approve_document_for_superadmin(
        request=request,
        current_user=current_user,
        background_tasks=background_tasks,
    )


@router.post("/super-admin/reject-document")
async def reject_document(
    request: DocumentRejectionRequest,
    current_user: dict = Depends(get_current_user),
):
    _require_super_admin(current_user, "reject documents")
    return await reject_document_for_superadmin(
        request=request,
        current_user=current_user,
    )


@router.post("/super-admin/schedule-document-processing")
async def schedule_document_processing(
    request: ScheduleProcessingRequest,
    current_user: dict = Depends(get_current_user),
):
    _require_super_admin(current_user, "schedule processing")
    return await schedule_document_processing_for_superadmin(
        request=request,
        current_user=current_user,
    )


@router.post("/super-admin/trigger-processing")
async def trigger_processing(
    request: TriggerProcessingRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    _require_super_admin(current_user, "trigger processing")
    return await trigger_document_processing_for_superadmin(
        request=request,
        current_user=current_user,
        background_tasks=background_tasks,
    )


@router.get("/super-admin/scheduled-documents")
async def get_scheduled_documents(current_user: dict = Depends(get_current_user)):
    _require_super_admin(current_user, "view scheduled documents")
    return get_scheduled_documents_for_superadmin()


@router.get("/superadmin/stats")
async def get_superadmin_stats(current_user: dict = Depends(get_current_user)):
    _require_super_admin(current_user, "view superadmin stats")
    return get_superadmin_dashboard_stats()


@router.get("/superadmin/colleges")
async def get_superadmin_colleges(
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    _require_super_admin(current_user, "view colleges")
    return get_superadmin_college_directory(search=search)


@router.post("/superadmin/colleges")
async def create_superadmin_college(
    request: CollegeCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    _require_super_admin(current_user, "create colleges")
    return create_superadmin_college_record(request=request)


@router.put("/superadmin/colleges/{college_id}")
async def update_superadmin_college(
    college_id: str,
    request: CollegeUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    _require_super_admin(current_user, "update colleges")
    return update_superadmin_college_record(college_id=college_id, request=request)


@router.delete("/superadmin/colleges/{college_id}")
async def delete_superadmin_college(
    college_id: str,
    current_user: dict = Depends(get_current_user),
):
    _require_super_admin(current_user, "delete colleges")
    return delete_superadmin_college_record(college_id=college_id)


@router.get("/superadmin/admins")
async def get_superadmin_admins(
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    _require_super_admin(current_user, "view admins")
    return get_superadmin_admin_directory(search=search)


@router.post("/superadmin/admins")
async def create_superadmin_admin(
    request: AdminCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    _require_super_admin(current_user, "create admins")
    return create_superadmin_admin_account(request=request)


@router.put("/superadmin/admins/{admin_id}")
async def update_superadmin_admin(
    admin_id: str,
    request: AdminUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    _require_super_admin(current_user, "update admins")
    return update_superadmin_admin_account(admin_id=admin_id, request=request)


@router.delete("/superadmin/admins/{admin_id}")
async def delete_superadmin_admin(
    admin_id: str,
    current_user: dict = Depends(get_current_user),
):
    _require_super_admin(current_user, "delete admins")
    return delete_superadmin_admin_account(admin_id=admin_id)


@router.patch("/superadmin/admins/{admin_id}/toggle-status")
async def toggle_superadmin_admin_status(
    admin_id: str,
    request: AdminStatusUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    _require_super_admin(current_user, "update admin status")
    return toggle_superadmin_admin_account_status(admin_id=admin_id, request=request)


@router.get("/superadmin/documents")
async def get_superadmin_documents(
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    _require_super_admin(current_user, "view documents")
    return get_superadmin_document_groups(search=search)
