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

def test_upload_document_success():
    if get_current_user is None:
        pytest.fail("Dependency get_current_user not found")

    college_id = "test-college-id"
    filename = "syllabus.pdf"

    app.dependency_overrides[get_current_user] = mock_admin_user

    # Patch the supabase client instance in main
    with patch("main.supabase") as mock_supabase:
        
        # Mock Storage
        mock_supabase.storage.from_.return_value.upload.return_value = {"path": f"{college_id}/{filename}"}

        # Mock DB
        mock_exe = MagicMock()
        mock_exe.data = [{"id": "doc-123", "filename": filename, "status": "processing"}]
        mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_exe

        files = {"file": (filename, b"fake pdf content", "application/pdf")}
        response = client.post(
            "/admin/upload",
            files=files,
            data={"college_id": college_id}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "Upload successful"
        assert "document_id" in response.json()

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
