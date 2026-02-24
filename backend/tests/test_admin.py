import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient
from main import app
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

# We'll try to import the dependency.
try:
    from app.core.auth import get_current_user
except ImportError:
    get_current_user = None

client = TestClient(app)

# Mock users
def mock_admin_user():
    return {
        "user_id": "admin-user-id",
        "role": "college_admin",
        "college_id": "test-college-id"
    }

def mock_student_user():
    return {
        "user_id": "student-user-id",
        "role": "student",
        "college_id": "test-college-id"
    }

def mock_super_admin_user():
    return {
        "user_id": "super-admin-user-id",
        "role": "super_admin",
        "college_id": None
    }

def test_upload_document_success():
    if get_current_user is None:
        pytest.fail("Dependency get_current_user not found")

    college_id = "test-college-id"
    filename = "syllabus.pdf"

    app.dependency_overrides[get_current_user] = mock_admin_user

    # Mock the httpx client for storage and database operations
    with patch("httpx.AsyncClient") as mock_httpx:
        mock_client = MagicMock()
        mock_httpx.return_value.__aenter__.return_value = mock_client
        mock_httpx.return_value.__aexit__.return_value = None
        
        # Mock storage upload response
        mock_storage_response = MagicMock()
        mock_storage_response.status_code = 201
        
        # Mock database insert response
        mock_db_response = MagicMock()
        mock_db_response.status_code = 201
        mock_db_response.json.return_value = [{
            "id": "doc-123",
            "filename": filename,
            "file_type": "pdf",
            "file_size": 16,  # Length of "fake pdf content"
            "status": "pending_approval",  # Updated to match new workflow
            "created_at": "2024-01-04T10:00:00Z"
        }]
        
        # Configure mock to return different responses for different calls
        def mock_post_side_effect(url, **kwargs):
            if "storage" in url:
                return mock_storage_response
            else:  # database call
                return mock_db_response
        
        # Make the post method async
        async def async_post(*args, **kwargs):
            return mock_post_side_effect(*args, **kwargs)
        
        mock_client.post = async_post

        files = {"file": (filename, b"fake pdf content", "application/pdf")}
        response = client.post(
            "/admin/upload",
            files=files,
            data={"college_id": college_id}
        )

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "success"
        assert response_data["message"] == "Document uploaded successfully. Awaiting super admin approval."
        assert "document" in response_data
        assert response_data["document"]["id"] == "doc-123"
        assert response_data["document"]["filename"] == filename
        assert response_data["document"]["status"] == "pending_approval"  # Updated to match new workflow
        assert response_data["document"]["file_size"] == 16

    app.dependency_overrides = {}

def test_get_documents_with_statistics():
    if get_current_user is None:
        pytest.fail("Dependency get_current_user not found")

    app.dependency_overrides[get_current_user] = mock_admin_user

    # Mock the httpx client and service client
    with patch("app.legacy_main.get_service_client") as mock_get_service_client:
        mock_client = MagicMock()
        mock_get_service_client.return_value = mock_client
        
        # Mock documents query
        mock_docs_response = MagicMock()
        mock_docs_response.data = [
            {"id": "doc-1", "filename": "test1.pdf", "status": "uploaded"},
            {"id": "doc-2", "filename": "test2.pdf", "status": "completed"}
        ]
        
        # Mock statistics query
        mock_stats_response = MagicMock()
        mock_stats_response.data = [
            {"status": "uploaded"},
            {"status": "completed"}
        ]
        
        # Mock college query
        mock_college_response = MagicMock()
        mock_college_response.data = [{"name": "Test College"}]
        
        # Mock profile query
        mock_profile_response = MagicMock()
        mock_profile_response.data = [{
            "id": "admin-user-id",
            "email": "admin@test.edu",
            "role": "college_admin",
            "college_id": "test-college-id"
        }]
        
        # Configure the mock client to return different responses based on table
        def mock_table_side_effect(table_name):
            mock_table = MagicMock()
            if table_name == "documents":
                # First call is for documents, second is for statistics
                mock_table.select.return_value.eq.return_value.order.return_value.execute.return_value = mock_docs_response
                # For statistics call, return stats response
                mock_table.select.return_value.eq.return_value.execute.return_value = mock_stats_response
            elif table_name == "colleges":
                mock_table.select.return_value.eq.return_value.execute.return_value = mock_college_response
            elif table_name == "profiles":
                mock_table.select.return_value.eq.return_value.execute.return_value = mock_profile_response
            return mock_table
        
        mock_client.table.side_effect = mock_table_side_effect

        response = client.get("/admin/documents")

        assert response.status_code == 200
        response_data = response.json()
        assert "documents" in response_data
        assert "statistics" in response_data
        assert "college_info" in response_data
        assert "user_profile" in response_data
        assert response_data["statistics"]["total"] == 2
        assert response_data["statistics"]["uploaded"] == 1
        assert response_data["statistics"]["completed"] == 1
        assert response_data["college_info"]["name"] == "Test College"

    app.dependency_overrides = {}

def test_get_query_history():
    if get_current_user is None:
        pytest.fail("Dependency get_current_user not found")

    app.dependency_overrides[get_current_user] = mock_admin_user

    with patch("app.legacy_main.get_service_client") as mock_get_service_client:
        mock_client = MagicMock()
        mock_get_service_client.return_value = mock_client
        
        # Mock conversations query response
        mock_conversations_response = MagicMock()
        mock_conversations_response.data = [
            {
                "id": "conv-1",
                "title": "Test Conversation 1",
                "created_at": "2024-01-04T10:00:00Z",
                "messages": [
                    {"content": "What are the admission requirements?", "role": "user", "created_at": "2024-01-04T10:00:00Z"},
                    {"content": "Here are the admission requirements...", "role": "assistant", "created_at": "2024-01-04T10:01:00Z"}
                ]
            },
            {
                "id": "conv-2", 
                "title": "Test Conversation 2",
                "created_at": "2024-01-04T09:00:00Z",
                "messages": [
                    {"content": "Tell me about the computer science program", "role": "user", "created_at": "2024-01-04T09:00:00Z"}
                ]
            }
        ]
        
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_conversations_response

        response = client.get("/admin/query-history?limit=5")

        assert response.status_code == 200
        response_data = response.json()
        assert "query_history" in response_data
        assert "total_conversations" in response_data
        assert len(response_data["query_history"]) == 2
        assert response_data["query_history"][0]["query"] == "What are the admission requirements?"
        assert response_data["query_history"][1]["query"] == "Tell me about the computer science program"
        assert response_data["total_conversations"] == 2

    app.dependency_overrides = {}

def test_upload_document_unauthorized():
    # Provide file so we don't get 422 Validation Error
    files = {"file": ("syllabus.pdf", b"fake pdf content", "application/pdf")}
    response = client.post("/admin/upload", files=files)
    # Should be 401 Unauthorized
    assert response.status_code == 401

def test_upload_document_forbidden():
    if get_current_user is None:
        pytest.fail("Dependency get_current_user not found")

    app.dependency_overrides[get_current_user] = mock_student_user
    
    files = {"file": ("syllabus.pdf", b"fake pdf content", "application/pdf")}
    response = client.post(
        "/admin/upload", 
        files=files,
        data={"college_id": "test-college-id"}
    )
    
    assert response.status_code == 403
    
    app.dependency_overrides = {}

def test_get_pending_documents_success():
    if get_current_user is None:
        pytest.fail("Dependency get_current_user not found")

    app.dependency_overrides[get_current_user] = mock_super_admin_user

    with patch("app.legacy_main.get_service_client") as mock_get_service_client:
        mock_client = MagicMock()
        mock_get_service_client.return_value = mock_client
        
        # Mock pending documents query response
        mock_pending_response = MagicMock()
        mock_pending_response.data = [
            {
                "id": "doc-1",
                "filename": "test1.pdf",
                "file_type": "pdf",
                "file_size": 1024,
                "college_id": "college-1",
                "uploaded_by": "admin-1",
                "created_at": "2024-01-04T10:00:00Z"
            }
        ]
        
        # Mock college query response
        mock_college_response = MagicMock()
        mock_college_response.data = [{"name": "Test College"}]
        
        # Mock profile query response
        mock_profile_response = MagicMock()
        mock_profile_response.data = [{"email": "admin@test.edu"}]
        
        # Configure the mock client to return different responses based on table
        def mock_table_side_effect(table_name):
            mock_table = MagicMock()
            if table_name == "documents":
                mock_table.select.return_value.in_.return_value.order.return_value.execute.return_value = mock_pending_response
            elif table_name == "colleges":
                mock_table.select.return_value.eq.return_value.execute.return_value = mock_college_response
            elif table_name == "profiles":
                mock_table.select.return_value.eq.return_value.execute.return_value = mock_profile_response
            return mock_table
        
        mock_client.table.side_effect = mock_table_side_effect

        response = client.get("/super-admin/pending-documents")

        assert response.status_code == 200
        response_data = response.json()
        assert "pending_documents" in response_data
        assert "total_pending" in response_data
        assert len(response_data["pending_documents"]) == 1
        assert response_data["pending_documents"][0]["filename"] == "test1.pdf"
        assert response_data["pending_documents"][0]["college_name"] == "Test College"
        assert response_data["pending_documents"][0]["uploader_email"] == "admin@test.edu"
        assert response_data["total_pending"] == 1

    app.dependency_overrides = {}

def test_approve_document_success():
    if get_current_user is None:
        pytest.fail("Dependency get_current_user not found")

    app.dependency_overrides[get_current_user] = mock_super_admin_user

    with patch("app.legacy_main.get_service_client") as mock_get_service_client:
        mock_client = MagicMock()
        mock_get_service_client.return_value = mock_client
        
        # Mock document query response
        mock_doc_response = MagicMock()
        mock_doc_response.data = [{
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "filename": "test.pdf",
            "status": "pending_approval",
            "college_id": "college-1"
        }]
        
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_doc_response

        # Mock the httpx client for database operations
        with patch("httpx.AsyncClient") as mock_httpx:
            mock_http_client = MagicMock()
            mock_httpx.return_value.__aenter__.return_value = mock_http_client
            mock_httpx.return_value.__aexit__.return_value = None
            
            # Mock database update response
            mock_update_response = MagicMock()
            mock_update_response.status_code = 200
            mock_update_response.json.return_value = [{"id": "550e8400-e29b-41d4-a716-446655440000", "status": "approved"}]
            
            # Mock approval record response
            mock_approval_response = MagicMock()
            mock_approval_response.status_code = 201
            
            # Configure mock to return different responses for different calls
            def mock_patch_side_effect(url, **kwargs):
                return mock_update_response
            
            def mock_post_side_effect(url, **kwargs):
                return mock_approval_response
            
            # Make the methods async
            async def async_patch(*args, **kwargs):
                return mock_patch_side_effect(*args, **kwargs)
            
            async def async_post(*args, **kwargs):
                return mock_post_side_effect(*args, **kwargs)
            
            mock_http_client.patch = async_patch
            mock_http_client.post = async_post

            # Mock background task processing
            with patch("app.legacy_main.BackgroundTasks.add_task") as mock_add_task:
                response = client.post(
                    "/super-admin/approve-document",
                    json={
                        "document_id": "550e8400-e29b-41d4-a716-446655440000",
                        "comments": "Approved for processing"
                    }
                )

                assert response.status_code == 200
                response_data = response.json()
                assert response_data["status"] == "success"
                assert "approved for processing" in response_data["message"].lower()
                assert response_data["document"]["id"] == "550e8400-e29b-41d4-a716-446655440000"
                assert response_data["document"]["status"] == "approved"
                
                # Verify background task was added
                mock_add_task.assert_called_once()

    app.dependency_overrides = {}

def test_reject_document_success():
    if get_current_user is None:
        pytest.fail("Dependency get_current_user not found")

    app.dependency_overrides[get_current_user] = mock_super_admin_user

    with patch("app.legacy_main.get_service_client") as mock_get_service_client:
        mock_client = MagicMock()
        mock_get_service_client.return_value = mock_client
        
        # Mock document query response
        mock_doc_response = MagicMock()
        mock_doc_response.data = [{
            "id": "550e8400-e29b-41d4-a716-446655440001",
            "filename": "test.pdf",
            "status": "pending_approval",
            "college_id": "college-1"
        }]
        
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_doc_response

        # Mock the httpx client for database operations
        with patch("httpx.AsyncClient") as mock_httpx:
            mock_http_client = MagicMock()
            mock_httpx.return_value.__aenter__.return_value = mock_http_client
            mock_httpx.return_value.__aexit__.return_value = None
            
            # Mock database update response
            mock_update_response = MagicMock()
            mock_update_response.status_code = 200
            mock_update_response.json.return_value = [{"id": "550e8400-e29b-41d4-a716-446655440001", "status": "rejected"}]
            
            # Mock approval record response
            mock_approval_response = MagicMock()
            mock_approval_response.status_code = 201
            
            # Configure mock to return different responses for different calls
            def mock_patch_side_effect(url, **kwargs):
                return mock_update_response
            
            def mock_post_side_effect(url, **kwargs):
                return mock_approval_response
            
            # Make the methods async
            async def async_patch(*args, **kwargs):
                return mock_patch_side_effect(*args, **kwargs)
            
            async def async_post(*args, **kwargs):
                return mock_post_side_effect(*args, **kwargs)
            
            mock_http_client.patch = async_patch
            mock_http_client.post = async_post

            response = client.post(
                "/super-admin/reject-document",
                json={
                    "document_id": "550e8400-e29b-41d4-a716-446655440001",
                    "reason": "Document quality is insufficient"
                }
            )

            assert response.status_code == 200
            response_data = response.json()
            assert response_data["status"] == "success"
            assert "rejected" in response_data["message"].lower()
            assert response_data["document"]["id"] == "550e8400-e29b-41d4-a716-446655440001"
            assert response_data["document"]["status"] == "rejected"
            assert response_data["document"]["rejection_reason"] == "Document quality is insufficient"

    app.dependency_overrides = {}

def test_super_admin_endpoints_unauthorized():
    # Test without authentication
    response = client.get("/super-admin/pending-documents")
    assert response.status_code == 401
    
    response = client.post("/super-admin/approve-document", json={"document_id": "550e8400-e29b-41d4-a716-446655440000"})
    assert response.status_code == 401
    
    response = client.post("/super-admin/reject-document", json={"document_id": "550e8400-e29b-41d4-a716-446655440000", "reason": "test"})
    assert response.status_code == 401

def test_super_admin_endpoints_forbidden():
    if get_current_user is None:
        pytest.fail("Dependency get_current_user not found")

    # Test with college admin (should be forbidden)
    app.dependency_overrides[get_current_user] = mock_admin_user
    
    response = client.get("/super-admin/pending-documents")
    assert response.status_code == 403
    
    response = client.post("/super-admin/approve-document", json={"document_id": "550e8400-e29b-41d4-a716-446655440000"})
    assert response.status_code == 403
    
    response = client.post("/super-admin/reject-document", json={"document_id": "550e8400-e29b-41d4-a716-446655440000", "reason": "test"})
    assert response.status_code == 403
    
    app.dependency_overrides = {}
