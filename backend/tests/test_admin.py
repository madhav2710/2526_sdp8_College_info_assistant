import os
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

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

    def in_(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def update(self, *args, **kwargs):
        return self

    def rpc(self, *args, **kwargs):
        return self

    def execute(self):
        return types.SimpleNamespace(data=[])


setattr(supabase_module, "Client", _Client)
setattr(supabase_module, "create_client", lambda *args, **kwargs: _Client())
sys.modules.setdefault("supabase", supabase_module)
sys.modules.setdefault("google", google_module)
sys.modules.setdefault("google.generativeai", google_generativeai_module)

from app.core.auth import get_current_user
from app.routers.admin import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


async def mock_college_admin_user():
    return {
        "user_id": "admin-user-id",
        "role": "college_admin",
        "college_id": "college-1",
    }


async def mock_student_user():
    return {
        "user_id": "student-user-id",
        "role": "student",
        "college_id": "college-1",
    }


def test_upload_document_unauthorized():
    response = client.post(
        "/admin/upload",
        files={"file": ("catalog.txt", b"college handbook", "text/plain")},
    )

    assert response.status_code == 401


def test_upload_document_forbidden():
    app.dependency_overrides[get_current_user] = mock_student_user

    response = client.post(
        "/admin/upload",
        files={"file": ("catalog.txt", b"college handbook", "text/plain")},
        data={"college_id": "college-1"},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json() == {"detail": "Not authorized to upload documents"}


def test_upload_document_success():
    app.dependency_overrides[get_current_user] = mock_college_admin_user
    document_id = str(uuid4())
    super_admin_id = str(uuid4())

    documents_table = MagicMock()
    profiles_table = MagicMock()
    mock_service_client = MagicMock()
    mock_service_client.table.side_effect = lambda table_name: {
        "documents": documents_table,
        "profiles": profiles_table,
    }[table_name]

    documents_table.select.return_value.eq.return_value.eq.return_value.in_.return_value.execute.return_value = SimpleNamespace(
        data=[]
    )
    profiles_table.select.return_value.eq.return_value.execute.return_value = (
        SimpleNamespace(data=[{"id": super_admin_id}])
    )

    storage_response = MagicMock(status_code=201, text="")
    db_response = MagicMock(status_code=201, text="")
    db_response.json.return_value = [
        {
            "id": document_id,
            "filename": "catalog.txt",
            "file_type": "txt",
            "file_size": len(b"college handbook"),
            "status": "pending_approval",
            "created_at": "2024-01-04T10:00:00Z",
        }
    ]

    http_client = MagicMock()
    http_client.post = AsyncMock(side_effect=[storage_response, db_response])

    with (
        patch(
            "app.services.document_service.get_service_client",
            return_value=mock_service_client,
        ),
        patch("app.services.document_service.httpx.AsyncClient") as mock_async_client,
        patch(
            "app.services.document_service.log_status_change"
        ) as mock_log_status_change,
        patch(
            "app.services.document_service.notification_manager.create_document_notification",
            new=AsyncMock(),
        ) as mock_create_notification,
    ):
        mock_async_client.return_value.__aenter__.return_value = http_client
        mock_async_client.return_value.__aexit__.return_value = None

        response = client.post(
            "/admin/upload",
            files={"file": ("catalog.txt", b"college handbook", "text/plain")},
            data={"college_id": "ignored-college-id"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "message": "Document uploaded successfully. Awaiting super admin approval.",
        "document": {
            "id": document_id,
            "filename": "catalog.txt",
            "file_type": "txt",
            "file_size": len(b"college handbook"),
            "status": "pending_approval",
            "uploaded_at": "2024-01-04T10:00:00Z",
        },
    }
    mock_log_status_change.assert_called_once()
    assert mock_create_notification.await_count == 1


def test_get_query_history_success():
    app.dependency_overrides[get_current_user] = mock_college_admin_user
    conversations_table = MagicMock()
    mock_service_client = MagicMock()
    mock_service_client.table.side_effect = lambda table_name: {
        "conversations": conversations_table,
    }[table_name]

    conversations_table.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = SimpleNamespace(
        data=[
            {
                "id": "conv-1",
                "title": "Admissions",
                "created_at": "2024-01-04T10:00:00Z",
                "messages": [
                    {
                        "content": "What are the admission requirements?",
                        "role": "user",
                        "created_at": "2024-01-04T10:00:00Z",
                    },
                    {
                        "content": "Here are the requirements",
                        "role": "assistant",
                        "created_at": "2024-01-04T10:01:00Z",
                    },
                ],
            },
            {
                "id": "conv-2",
                "title": "Programs",
                "created_at": "2024-01-04T09:00:00Z",
                "messages": [
                    {
                        "content": "Tell me about the computer science program",
                        "role": "user",
                        "created_at": "2024-01-04T09:00:00Z",
                    }
                ],
            },
        ]
    )

    with patch(
        "app.services.document_service.get_service_client",
        return_value=mock_service_client,
    ):
        response = client.get("/admin/query-history", params={"limit": 5})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "query_history": [
            {
                "id": "conv-1",
                "query": "What are the admission requirements?",
                "title": "Admissions",
                "created_at": "2024-01-04T10:00:00Z",
                "message_count": 2,
            },
            {
                "id": "conv-2",
                "query": "Tell me about the computer science program",
                "title": "Programs",
                "created_at": "2024-01-04T09:00:00Z",
                "message_count": 1,
            },
        ],
        "total_conversations": 2,
    }


def test_get_documents_with_statistics():
    app.dependency_overrides[get_current_user] = mock_college_admin_user
    documents_table = MagicMock()
    document_chunks_table = MagicMock()
    colleges_table = MagicMock()
    profiles_table = MagicMock()
    mock_service_client = MagicMock()
    mock_service_client.table.side_effect = lambda table_name: {
        "documents": documents_table,
        "document_chunks": document_chunks_table,
        "colleges": colleges_table,
        "profiles": profiles_table,
    }[table_name]

    document_list_response = SimpleNamespace(
        data=[
            {
                "id": "doc-1",
                "filename": "catalog.txt",
                "status": "completed",
                "file_size": 2048,
                "processing_metadata": None,
            },
            {
                "id": "doc-2",
                "filename": "brochure.txt",
                "status": "processing",
                "file_size": 1024,
                "processing_metadata": {
                    "start_time": "2024-01-04T11:00:00Z",
                    "triggered_by": "manual_trigger",
                    "processing_type": "manual",
                },
            },
        ]
    )
    document_stats_response = SimpleNamespace(
        data=[{"status": "completed"}, {"status": "processing"}]
    )

    list_select = MagicMock()
    list_filter = MagicMock()
    stats_select = MagicMock()
    stats_filter = MagicMock()
    documents_table.select.side_effect = lambda fields, **kwargs: (
        list_select if fields == "*" else stats_select
    )
    list_select.eq.return_value = list_filter
    list_filter.order.return_value.execute.return_value = document_list_response
    stats_select.eq.return_value = stats_filter
    stats_filter.execute.return_value = document_stats_response

    document_chunks_table.select.return_value.eq.return_value.execute.return_value = (
        SimpleNamespace(
            data=[{"id": "chunk-1"}, {"id": "chunk-2"}],
            count=2,
        )
    )
    colleges_table.select.return_value.eq.return_value.execute.return_value = (
        SimpleNamespace(data=[{"name": "Test College"}])
    )
    profiles_table.select.return_value.eq.return_value.execute.return_value = (
        SimpleNamespace(
            data=[
                {
                    "id": "admin-user-id",
                    "email": "admin@test.edu",
                    "role": "college_admin",
                    "college_id": "college-1",
                }
            ]
        )
    )
    mock_service_client.rpc.return_value.execute.return_value = SimpleNamespace(
        data=[{"completed_documents": 1}]
    )

    with patch(
        "app.services.document_service.get_service_client",
        return_value=mock_service_client,
    ):
        response = client.get("/admin/documents")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["statistics"] == {
        "total": 2,
        "uploaded": 0,
        "pending_approval": 0,
        "approved": 0,
        "rejected": 0,
        "processing": 1,
        "completed": 1,
        "failed": 0,
        "rag_ready": 1,
        "processing_queue": 1,
    }
    assert body["college_info"] == {"id": "college-1", "name": "Test College"}
    assert body["user_profile"] == {
        "id": "admin-user-id",
        "email": "admin@test.edu",
        "role": "college_admin",
        "college_id": "college-1",
    }
    assert body["documents"][0]["rag_status"] == {
        "is_rag_ready": True,
        "chunk_count": 2,
        "processing_progress": None,
        "can_be_queried": True,
    }
    assert body["documents"][1]["rag_status"] == {
        "is_rag_ready": False,
        "chunk_count": 0,
        "processing_progress": {
            "started_at": "2024-01-04T11:00:00Z",
            "triggered_by": "manual_trigger",
            "processing_type": "manual",
            "estimated_completion": None,
        },
        "can_be_queried": False,
    }


def test_trigger_manual_rag_processing_success():
    app.dependency_overrides[get_current_user] = mock_college_admin_user
    document_id = str(uuid4())
    documents_table = MagicMock()
    mock_service_client = MagicMock()
    mock_service_client.table.side_effect = lambda table_name: {
        "documents": documents_table,
    }[table_name]

    documents_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = SimpleNamespace(
        data=[
            {
                "id": document_id,
                "filename": "catalog.txt",
                "status": "approved",
            }
        ]
    )
    documents_table.update.return_value.eq.return_value.execute.return_value = (
        SimpleNamespace(data=[])
    )

    with (
        patch(
            "app.services.document_service.get_service_client",
            return_value=mock_service_client,
        ),
        patch(
            "app.services.document_service.log_status_change"
        ) as mock_log_status_change,
        patch(
            "app.services.document_service.trigger_rag_processing_with_status_tracking",
            new=AsyncMock(),
        ) as mock_trigger_rag,
    ):
        response = client.post(
            "/admin/trigger-rag-processing",
            params={"document_id": document_id},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["message"] == "RAG processing started for document 'catalog.txt'"
    assert body["document"]["id"] == document_id
    assert body["document"]["filename"] == "catalog.txt"
    assert body["document"]["status"] == "processing"
    assert body["document"]["triggered_by"] == "admin-user-id"
    assert "triggered_at" in body["document"]
    mock_log_status_change.assert_called_once()
    assert mock_trigger_rag.await_count == 1
