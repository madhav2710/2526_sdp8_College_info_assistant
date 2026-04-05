import os
import sys
import types
from unittest.mock import patch

from fastapi import HTTPException
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
        self.auth = types.SimpleNamespace(
            admin=types.SimpleNamespace(),
            sign_in_with_password=lambda *args, **kwargs: None,
            sign_up=lambda *args, **kwargs: None,
        )

    def table(self, *args, **kwargs):
        return self

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def insert(self, *args, **kwargs):
        return self

    def execute(self):
        return types.SimpleNamespace(data=[])


setattr(supabase_module, "Client", _Client)
setattr(supabase_module, "create_client", lambda *args, **kwargs: _Client())
sys.modules["supabase"] = supabase_module
sys.modules["google"] = google_module
sys.modules["google.generativeai"] = google_generativeai_module

import app.routers.auth as auth_router_module

router = auth_router_module.router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_login_success():
    with patch("app.routers.auth.login_user_account") as mock_login:
        mock_login.return_value = {
            "access_token": "test-access-token",
            "token_type": "bearer",
            "user_id": "test-user-id",
            "email": "test@college.edu",
            "full_name": "Test Student",
            "role": "student",
            "college_id": "test-college-id",
        }

        response = client.post(
            "/auth/login",
            json={
                "email": "test@college.edu",
                "password": "password123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["role"] == "student"
        assert data["full_name"] == "Test Student"


def test_login_invalid_credentials():
    with patch("app.routers.auth.login_user_account") as mock_login:
        mock_login.side_effect = HTTPException(
            status_code=401, detail="Invalid login credentials"
        )

        response = client.post(
            "/auth/login",
            json={
                "email": "wrong@college.edu",
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid login credentials"


def test_signup_success():
    with patch("app.routers.auth.signup_user_account") as mock_signup:
        mock_signup.return_value = {
            "message": "Signup successful! Please check your email to confirm your account before logging in.",
            "email_sent": True,
        }

        response = client.post(
            "/auth/signup",
            json={
                "email": "new@college.edu",
                "password": "password123",
                "full_name": "New Student",
            },
        )

        assert response.status_code == 200
        assert response.json() == {
            "message": "Signup successful! Please check your email to confirm your account before logging in.",
            "email_sent": True,
        }


def test_signup_duplicate_email():
    with patch("app.routers.auth.signup_user_account") as mock_signup:
        mock_signup.side_effect = HTTPException(
            status_code=400, detail="An account with this email already exists"
        )

        response = client.post(
            "/auth/signup",
            json={
                "email": "existing@college.edu",
                "password": "password123",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "An account with this email already exists"


def test_signup_invalid_college():
    with patch("app.routers.auth.signup_user_account") as mock_signup:
        mock_signup.side_effect = HTTPException(
            status_code=400, detail="Invalid college selected"
        )

        response = client.post(
            "/auth/signup",
            json={
                "email": "new@college.edu",
                "password": "password123",
                "college_id": "missing-college",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid college selected"


def test_login_profile_not_found():
    with patch("app.routers.auth.login_user_account") as mock_login:
        mock_login.side_effect = HTTPException(
            status_code=404, detail="User profile not found"
        )

        response = client.post(
            "/auth/login",
            json={
                "email": "test@college.edu",
                "password": "password123",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "User profile not found"
