import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4

# Import the app and create a test client with proper initialization
from main import app
from fastapi.testclient import TestClient

# We'll try to import the dependency.
try:
    from app.core.auth import get_current_user
except ImportError:
    get_current_user = None

client = TestClient(app=app)

def test_create_chat_message():
    """Test the enhanced chat endpoint with proper mocking"""
    conv_id = str(uuid4())
    user_id = str(uuid4())
    message_content = "Hello, I need the syllabus."
    
    if get_current_user is None:
        pytest.fail("Dependency get_current_user not found")

    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id, "role": "user", "college_id": "test-college-id"}

    with patch("main.get_service_client") as mock_get_client, \
        patch("main.get_current_user") as mock_get_current_user, \
        patch("app.core.rag.generate_rag_response", new_callable=AsyncMock) as mock_rag_response:
        
        # Mock authentication
        mock_get_current_user.return_value = {"user_id": user_id, "role": "user"}
        
        # Mock database client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Mock profile lookup (for college_id)
        mock_profile = MagicMock()
        mock_profile.data = [{"college_id": "test-college-id", "role": "user"}]
        
        # Mock conversation check (return empty to trigger creation)
        mock_conv_check = MagicMock()
        mock_conv_check.data = []
        
        # Mock message insertion
        mock_message_insert = MagicMock()
        mock_message_insert.data = [{"id": "msg-123"}]
        
        # Setup table mocks
        def table_mock(name):
            m = MagicMock()
            if name == "messages":
                m.insert.return_value.execute.return_value = mock_message_insert
            elif name == "profiles":
                m.select.return_value.eq.return_value.execute.return_value = mock_profile
            elif name == "conversations":
                m.select.return_value.eq.return_value.execute.return_value = mock_conv_check
                m.insert.return_value.execute.return_value = MagicMock(data=[{"id": conv_id}])
            return m
            
        mock_client.table.side_effect = table_mock
        
        # Mock RAG response
        mock_rag_response.return_value = {
            "response": "Here is the syllabus information you requested.",
            "sources": ["syllabus.pdf"],
            "chunks_used": 2,
            "fallback_used": False
        }

        response = client.post("/chat/", json={
            "conversation_id": conv_id,
            "user_id": user_id,
            "role": "user",
            "content": message_content
        })
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "success"
        assert response_data["role"] == "assistant"
        assert "syllabus information" in response_data["content"]
        assert "sources" in response_data
        assert "metadata" in response_data

    app.dependency_overrides = {}

def test_get_chat_history():
    user_id = str(uuid4())
    
    with patch("main.supabase.table") as mock_table:
        # Create a mock execution result
        mock_exe = MagicMock()
        mock_exe.data = [{"id": "conv-1", "title": "First Chat"}]
        # Mock the chain: table().select().eq().order().execute()
        mock_table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = mock_exe

        response = client.get(f"/chat/history/?user_id={user_id}")
        
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) == 1

def test_chat_rate_limiting():
    """Test that rate limiting works for chat endpoint"""
    conv_id = str(uuid4())
    user_id = str(uuid4())
    message_content = "Test message"
    
    if get_current_user is None:
        pytest.fail("Dependency get_current_user not found")

    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id, "role": "user", "college_id": "test-college-id"}

    with patch("main.get_service_client") as mock_get_client, \
        patch("main.get_current_user") as mock_get_current_user, \
        patch("app.core.rag.generate_rag_response", new_callable=AsyncMock) as mock_rag_response:
        
        # Mock authentication
        mock_get_current_user.return_value = {"user_id": user_id, "role": "user"}
        
        # Mock database client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Mock profile lookup
        mock_profile = MagicMock()
        mock_profile.data = [{"college_id": "test-college-id", "role": "user"}]
        
        # Mock conversation check
        mock_conv_check = MagicMock()
        mock_conv_check.data = []
        
        # Mock message insertion
        mock_message_insert = MagicMock()
        mock_message_insert.data = [{"id": "msg-123"}]
        
        # Setup table mocks
        def table_mock(name):
            m = MagicMock()
            if name == "messages":
                m.insert.return_value.execute.return_value = mock_message_insert
            elif name == "profiles":
                m.select.return_value.eq.return_value.execute.return_value = mock_profile
            elif name == "conversations":
                m.select.return_value.eq.return_value.execute.return_value = mock_conv_check
                m.insert.return_value.execute.return_value = MagicMock(data=[{"id": conv_id}])
            return m
            
        mock_client.table.side_effect = table_mock
        
        # Mock RAG response
        mock_rag_response.return_value = {
            "response": "Test response",
            "sources": [],
            "chunks_used": 0,
            "fallback_used": False
        }
        
        # Clear any existing rate limit cache
        if hasattr(client.app.routes[0].endpoint, 'rate_limit_cache'):
            delattr(client.app.routes[0].endpoint, 'rate_limit_cache')
        
        # Send 11 requests rapidly (should trigger rate limit on 11th)
        for i in range(11):
            response = client.post("/chat/", json={
                "conversation_id": conv_id,
                "user_id": user_id,
                "role": "user",
                "content": f"{message_content} {i}"
            })
            
            if i < 10:
                assert response.status_code == 200
            else:
                assert response.status_code == 429
                assert "Too many requests" in response.json()["detail"]

    app.dependency_overrides = {}
