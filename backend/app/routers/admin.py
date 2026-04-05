from typing import Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from app.core.auth import get_current_user
from app.services.document_service import (
    get_admin_documents,
    get_admin_query_history,
    trigger_manual_rag_processing_for_admin,
    upload_document_for_admin,
)

router = APIRouter()


def _require_college_admin(current_user: dict, action: str) -> str:
    if current_user["role"] != "college_admin":
        raise HTTPException(status_code=403, detail=f"Not authorized to {action}")

    target_college_id = current_user.get("college_id")
    if not target_college_id:
        raise HTTPException(
            status_code=400, detail="User is not associated with a college"
        )

    return target_college_id


@router.post("/admin/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    college_id: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    _require_college_admin(current_user, "upload documents")
    return await upload_document_for_admin(file=file, current_user=current_user)


@router.get("/admin/documents")
async def get_documents(
    status: Optional[str] = None,
    sort_by: Optional[str] = "created_at",
    sort_order: Optional[str] = "desc",
    current_user: dict = Depends(get_current_user),
):
    _require_college_admin(current_user, "view documents")
    return get_admin_documents(
        college_id=current_user["college_id"],
        user_id=current_user["user_id"],
        status=status,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/admin/query-history")
async def get_query_history(
    limit: Optional[int] = 10, current_user: dict = Depends(get_current_user)
):
    _require_college_admin(current_user, "view query history")
    return get_admin_query_history(
        college_id=current_user["college_id"],
        limit=limit,
    )


@router.post("/admin/trigger-rag-processing")
async def trigger_manual_rag_processing(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    _require_college_admin(current_user, "trigger RAG processing")
    return await trigger_manual_rag_processing_for_admin(
        document_id=document_id,
        current_user=current_user,
        background_tasks=background_tasks,
    )
