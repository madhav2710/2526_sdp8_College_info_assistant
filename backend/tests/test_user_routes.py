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
        self.auth = types.SimpleNamespace(admin=types.SimpleNamespace())

    def table(self, *args, **kwargs):
        return self

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def update(self, *args, **kwargs):
        return self

    def execute(self):
        return types.SimpleNamespace(data=[])


setattr(supabase_module, "Client", _Client)
setattr(supabase_module, "create_client", lambda *args, **kwargs: _Client())
sys.modules.setdefault("supabase", supabase_module)
sys.modules.setdefault("google", google_module)
sys.modules.setdefault("google.generativeai", google_generativeai_module)

from app.core.auth import get_current_user
from app.routers.user import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


async def mock_user():
    return {"user_id": "user-1", "role": "student", "college_id": None}


def test_get_user_profile_success():
    app.dependency_overrides[get_current_user] = mock_user
    with patch(
        "app.routers.user.get_user_profile_for_current_user"
    ) as mock_get_user_profile:
        mock_get_user_profile.return_value = {
            "user_id": "user-1",
            "email": "student@example.edu",
            "full_name": "Student One",
            "role": "student",
            "college_id": "college-1",
            "college_name": "Alpha College",
        }
        response = client.get("/user/profile")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "user-1",
        "email": "student@example.edu",
        "full_name": "Student One",
        "role": "student",
        "college_id": "college-1",
        "college_name": "Alpha College",
    }


def test_get_user_profile_not_found():
    app.dependency_overrides[get_current_user] = mock_user
    with patch(
        "app.routers.user.get_user_profile_for_current_user"
    ) as mock_get_user_profile:
        mock_get_user_profile.side_effect = HTTPException(
            status_code=404, detail="User profile not found"
        )
        response = client.get("/user/profile")

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "User profile not found"}


def test_set_user_college_success():
    app.dependency_overrides[get_current_user] = mock_user
    with patch(
        "app.routers.user.set_user_college_for_current_user"
    ) as mock_set_college:
        mock_set_college.return_value = {"status": "success", "college_id": "college-1"}
        response = client.post("/user/set-college", json={"college_id": "college-1"})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "success", "college_id": "college-1"}


def test_set_user_college_invalid_college():
    app.dependency_overrides[get_current_user] = mock_user
    with patch(
        "app.routers.user.set_user_college_for_current_user"
    ) as mock_set_college:
        mock_set_college.side_effect = HTTPException(
            status_code=400, detail="Invalid college selected"
        )
        response = client.post(
            "/user/set-college", json={"college_id": "missing-college"}
        )

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid college selected"}
