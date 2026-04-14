import asyncio
import os
import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
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
            get_user=lambda *args, **kwargs: None,
        )

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

    def insert(self, *args, **kwargs):
        return self

    def upsert(self, *args, **kwargs):
        return self

    def delete(self, *args, **kwargs):
        return self

    def execute(self):
        return types.SimpleNamespace(data=[])


setattr(supabase_module, "Client", _Client)
setattr(supabase_module, "create_client", lambda *args, **kwargs: _Client())
sys.modules.setdefault("supabase", supabase_module)
sys.modules.setdefault("google", google_module)
sys.modules.setdefault("google.generativeai", google_generativeai_module)

from app.core.auth import get_current_user
from app.routers.superadmin import router as superadmin_router
from app.schemas.admin import AdminCreateRequest
from app.schemas.auth import LoginRequest
from app.services.account_service import login_user_account
from app.services.governance_service import (
    create_superadmin_admin_account,
    delete_superadmin_admin_account,
)


@pytest.fixture
def superadmin_client():
    app = FastAPI()
    app.include_router(superadmin_router)

    async def mock_super_admin_user():
        return {"user_id": "super-admin-1", "role": "super_admin", "college_id": None}

    app.dependency_overrides[get_current_user] = mock_super_admin_user
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


def _chainable_table(*, execute_return=None, execute_side_effect=None):
    table = MagicMock()
    table.select.return_value = table
    table.eq.return_value = table
    table.limit.return_value = table
    table.update.return_value = table
    table.insert.return_value = table
    table.upsert.return_value = table
    table.delete.return_value = table
    table.execute.return_value = execute_return or SimpleNamespace(data=[])
    if execute_side_effect is not None:
        table.execute.side_effect = execute_side_effect
    return table


def test_login_user_account_fetches_status_and_denies_disabled_profiles():
    request = LoginRequest(email="admin@example.edu", password="password123")
    auth_response = SimpleNamespace(
        user=SimpleNamespace(id="user-1", email="admin@example.edu"),
        session=SimpleNamespace(access_token="access-token"),
    )
    profiles_table = _chainable_table(
        execute_return=SimpleNamespace(
            data=[
                {
                    "role": "college_admin",
                    "college_id": "college-1",
                    "full_name": "Admin User",
                    "status": "disabled",
                }
            ]
        )
    )

    with patch(
        "app.services.account_service.supabase.auth.sign_in_with_password",
        return_value=auth_response,
        create=True,
    ), patch(
        "app.services.account_service.supabase.table",
        return_value=profiles_table,
    ):
        with pytest.raises(HTTPException) as exc_info:
            login_user_account(request)

    select_clause = profiles_table.select.call_args.args[0]
    assert "status" in select_clause
    assert exc_info.value.status_code == 403
    assert "disabled" in exc_info.value.detail.lower()


def test_get_current_user_fetches_status_and_denies_disabled_profiles():
    profiles_table = _chainable_table(
        execute_return=SimpleNamespace(
            data=[{"role": "college_admin", "college_id": "college-1", "status": "disabled"}]
        )
    )
    auth_response = SimpleNamespace(user=SimpleNamespace(id="user-1"))

    with patch(
        "app.core.auth.supabase.auth.get_user",
        return_value=auth_response,
        create=True,
    ), patch("app.core.auth.supabase.table", return_value=profiles_table):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_current_user(token="valid-token"))

    select_clause = profiles_table.select.call_args.args[0]
    assert "status" in select_clause
    assert exc_info.value.status_code == 403
    assert "disabled" in exc_info.value.detail.lower()


def test_create_superadmin_admin_account_rolls_back_auth_user_on_admin_record_failure():
    request = AdminCreateRequest(
        name="Admin User",
        email="admin@example.edu",
        password="password123",
        college_id="college-1",
    )
    user_id = "user-1"
    mock_client = MagicMock()
    mock_client.auth.admin.create_user.return_value = SimpleNamespace(
        user=SimpleNamespace(id=user_id)
    )

    profiles_table = _chainable_table(execute_return=SimpleNamespace(data=[{"id": user_id}]))
    users_table = _chainable_table(execute_return=SimpleNamespace(data=[{"id": user_id}]))
    admins_table = _chainable_table(execute_side_effect=Exception("admins insert failed"))
    mock_client.table.side_effect = lambda name: {
        "profiles": profiles_table,
        "users": users_table,
        "admins": admins_table,
    }[name]

    with patch("app.services.governance_service.get_service_client", return_value=mock_client):
        with pytest.raises(HTTPException) as exc_info:
            create_superadmin_admin_account(request)

    mock_client.auth.admin.delete_user.assert_called_once_with(user_id)
    assert exc_info.value.status_code >= 400
    assert "admin" in exc_info.value.detail.lower() or "create" in exc_info.value.detail.lower()


def test_delete_superadmin_admin_account_surfaces_auth_delete_failures():
    admin_id = "admin-1"
    mock_client = MagicMock()
    profiles_table = _chainable_table(execute_return=SimpleNamespace(data=[{"id": admin_id}]))
    mock_client.table.return_value = profiles_table
    mock_client.auth.admin.delete_user.side_effect = Exception("auth delete failed")

    with patch("app.services.governance_service.get_service_client", return_value=mock_client):
        with pytest.raises(HTTPException) as exc_info:
            delete_superadmin_admin_account(admin_id)

    mock_client.auth.admin.delete_user.assert_called_once_with(admin_id)
    assert exc_info.value.status_code == 500
    assert "delete" in exc_info.value.detail.lower()


def test_get_superadmin_admin_by_id_route_returns_payload(superadmin_client):
    with patch(
        "app.routers.superadmin.get_superadmin_admin_record",
        return_value={
            "id": "admin-1",
            "name": "Admin User",
            "email": "admin@example.edu",
            "college_id": "college-1",
            "college": "Alpha College",
            "status": "active",
            "joined": "2026-04-14T00:00:00Z",
        },
        create=True,
    ):
        response = superadmin_client.get("/superadmin/admins/admin-1")

    assert response.status_code == 200
    assert response.json()["id"] == "admin-1"
    assert response.json()["status"] == "active"


def test_get_superadmin_college_by_id_route_returns_payload(superadmin_client):
    with patch(
        "app.routers.superadmin.get_superadmin_college_record",
        return_value={
            "id": "college-1",
            "name": "Alpha College",
            "code": "ALPHA",
            "domain": "alpha.edu",
            "description": "Alpha description",
            "admin_count": 2,
        },
        create=True,
    ):
        response = superadmin_client.get("/superadmin/colleges/college-1")

    assert response.status_code == 200
    assert response.json() == {
        "id": "college-1",
        "name": "Alpha College",
        "code": "ALPHA",
        "domain": "alpha.edu",
        "description": "Alpha description",
        "admin_count": 2,
    }
