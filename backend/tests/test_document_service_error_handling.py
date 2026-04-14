import asyncio
import os
import sys
import types
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch

import pytest
from fastapi import HTTPException

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
os.environ.setdefault("SERVICE_ROLE_KEY", "test-service-key")

supabase_module = types.ModuleType("supabase")
google_module = types.ModuleType("google")
google_generativeai_module = types.ModuleType("google.generativeai")
setattr(google_generativeai_module, "configure", lambda **kwargs: None)
setattr(google_module, "generativeai", google_generativeai_module)


class _Client:
    def __init__(self):
        self.auth = types.SimpleNamespace(admin=types.SimpleNamespace())

    def table(self, *args, **kwargs):
        return self

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def execute(self):
        return types.SimpleNamespace(data=[])


setattr(supabase_module, "Client", _Client)
setattr(supabase_module, "create_client", lambda *args, **kwargs: _Client())
sys.modules.setdefault("supabase", supabase_module)
sys.modules.setdefault("google", google_module)
sys.modules.setdefault("google.generativeai", google_generativeai_module)

from app.services.document_service import (
    approve_document_for_superadmin,
    get_pending_documents_for_superadmin,
    get_scheduled_documents_for_superadmin,
    reject_document_for_superadmin,
    schedule_document_processing_for_superadmin,
    trigger_document_processing_for_superadmin,
    trigger_manual_rag_processing_for_admin,
)


def test_get_pending_documents_hides_internal_errors():
    with patch(
        "app.services.document_service.get_service_client",
        side_effect=Exception("pending documents exploded"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            get_pending_documents_for_superadmin()

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Failed to retrieve pending documents. Please try again."


def test_get_scheduled_documents_hides_internal_errors():
    with patch(
        "app.services.document_service.get_service_client",
        side_effect=Exception("scheduled documents exploded"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            get_scheduled_documents_for_superadmin()

    assert exc_info.value.status_code == 500
    assert (
        exc_info.value.detail
        == "Failed to retrieve scheduled documents. Please try again."
    )


def test_approve_document_hides_internal_errors():
    request = SimpleNamespace(
        document_id=uuid4(),
        comments="Looks good",
        process_schedule="manual",
        scheduled_at=None,
    )
    current_user = {"user_id": "super-admin-1", "role": "super_admin"}

    with patch(
        "app.services.document_service.get_service_client",
        side_effect=Exception("approval exploded"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                approve_document_for_superadmin(
                    request=request,
                    current_user=current_user,
                    background_tasks=SimpleNamespace(add_task=lambda *args, **kwargs: None),
                )
            )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Approval failed. Please try again."


def test_reject_document_hides_internal_errors():
    request = SimpleNamespace(document_id=uuid4(), reason="bad file")
    current_user = {"user_id": "super-admin-1", "role": "super_admin"}

    with patch(
        "app.services.document_service.get_service_client",
        side_effect=Exception("rejection exploded"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                reject_document_for_superadmin(
                    request=request,
                    current_user=current_user,
                )
            )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Rejection failed. Please try again."


def test_schedule_document_processing_hides_internal_errors():
    request = SimpleNamespace(document_id=uuid4(), scheduled_at=SimpleNamespace(isoformat=lambda: "2026-04-14T00:00:00Z"))
    current_user = {"user_id": "super-admin-1", "role": "super_admin"}

    with patch(
        "app.services.document_service.get_service_client",
        side_effect=Exception("schedule exploded"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                schedule_document_processing_for_superadmin(
                    request=request,
                    current_user=current_user,
                )
            )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Scheduling failed. Please try again."


def test_trigger_document_processing_hides_internal_errors():
    request = SimpleNamespace(document_id=uuid4())
    current_user = {"user_id": "super-admin-1", "role": "super_admin"}

    with patch(
        "app.services.document_service.get_service_client",
        side_effect=Exception("trigger exploded"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                trigger_document_processing_for_superadmin(
                    request=request,
                    current_user=current_user,
                    background_tasks=SimpleNamespace(add_task=lambda *args, **kwargs: None),
                )
            )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Trigger processing failed. Please try again."


def test_trigger_manual_rag_processing_hides_internal_errors():
    document_id = uuid4()
    current_user = {"user_id": str(uuid4()), "role": "college_admin"}

    with patch(
        "app.services.document_service.get_service_client",
        side_effect=Exception("manual rag exploded"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                trigger_manual_rag_processing_for_admin(
                    document_id=document_id,
                    current_user=current_user,
                    background_tasks=SimpleNamespace(
                        add_task=lambda *args, **kwargs: None
                    ),
                )
            )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Failed to trigger RAG processing. Please try again."
