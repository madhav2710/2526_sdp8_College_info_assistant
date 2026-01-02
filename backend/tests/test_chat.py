import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient
from main import app
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

client = TestClient(app)

def test_create_chat_message():
    conv_id = str(uuid4())
    user_id = str(uuid4())
    message_content = "Hello, I need the syllabus."
    
    with patch("main.create_client") as mock_supabase_client:
        mock_client = mock_supabase_client.return_value
        
        # 1. Mock conversation check (return empty to trigger creation)
        mock_conv_check = MagicMock()
        mock_conv_check.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_conv_check
        
        # 2. Mock profile lookup (for college_id)
        mock_profile = MagicMock()
        mock_profile.data = [{"college_id": "test-college-id"}]
        # Need to handle different tables in mocks
        def table_mock(name):
            m = MagicMock()
            if name == "messages":
                m.insert.return_value.execute.return_value = MagicMock(data=[{"id": "msg-123"}])
            elif name == "profiles":
                m.select.return_value.eq.return_value.execute.return_value = mock_profile
            elif name == "conversations":
                m.select.return_value.eq.return_value.execute.return_value = mock_conv_check
                m.insert.return_value.execute.return_value = MagicMock(data=[{"id": conv_id}])
            return m
            
        mock_client.table.side_effect = table_mock

        response = client.post("/chat/", json={
            "conversation_id": conv_id,
            "user_id": user_id,
            "role": "user",
            "content": message_content
        })
        
        assert response.status_code == 200
        assert response.json()["status"] == "Message sent"
        assert "mock_response" in response.json()

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
