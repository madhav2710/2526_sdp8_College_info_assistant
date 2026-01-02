import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient
from main import app
import pytest
from unittest.mock import MagicMock, patch

client = TestClient(app)

def test_login_success():
    # Mock supabase auth sign_in_with_password
    with patch("main.supabase.auth.sign_in_with_password") as mock_signin:
        mock_signin.return_value = MagicMock(
            user=MagicMock(id="test-user-id", email="test@college.edu"),
            session=MagicMock(access_token="test-access-token")
        )
        
        # We also need to mock the profile lookup which we'll implement
        with patch("main.supabase.table") as mock_table:
            mock_table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"role": "student", "college_id": "test-college-id"}]
            )

            response = client.post("/auth/login", json={
                "email": "test@college.edu",
                "password": "password123"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert data["role"] == "student"

def test_login_invalid_credentials():
    with patch("main.supabase.auth.sign_in_with_password") as mock_signin:
        # Simulate Supabase error for invalid credentials
        mock_signin.side_effect = Exception("Invalid login credentials")
        
        response = client.post("/auth/login", json={
            "email": "wrong@college.edu",
            "password": "wrongpassword"
        })
        
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid login credentials"
