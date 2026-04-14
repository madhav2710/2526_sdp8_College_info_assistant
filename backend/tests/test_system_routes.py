import os
import sys
import types
from unittest.mock import AsyncMock, patch

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

    def order(self, *args, **kwargs):
        return self

    def execute(self):
        return types.SimpleNamespace(data=[])


setattr(supabase_module, "Client", _Client)
setattr(supabase_module, "create_client", lambda *args, **kwargs: _Client())
sys.modules.setdefault("supabase", supabase_module)
sys.modules.setdefault("google", google_module)
sys.modules.setdefault("google.generativeai", google_generativeai_module)

from app.core.auth import get_current_user
from app.routers.system import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


async def mock_super_admin_user():
    return {"user_id": "user-1", "role": "super_admin", "college_id": None}


async def mock_college_admin_user():
    return {"user_id": "user-2", "role": "college_admin", "college_id": "college-1"}


async def mock_student_user():
    return {"user_id": "user-3", "role": "student", "college_id": "college-1"}


def test_root_route():
    with patch("app.routers.system.get_root_payload") as mock_root_payload:
        mock_root_payload.return_value = {
            "app": "College Platform API",
            "status": "ok",
            "version": "1.0.0",
        }
        response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "app": "College Platform API",
        "status": "ok",
        "version": "1.0.0",
    }


def test_list_public_colleges_success():
    with patch(
        "app.routers.system.list_public_colleges_payload"
    ) as mock_list_public_colleges:
        mock_list_public_colleges.return_value = {
            "colleges": [
                {
                    "id": "college-1",
                    "name": "Alpha College",
                    "domain": "alpha.edu",
                    "code": "ALP",
                }
            ]
        }
        response = client.get("/public/colleges")

    assert response.status_code == 200
    assert response.json() == {
        "colleges": [
            {
                "id": "college-1",
                "name": "Alpha College",
                "domain": "alpha.edu",
                "code": "ALP",
            }
        ]
    }


def test_get_config_status_requires_super_admin():
    app.dependency_overrides[get_current_user] = mock_student_user

    response = client.get("/config/status")

    app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json() == {"detail": "Not authorized to view configuration status"}


def test_get_config_status_success():
    app.dependency_overrides[get_current_user] = mock_super_admin_user

    with patch("app.routers.system.get_configuration_status") as mock_get_config_status:
        mock_get_config_status.return_value = {
            "status": "success",
            "configuration_status": "valid",
            "validation_errors": [],
            "config_summary": {"debug": False},
            "timestamp": "2026-04-05T00:00:00+00:00",
        }
        response = client.get("/config/status")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["configuration_status"] == "valid"
    assert body["validation_errors"] == []
    assert body["config_summary"] == {"debug": False}
    assert "timestamp" in body


def test_validate_config_success():
    app.dependency_overrides[get_current_user] = mock_super_admin_user

    with patch(
        "app.routers.system.validate_configuration"
    ) as mock_validate_configuration:
        mock_validate_configuration.return_value = {
            "status": "success",
            "is_valid": True,
            "validation_errors": [],
            "error_count": 0,
            "timestamp": "2026-04-05T00:00:00+00:00",
        }
        response = client.post("/config/validate")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["is_valid"] is True
    assert body["validation_errors"] == []
    assert body["error_count"] == 0
    assert "timestamp" in body


def test_get_system_health_success():
    app.dependency_overrides[get_current_user] = mock_college_admin_user

    with patch(
        "app.routers.system.get_current_system_health",
        new=AsyncMock(
            return_value={
                "status": "success",
                "system_health": {"rag": {"healthy": True}},
                "timestamp": "2026-04-05T00:00:00+00:00",
            }
        ),
    ):
        response = client.get("/system/health")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["system_health"] == {"rag": {"healthy": True}}
    assert "timestamp" in body


def test_reset_system_health_requires_super_admin():
    app.dependency_overrides[get_current_user] = mock_college_admin_user

    response = client.post("/system/health/reset")

    app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json() == {"detail": "Not authorized to reset system health"}


def test_reset_system_health_success():
    app.dependency_overrides[get_current_user] = mock_super_admin_user

    with patch(
        "app.routers.system.reset_current_system_health",
        new=AsyncMock(
            return_value={
                "status": "success",
                "reset_result": {"status": "success", "services_reset": 2},
                "timestamp": "2026-04-05T00:00:00+00:00",
            }
        ),
    ):
        response = client.post("/system/health/reset", params={"service_name": "rag"})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["reset_result"] == {"status": "success", "services_reset": 2}
    assert "timestamp" in body
