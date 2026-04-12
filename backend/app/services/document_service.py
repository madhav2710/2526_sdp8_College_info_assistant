import asyncio
import datetime as dt
import hashlib
import importlib
import logging
import mimetypes
import os
from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

import httpx
from fastapi import BackgroundTasks, HTTPException, UploadFile

from app.core.config import get_system_config
from app.core.database import get_service_client, service_key, url as supabase_url
from app.core.notifications import notification_manager
from app.core.workflow import log_status_change, validate_status_transition
from app.models.notification import NotificationType

logger = logging.getLogger(__name__)

VALID_DOCUMENT_STATUSES = {
    "uploaded",
    "pending_approval",
    "approved",
    "rejected",
    "processing",
    "completed",
    "failed",
}
VALID_DOCUMENT_SORT_FIELDS = {
    "created_at",
    "updated_at",
    "filename",
    "status",
    "file_size",
}
ACTIVE_DUPLICATE_STATUSES = ["pending_approval", "approved", "processing", "completed"]
RETRYABLE_UPLOAD_STATUS_CODES = {500, 502, 503, 504, 520, 522, 524}
MIME_TO_FILE_TYPE = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
}


def get_file_config():
    """Get file configuration from system config."""
    return get_system_config().file


def validate_file(file: UploadFile, file_content: bytes) -> tuple[bool, Optional[str]]:
    """Validate uploaded file using configuration settings."""
    file_config = get_file_config()
    max_file_size = file_config.max_file_size_mb * 1024 * 1024
    allowed_extensions = set(file_config.allowed_file_extensions)

    if len(file_content) > max_file_size:
        return False, f"File exceeds {file_config.max_file_size_mb}MB limit"
    if len(file_content) == 0:
        return False, "File is empty"

    file_ext = None
    if file.filename:
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            return False, f"Only {', '.join(allowed_extensions)} files are allowed"

    allowed_mime_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
    }
    if file.content_type and file.content_type not in allowed_mime_types:
        return (
            False,
            f"Invalid file type. Allowed types: {', '.join(allowed_mime_types)}",
        )

    filename = file.filename
    if file_ext and filename and file.content_type:
        expected_mime = mimetypes.guess_type(filename)[0]
        if expected_mime and expected_mime != file.content_type:
            return (
                False,
                "File type mismatch. Please ensure the file extension matches the file content.",
            )

    if file_ext == ".pdf":
        try:
            from io import BytesIO

            PdfReader = getattr(importlib.import_module("pypdf"), "PdfReader")

            reader = PdfReader(BytesIO(file_content))
            if len(reader.pages) == 0:
                return False, "PDF file appears to be corrupted or empty"
        except ModuleNotFoundError:
            pass
        except Exception as e:  # noqa: BLE001
            return False, f"File validation failed: {str(e)}"

    return True, None


def calculate_file_hash(file_content: bytes) -> str:
    return hashlib.sha256(file_content).hexdigest()


def _sanitize_filename(original_filename: str) -> str:
    return "".join(c for c in original_filename if c.isalnum() or c in "._- ")


async def _storage_file_exists(storage_path: str) -> bool:
    check_url = f"{supabase_url}/storage/v1/object/documents/{storage_path}"
    headers = {"Authorization": f"Bearer {service_key}"}

    async with httpx.AsyncClient(trust_env=False) as http_client:
        check_response = await http_client.head(
            check_url, headers=headers, timeout=10.0
        )

    return check_response.status_code == 200


async def _ensure_not_duplicate_document(
    client: Any, college_id: str, file_hash: str
) -> None:
    existing_docs = (
        client.table("documents")
        .select("id, storage_path, status")
        .eq("college_id", college_id)
        .eq("file_hash", file_hash)
        .in_("status", ACTIVE_DUPLICATE_STATUSES)
        .execute()
    )

    for document in existing_docs.data or []:
        storage_path = document.get("storage_path")
        if not storage_path:
            continue

        try:
            if await _storage_file_exists(storage_path):
                raise HTTPException(
                    status_code=400,
                    detail="A file with identical content already exists. Please upload a different file.",
                )
        except HTTPException:
            raise
        except Exception:
            continue


async def _upload_file_to_storage(
    storage_path: str,
    file_content: bytes,
    content_type: Optional[str],
) -> None:
    storage_url = f"{supabase_url}/storage/v1/object/documents/{storage_path}"
    headers = {
        "Authorization": f"Bearer {service_key}",
        "ApiKey": service_key,
        "Content-Type": content_type,
        "x-upsert": "true",
    }

    last_upload_error: Exception | None = None

    for attempt in range(1, 4):
        try:
            async with httpx.AsyncClient(trust_env=False) as http_client:
                response = await http_client.post(
                    storage_url,
                    content=file_content,
                    headers=headers,
                    timeout=60.0,
                )

            if response.status_code in {200, 201}:
                return

            if response.status_code in RETRYABLE_UPLOAD_STATUS_CODES and attempt < 3:
                await asyncio.sleep(0.5 * attempt)
                continue

            raise HTTPException(
                status_code=400, detail=f"File upload failed: {response.text}"
            )
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
            last_upload_error = exc
            if attempt < 3:
                await asyncio.sleep(0.5 * attempt)
                continue
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            last_upload_error = exc
            if attempt < 3:
                await asyncio.sleep(0.5 * attempt)
                continue

    logger.error(
        "Storage upload failed after retries for path %s: %s",
        storage_path,
        last_upload_error,
    )
    raise HTTPException(
        status_code=502,
        detail="Could not connect to Supabase Storage. Please retry in a few seconds.",
    )


async def _delete_storage_file(storage_path: str) -> None:
    delete_url = f"{supabase_url}/storage/v1/object/documents/{storage_path}"
    headers = {"Authorization": f"Bearer {service_key}"}

    async with httpx.AsyncClient(trust_env=False) as http_client:
        await http_client.delete(delete_url, headers=headers, timeout=10.0)


async def _insert_document_record(document_data: dict[str, Any]) -> dict[str, Any]:
    db_url = f"{supabase_url}/rest/v1/documents"
    db_headers = {
        "Authorization": f"Bearer {service_key}",
        "ApiKey": service_key,
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    async with httpx.AsyncClient(trust_env=False) as http_client:
        response = await http_client.post(
            db_url,
            json=document_data,
            headers=db_headers,
            timeout=10.0,
        )

    if response.status_code not in {200, 201}:
        raise HTTPException(status_code=500, detail=f"Database error: {response.text}")

    db_data = response.json()
    document_record = db_data[0] if db_data else None
    if not document_record:
        raise HTTPException(status_code=500, detail="Failed to create document record")

    return document_record


async def upload_document_for_admin(
    file: UploadFile, current_user: dict
) -> dict[str, Any]:
    target_college_id = current_user["college_id"]
    storage_path: str | None = None

    try:
        client = get_service_client()
        file_content = await file.read()
        file_size = len(file_content)

        is_valid, error_msg = validate_file(file, file_content)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        file_hash = calculate_file_hash(file_content)
        await _ensure_not_duplicate_document(client, target_college_id, file_hash)

        original_filename = file.filename or "document"
        safe_filename = _sanitize_filename(original_filename)
        generated_filename = f"{uuid4()}_{safe_filename}"
        storage_path = f"{target_college_id}/{generated_filename}"

        await _upload_file_to_storage(storage_path, file_content, file.content_type)

        content_type = file.content_type or ""
        document_record = await _insert_document_record(
            {
                "college_id": target_college_id,
                "filename": original_filename,
                "storage_path": storage_path,
                "file_type": MIME_TO_FILE_TYPE.get(content_type, "other"),
                "file_size": file_size,
                "uploaded_by": current_user["user_id"],
                "status": "pending_approval",
                "file_hash": file_hash,
                "validated_at": datetime.now(dt.UTC).isoformat(),
                "process_schedule": "immediate",
                "upload_metadata": {
                    "original_filename": original_filename,
                    "content_type": file.content_type,
                    "upload_timestamp": datetime.now(dt.UTC).isoformat(),
                    "uploaded_by": current_user["user_id"],
                    "rag_processing_enabled": True,
                },
            }
        )

        try:
            log_status_change(
                client=client,
                document_id=document_record["id"],
                old_status="uploaded",
                new_status="pending_approval",
                changed_by=current_user["user_id"],
                comments="Document uploaded",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to log upload status change: %s", str(exc))

        try:
            super_admin_response = (
                client.table("profiles")
                .select("id")
                .eq("role", "super_admin")
                .execute()
            )
            super_admin_ids = [
                UUID(admin["id"]) for admin in (super_admin_response.data or [])
            ]

            if super_admin_ids:
                await notification_manager.create_document_notification(
                    recipient_ids=super_admin_ids,
                    notification_type=NotificationType.DOCUMENT_UPLOADED,
                    document_id=UUID(document_record["id"]),
                    document_filename=document_record["filename"],
                    additional_metadata={
                        "college_id": target_college_id,
                        "uploaded_by": current_user["user_id"],
                    },
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to create upload notification: %s", str(exc))

        return {
            "status": "success",
            "message": "Document uploaded successfully. Awaiting super admin approval.",
            "document": {
                "id": document_record["id"],
                "filename": document_record["filename"],
                "file_type": document_record["file_type"],
                "file_size": document_record["file_size"],
                "status": document_record["status"],
                "uploaded_at": document_record["created_at"],
            },
        }
    except HTTPException as exc:
        if storage_path is not None:
            try:
                await _delete_storage_file(storage_path)
            except Exception as cleanup_error:  # noqa: BLE001
                logger.warning(
                    "Failed to cleanup orphaned file %s: %s",
                    storage_path,
                    str(cleanup_error),
                )
        raise exc
    except Exception as exc:  # noqa: BLE001
        if storage_path is not None:
            try:
                await _delete_storage_file(storage_path)
            except Exception as cleanup_error:  # noqa: BLE001
                logger.warning(
                    "Failed to cleanup orphaned file %s: %s",
                    storage_path,
                    str(cleanup_error),
                )
        raise HTTPException(
            status_code=500, detail=f"Upload failed: {str(exc)}"
        ) from exc


def get_admin_query_history(
    college_id: str, limit: Optional[int] = 10
) -> dict[str, Any]:
    try:
        client = get_service_client()
        response = (
            client.table("conversations")
            .select("id, title, created_at, messages(content, role, created_at)")
            .eq("college_id", college_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        query_history = []
        for conversation in response.data or []:
            user_messages = [
                message
                for message in conversation.get("messages", [])
                if message["role"] == "user"
            ]
            if not user_messages:
                continue

            first_message = user_messages[0]
            content = first_message["content"]
            query_history.append(
                {
                    "id": conversation["id"],
                    "query": content[:100] + "..." if len(content) > 100 else content,
                    "title": conversation["title"],
                    "created_at": conversation["created_at"],
                    "message_count": len(conversation.get("messages", [])),
                }
            )

        return {
            "query_history": query_history,
            "total_conversations": len(response.data or []),
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve query history: {str(exc)}"
        ) from exc


def get_admin_documents(
    college_id: str,
    user_id: str,
    status: Optional[str] = None,
    sort_by: Optional[str] = "created_at",
    sort_order: Optional[str] = "desc",
) -> dict[str, Any]:
    try:
        client = get_service_client()
        documents_query = (
            client.table("documents").select("*").eq("college_id", college_id)
        )

        if status and status in VALID_DOCUMENT_STATUSES:
            documents_query = documents_query.eq("status", status)

        if sort_by in VALID_DOCUMENT_SORT_FIELDS:
            documents_query = documents_query.order(
                sort_by,
                desc=(sort_order or "desc").lower() == "desc",
            )
        else:
            documents_query = documents_query.order("created_at", desc=True)

        documents_response = documents_query.execute()
        documents = []

        for document in documents_response.data or []:
            chunk_count = 0
            rag_ready = False
            processing_progress = None

            if document.get("status") == "completed":
                try:
                    chunk_response = (
                        client.table("document_chunks")
                        .select("id", count="exact")
                        .eq("document_id", document["id"])
                        .execute()
                    )
                    chunk_count = (
                        chunk_response.count
                        if hasattr(chunk_response, "count")
                        else len(chunk_response.data or [])
                    )
                    rag_ready = chunk_count > 0
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Failed to get chunk count for document %s: %s",
                        document["id"],
                        str(exc),
                    )

            processing_metadata = document.get("processing_metadata") or {}
            if document.get("status") == "processing" and processing_metadata:
                processing_progress = {
                    "started_at": processing_metadata.get("start_time"),
                    "triggered_by": processing_metadata.get("triggered_by"),
                    "processing_type": processing_metadata.get("processing_type"),
                    "estimated_completion": None,
                }

            documents.append(
                {
                    **document,
                    "rag_status": {
                        "is_rag_ready": rag_ready,
                        "chunk_count": chunk_count,
                        "processing_progress": processing_progress,
                        "can_be_queried": rag_ready
                        and document.get("status") == "completed",
                    },
                }
            )

        stats_response = (
            client.table("documents")
            .select("status")
            .eq("college_id", college_id)
            .execute()
        )
        statistics = {
            "total": 0,
            "uploaded": 0,
            "pending_approval": 0,
            "approved": 0,
            "rejected": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
            "rag_ready": 0,
            "processing_queue": 0,
        }

        for document in stats_response.data or []:
            document_status = document.get("status", "unknown")
            statistics["total"] += 1
            if document_status in statistics:
                statistics[document_status] += 1
            if document_status == "processing":
                statistics["processing_queue"] += 1

        try:
            rag_stats_response = client.rpc(
                "get_vector_storage_stats", {"target_college_id": college_id}
            ).execute()
            if rag_stats_response.data:
                statistics["rag_ready"] = rag_stats_response.data[0].get(
                    "completed_documents", 0
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to get RAG statistics: %s", str(exc))
            statistics["rag_ready"] = statistics["completed"]

        college_response = (
            client.table("colleges").select("name").eq("id", college_id).execute()
        )
        college_name = (
            college_response.data[0]["name"]
            if college_response.data
            else "Unknown College"
        )

        profile_response = (
            client.table("profiles").select("*").eq("id", user_id).execute()
        )
        user_profile = profile_response.data[0] if profile_response.data else {}

        return {
            "documents": documents,
            "statistics": statistics,
            "college_info": {"id": college_id, "name": college_name},
            "user_profile": {
                "id": user_profile.get("id"),
                "email": user_profile.get("email"),
                "role": user_profile.get("role"),
                "college_id": user_profile.get("college_id"),
            },
            "filters": {
                "status": status,
                "sort_by": sort_by,
                "sort_order": sort_order,
            },
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve documents: {str(exc)}"
        ) from exc


async def trigger_rag_processing_with_status_tracking(
    document_id: str,
    filename: str,
    actor_user_id: str,
    triggered_by: str = "document_approval",
    processing_type: str = "immediate",
) -> None:
    """Run RAG processing and keep document status/notifications in sync."""
    client = get_service_client()
    started_at = datetime.now(dt.UTC).isoformat()
    processing_metadata = {
        "triggered_by": triggered_by,
        "processing_type": processing_type,
        "start_time": started_at,
    }
    if triggered_by == "document_approval":
        processing_metadata["approved_by"] = actor_user_id
    else:
        processing_metadata["triggered_by_user"] = actor_user_id

    try:
        client.table("documents").update(
            {
                "status": "processing",
                "processing_started_at": started_at,
                "processing_metadata": processing_metadata,
            }
        ).eq("id", document_id).execute()

        from app.core.rag import trigger_rag_processing

        await trigger_rag_processing(document_id)

    except Exception as e:  # noqa: BLE001
        failed_at = datetime.now(dt.UTC).isoformat()
        failed_metadata = {
            "triggered_by": triggered_by,
            "processing_type": processing_type,
            "error": str(e),
            "failed_at": failed_at,
        }
        if triggered_by == "document_approval":
            failed_metadata["approved_by"] = actor_user_id
        else:
            failed_metadata["triggered_by_user"] = actor_user_id

        client.table("documents").update(
            {
                "status": "failed",
                "error_message": f"RAG processing failed: {str(e)}",
                "failed_at": failed_at,
                "processing_metadata": failed_metadata,
            }
        ).eq("id", document_id).execute()

        try:
            doc_res = (
                client.table("documents")
                .select("uploaded_by")
                .eq("id", document_id)
                .execute()
            )
            if doc_res.data and doc_res.data[0]["uploaded_by"]:
                await notification_manager.create_document_notification(
                    recipient_ids=[UUID(doc_res.data[0]["uploaded_by"])],
                    notification_type=NotificationType.DOCUMENT_FAILED,
                    document_id=UUID(document_id),
                    document_filename=filename,
                    additional_metadata={
                        "error_message": str(e),
                        "processing_type": processing_type,
                        "failed_at": failed_at,
                    },
                )
        except Exception:  # noqa: BLE001
            pass


def get_pending_documents_for_superadmin() -> dict[str, Any]:
    try:
        client = get_service_client()
        response = (
            client.table("documents")
            .select(
                "id, filename, file_type, file_size, college_id, uploaded_by, created_at"
            )
            .in_("status", ["uploaded", "pending_approval"])
            .order("created_at", desc=False)
            .execute()
        )

        pending_documents = []
        for document in response.data or []:
            college_response = (
                client.table("colleges")
                .select("name")
                .eq("id", document["college_id"])
                .execute()
            )
            uploader_name = "Unknown User"
            if document.get("uploaded_by"):
                uploader_response = (
                    client.table("profiles")
                    .select("full_name")
                    .eq("id", document["uploaded_by"])
                    .execute()
                )
                if uploader_response.data:
                    uploader_name = (
                        uploader_response.data[0].get("full_name") or uploader_name
                    )

            pending_documents.append(
                {
                    "id": document["id"],
                    "filename": document["filename"],
                    "file_type": document["file_type"],
                    "file_size": document["file_size"],
                    "college_id": document["college_id"],
                    "college_name": college_response.data[0]["name"]
                    if college_response.data
                    else "Unknown College",
                    "uploaded_by": document.get("uploaded_by"),
                    "uploader_email": uploader_name,
                    "uploaded_at": document["created_at"],
                }
            )

        return {
            "pending_documents": pending_documents,
            "total_pending": len(pending_documents),
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve pending documents: {str(exc)}"
        ) from exc


def get_scheduled_documents_for_superadmin() -> dict[str, Any]:
    try:
        client = get_service_client()
        response = (
            client.table("documents")
            .select(
                "id, filename, file_type, file_size, college_id, scheduled_at, created_at"
            )
            .eq("process_schedule", "scheduled")
            .eq("status", "approved")
            .order("scheduled_at", desc=False)
            .execute()
        )

        scheduled_documents = []
        for document in response.data or []:
            college_response = (
                client.table("colleges")
                .select("name")
                .eq("id", document["college_id"])
                .execute()
            )
            scheduled_documents.append(
                {
                    "id": document["id"],
                    "filename": document["filename"],
                    "file_type": document["file_type"],
                    "file_size": document["file_size"],
                    "college_id": document["college_id"],
                    "college_name": college_response.data[0]["name"]
                    if college_response.data
                    else "Unknown College",
                    "scheduled_at": document["scheduled_at"],
                    "created_at": document["created_at"],
                }
            )

        return {
            "scheduled_documents": scheduled_documents,
            "total_scheduled": len(scheduled_documents),
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve scheduled documents: {str(exc)}",
        ) from exc


async def approve_document_for_superadmin(
    request: Any,
    current_user: dict,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    try:
        client = get_service_client()
        document_response = (
            client.table("documents")
            .select("*")
            .eq("id", str(request.document_id))
            .execute()
        )
        if not document_response.data:
            raise HTTPException(status_code=404, detail="Document not found")

        document = document_response.data[0]
        current_status = document["status"]
        if not validate_status_transition(current_status, "approved"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status transition from {current_status} to approved",
            )

        if request.process_schedule not in ["immediate", "scheduled", "manual"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid process_schedule. Must be 'immediate', 'scheduled', or 'manual'",
            )

        if request.process_schedule == "scheduled":
            if not request.scheduled_at:
                raise HTTPException(
                    status_code=400,
                    detail="scheduled_at is required when process_schedule is 'scheduled'",
                )
            if request.scheduled_at <= datetime.now(dt.UTC):
                raise HTTPException(
                    status_code=400, detail="scheduled_at must be in the future"
                )

        approved_at = datetime.now(dt.UTC).isoformat()
        new_status = (
            "processing" if request.process_schedule == "immediate" else "approved"
        )
        update_data = {
            "status": new_status,
            "approved_by": current_user["user_id"],
            "approval_comments": request.comments,
            "updated_at": approved_at,
            "process_schedule": request.process_schedule,
            "scheduled_at": request.scheduled_at.isoformat()
            if request.scheduled_at
            else None,
        }
        client.table("documents").update(update_data).eq(
            "id", str(request.document_id)
        ).execute()

        try:
            client.table("document_approvals").insert(
                {
                    "document_id": str(request.document_id),
                    "approved_by": current_user["user_id"],
                    "action": "approved",
                    "comments": request.comments,
                }
            ).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to create approval record: %s", str(exc))

        try:
            log_status_change(
                client=client,
                document_id=str(request.document_id),
                old_status=current_status,
                new_status=new_status,
                changed_by=current_user["user_id"],
                comments=request.comments,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to log status change: %s", str(exc))

        if request.process_schedule == "immediate":
            background_tasks.add_task(
                trigger_rag_processing_with_status_tracking,
                str(request.document_id),
                document["filename"],
                current_user["user_id"],
                "document_approval",
                "immediate",
            )

        try:
            if document.get("uploaded_by"):
                await notification_manager.create_document_notification(
                    recipient_ids=[UUID(document["uploaded_by"])],
                    notification_type=NotificationType.DOCUMENT_APPROVED,
                    document_id=request.document_id,
                    document_filename=document["filename"],
                    additional_metadata={
                        "approved_by": current_user["user_id"],
                        "approval_comments": request.comments,
                    },
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to create approval notification: %s", str(exc))

        return {
            "status": "success",
            "message": f"Document '{document['filename']}' has been approved. Processing: {request.process_schedule}",
            "document": {
                "id": str(request.document_id),
                "filename": document["filename"],
                "status": new_status,
                "process_schedule": request.process_schedule,
                "scheduled_at": request.scheduled_at.isoformat()
                if request.scheduled_at
                else None,
                "approved_by": current_user["user_id"],
                "approval_comments": request.comments,
                "approved_at": approved_at,
            },
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Approval failed: {str(exc)}"
        ) from exc


async def reject_document_for_superadmin(
    request: Any, current_user: dict
) -> dict[str, Any]:
    try:
        client = get_service_client()
        document_response = (
            client.table("documents")
            .select("*")
            .eq("id", str(request.document_id))
            .execute()
        )
        if not document_response.data:
            raise HTTPException(status_code=404, detail="Document not found")

        document = document_response.data[0]
        current_status = document["status"]
        if not validate_status_transition(current_status, "rejected"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status transition from {current_status} to rejected",
            )

        rejected_at = datetime.now(dt.UTC).isoformat()
        update_data = {
            "status": "rejected",
            "approved_by": current_user["user_id"],
            "approval_comments": request.reason,
            "updated_at": rejected_at,
        }
        client.table("documents").update(update_data).eq(
            "id", str(request.document_id)
        ).execute()

        try:
            log_status_change(
                client=client,
                document_id=str(request.document_id),
                old_status=current_status,
                new_status="rejected",
                changed_by=current_user["user_id"],
                comments=request.reason,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to log status change: %s", str(exc))

        try:
            client.table("document_approvals").insert(
                {
                    "document_id": str(request.document_id),
                    "approved_by": current_user["user_id"],
                    "action": "rejected",
                    "comments": request.reason,
                }
            ).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to create rejection record: %s", str(exc))

        try:
            if document.get("uploaded_by"):
                await notification_manager.create_document_notification(
                    recipient_ids=[UUID(document["uploaded_by"])],
                    notification_type=NotificationType.DOCUMENT_REJECTED,
                    document_id=request.document_id,
                    document_filename=document["filename"],
                    additional_metadata={
                        "rejected_by": current_user["user_id"],
                        "rejection_reason": request.reason,
                    },
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to create rejection notification: %s", str(exc))

        return {
            "status": "success",
            "message": f"Document '{document['filename']}' has been rejected",
            "document": {
                "id": str(request.document_id),
                "filename": document["filename"],
                "status": "rejected",
                "rejected_by": current_user["user_id"],
                "rejection_reason": request.reason,
                "rejected_at": rejected_at,
            },
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Rejection failed: {str(exc)}"
        ) from exc


async def schedule_document_processing_for_superadmin(
    request: Any, current_user: dict
) -> dict[str, Any]:
    try:
        client = get_service_client()
        document_response = (
            client.table("documents")
            .select("*")
            .eq("id", str(request.document_id))
            .execute()
        )
        if not document_response.data:
            raise HTTPException(status_code=404, detail="Document not found")

        document = document_response.data[0]
        if document["status"] != "approved":
            raise HTTPException(
                status_code=400,
                detail=(
                    "Document must be approved to schedule processing. "
                    f"Current status: {document['status']}"
                ),
            )
        if request.scheduled_at <= datetime.now(dt.UTC):
            raise HTTPException(
                status_code=400, detail="scheduled_at must be in the future"
            )

        client.table("documents").update(
            {
                "process_schedule": "scheduled",
                "scheduled_at": request.scheduled_at.isoformat(),
                "updated_at": datetime.now(dt.UTC).isoformat(),
            }
        ).eq("id", str(request.document_id)).execute()

        return {
            "status": "success",
            "message": f"Document '{document['filename']}' scheduled for processing",
            "document": {
                "id": str(request.document_id),
                "filename": document["filename"],
                "process_schedule": "scheduled",
                "scheduled_at": request.scheduled_at.isoformat(),
            },
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Scheduling failed: {str(exc)}"
        ) from exc


async def trigger_document_processing_for_superadmin(
    request: Any,
    current_user: dict,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    try:
        client = get_service_client()
        document_response = (
            client.table("documents")
            .select("*")
            .eq("id", str(request.document_id))
            .execute()
        )
        if not document_response.data:
            raise HTTPException(status_code=404, detail="Document not found")

        document = document_response.data[0]
        current_status = document["status"]
        if current_status != "approved":
            raise HTTPException(
                status_code=400,
                detail=f"Document must be approved to trigger processing. Current status: {current_status}",
            )

        client.table("documents").update(
            {
                "status": "processing",
                "process_schedule": "manual",
                "updated_at": datetime.now(dt.UTC).isoformat(),
            }
        ).eq("id", str(request.document_id)).execute()

        try:
            log_status_change(
                client=client,
                document_id=str(request.document_id),
                old_status=current_status,
                new_status="processing",
                changed_by=current_user["user_id"],
                comments="Manual processing trigger",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to log status change: %s", str(exc))

        background_tasks.add_task(
            trigger_rag_processing_with_status_tracking,
            str(request.document_id),
            document["filename"],
            current_user["user_id"],
            "manual_trigger",
            "manual",
        )

        return {
            "status": "success",
            "message": f"Processing triggered for document '{document['filename']}'",
            "document": {
                "id": str(request.document_id),
                "filename": document["filename"],
                "status": "processing",
            },
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Trigger processing failed: {str(exc)}"
        ) from exc


async def trigger_manual_rag_processing_for_admin(
    document_id: UUID,
    current_user: dict,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    try:
        client = get_service_client()
        document_response = (
            client.table("documents")
            .select("*")
            .eq("id", str(document_id))
            .eq("college_id", current_user["college_id"])
            .execute()
        )

        if not document_response.data:
            raise HTTPException(
                status_code=404, detail="Document not found or not accessible"
            )

        document = document_response.data[0]
        current_status = document["status"]
        filename = document["filename"]

        if current_status not in {"approved", "failed"}:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Document must be approved or failed to trigger RAG processing. "
                    f"Current status: {current_status}"
                ),
            )

        triggered_at = datetime.now(dt.UTC).isoformat()
        client.table("documents").update(
            {
                "status": "processing",
                "processing_started_at": triggered_at,
                "processing_metadata": {
                    "triggered_by": "manual_trigger",
                    "triggered_by_user": current_user["user_id"],
                    "processing_type": "manual",
                    "start_time": triggered_at,
                },
            }
        ).eq("id", str(document_id)).execute()

        try:
            log_status_change(
                client=client,
                document_id=str(document_id),
                old_status=current_status,
                new_status="processing",
                changed_by=current_user["user_id"],
                comments="Manual RAG processing triggered",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to log status change: %s", str(exc))

        background_tasks.add_task(
            trigger_rag_processing_with_status_tracking,
            str(document_id),
            filename,
            current_user["user_id"],
        )

        logger.info(
            "Manual RAG processing triggered for document %s (%s) by user %s",
            str(document_id),
            filename,
            current_user["user_id"],
        )

        return {
            "status": "success",
            "message": f"RAG processing started for document '{filename}'",
            "document": {
                "id": str(document_id),
                "filename": filename,
                "status": "processing",
                "triggered_by": current_user["user_id"],
                "triggered_at": triggered_at,
            },
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Failed to trigger manual RAG processing for document %s: %s",
            str(document_id),
            str(exc),
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to trigger RAG processing: {str(exc)}"
        ) from exc
