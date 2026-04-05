import os
import sys
import types

from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
os.environ.setdefault("SERVICE_ROLE_KEY", "test-service-key")
os.environ.setdefault("JWT_SECRET_KEY", "12345678901234567890123456789012")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")

supabase_module = types.ModuleType("supabase")
google_module = types.ModuleType("google")
google_generativeai_module = types.ModuleType("google.generativeai")
setattr(google_generativeai_module, "configure", lambda **kwargs: None)
setattr(google_module, "generativeai", google_generativeai_module)


class _Client:
    def __init__(self):
        self.auth = types.SimpleNamespace(
            admin=types.SimpleNamespace(),
            get_user=lambda *args, **kwargs: None,
            sign_in_with_password=lambda *args, **kwargs: None,
            sign_up=lambda *args, **kwargs: None,
        )

    def table(self, *args, **kwargs):
        return self

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def in_(self, *args, **kwargs):
        return self

    def ilike(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def insert(self, *args, **kwargs):
        return self

    def upsert(self, *args, **kwargs):
        return self

    def update(self, *args, **kwargs):
        return self

    def delete(self, *args, **kwargs):
        return self

    def rpc(self, *args, **kwargs):
        return self

    def execute(self):
        return types.SimpleNamespace(data=[])


setattr(supabase_module, "Client", _Client)
setattr(supabase_module, "create_client", lambda *args, **kwargs: _Client())
sys.modules["supabase"] = supabase_module
sys.modules["google"] = google_module
sys.modules["google.generativeai"] = google_generativeai_module

from main import app

client = TestClient(app)


def test_read_main():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to Our Application!"}
