import datetime as dt
import hashlib
import mimetypes
import os
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.core.config import get_system_config
from app.core.database import get_service_client
from app.core.notifications import notification_manager
from app.models.notification import NotificationType
from fastapi import UploadFile


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
        return False, f"Invalid file type. Allowed types: {', '.join(allowed_mime_types)}"

    if file_ext and file.content_type:
        expected_mime = mimetypes.guess_type(file.filename)[0]
        if expected_mime and expected_mime != file.content_type:
            return (
                False,
                "File type mismatch. Please ensure the file extension matches the file content.",
            )

    if file_ext == ".pdf":
        try:
            from io import BytesIO

            from pypdf import PdfReader

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


async def trigger_rag_processing_with_status_tracking(
    document_id: str,
    filename: str,
    approved_by: str,
) -> None:
    """Run RAG processing and keep document status/notifications in sync."""
    client = get_service_client()

    try:
        client.table("documents").update(
            {
                "status": "processing",
                "processing_started_at": datetime.now(dt.UTC).isoformat(),
                "processing_metadata": {
                    "triggered_by": "document_approval",
                    "approved_by": approved_by,
                    "processing_type": "immediate",
                    "start_time": datetime.now(dt.UTC).isoformat(),
                },
            }
        ).eq("id", document_id).execute()

        from app.core.rag import trigger_rag_processing

        await trigger_rag_processing(document_id)

    except Exception as e:  # noqa: BLE001
        client.table("documents").update(
            {
                "status": "failed",
                "error_message": f"RAG processing failed: {str(e)}",
                "failed_at": datetime.now(dt.UTC).isoformat(),
                "processing_metadata": {
                    "triggered_by": "document_approval",
                    "approved_by": approved_by,
                    "processing_type": "immediate",
                    "error": str(e),
                    "failed_at": datetime.now(dt.UTC).isoformat(),
                },
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
                        "processing_type": "immediate",
                        "failed_at": datetime.now(dt.UTC).isoformat(),
                    },
                )
        except Exception:  # noqa: BLE001
            pass
