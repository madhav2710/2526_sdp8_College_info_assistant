import os
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
os.environ.setdefault("SERVICE_ROLE_KEY", "test-service-key")
os.environ.setdefault("JWT_SECRET_KEY", "12345678901234567890123456789012")

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
        )

    def table(self, *args, **kwargs):
        return self

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def insert(self, *args, **kwargs):
        return self

    def execute(self):
        return types.SimpleNamespace(data=[])


setattr(supabase_module, "Client", _Client)
setattr(supabase_module, "create_client", lambda *args, **kwargs: _Client())
sys.modules.setdefault("supabase", supabase_module)
sys.modules.setdefault("google", google_module)
sys.modules.setdefault("google.generativeai", google_generativeai_module)

from app.core.auth import get_current_user
from app.routers.chat import router
from app.services.chat_service import clear_rate_limit_cache

app = FastAPI()
app.include_router(router)
client = TestClient(app)


async def mock_current_user():
    return {
        "user_id": "11111111-1111-1111-1111-111111111111",
        "role": "student",
        "college_id": "test-college-id",
    }


def make_rag_module(response: dict):
    rag_module = types.ModuleType("app.core.rag")

    class EmbeddingServiceError(Exception):
        pass

    class VectorStoreError(Exception):
        pass

    class RAGError(Exception):
        pass

    async def generate_rag_response(**kwargs):
        return response

    setattr(rag_module, "EmbeddingServiceError", EmbeddingServiceError)
    setattr(rag_module, "VectorStoreError", VectorStoreError)
    setattr(rag_module, "RAGError", RAGError)
    setattr(rag_module, "generate_rag_response", generate_rag_response)
    return rag_module


def test_create_chat_message():
    app.dependency_overrides[get_current_user] = mock_current_user
    clear_rate_limit_cache()
    conv_id = str(uuid4())
    user_id = "11111111-1111-1111-1111-111111111111"

    profiles_table = MagicMock()
    profiles_table.select.return_value.eq.return_value.execute.return_value = (
        SimpleNamespace(data=[{"college_id": "test-college-id", "role": "student"}])
    )

    conversations_table = MagicMock()
    conversations_table.select.return_value.eq.return_value.execute.return_value = (
        SimpleNamespace(data=[])
    )
    conversations_table.insert.return_value.execute.return_value = SimpleNamespace(
        data=[{"id": conv_id}]
    )

    messages_table = MagicMock()
    messages_table.insert.return_value.execute.side_effect = [
        SimpleNamespace(data=[{"id": "user-message-id"}]),
        SimpleNamespace(data=[{"id": "assistant-message-id"}]),
    ]
    messages_table.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = SimpleNamespace(
        data=[]
    )

    mock_service_client = MagicMock()
    mock_service_client.table.side_effect = lambda table_name: {
        "profiles": profiles_table,
        "conversations": conversations_table,
        "messages": messages_table,
    }[table_name]

    with (
        patch(
            "app.services.chat_service.get_service_client",
            return_value=mock_service_client,
        ),
        patch.dict(
            sys.modules,
            {
                "app.core.rag": make_rag_module(
                    {
                        "response": "Here is the syllabus information you requested.",
                        "sources": ["syllabus.pdf"],
                        "chunks_used": 2,
                        "fallback_used": False,
                        "quality_score": 0.91,
                        "source_details": [],
                        "conversation_context_used": False,
                    }
                )
            },
        ),
    ):
        response = client.post(
            "/chat/",
            json={
                "conversation_id": conv_id,
                "user_id": user_id,
                "role": "user",
                "content": "Hello, I need the syllabus.",
            },
        )

    app.dependency_overrides.clear()
    clear_rate_limit_cache()

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["status"] == "success"
    assert response_data["role"] == "assistant"
    assert "syllabus information" in response_data["content"]
    assert response_data["sources"] == ["syllabus.pdf"]
    assert response_data["conversation_id"] == conv_id
    assert response_data["metadata"]["chunks_used"] == 2
    assert response_data["metadata"]["rag_enabled"] is True


def test_guest_chat_falls_back_to_basic_response():
    colleges_table = MagicMock()
    colleges_table.select.return_value.limit.return_value.execute.return_value = (
        SimpleNamespace(data=[{"id": "college-1"}])
    )

    mock_service_client = MagicMock()
    mock_service_client.table.side_effect = lambda table_name: {
        "colleges": colleges_table,
    }[table_name]

    fallback_response = {
        "response": "Fallback answer",
        "sources": [],
        "chunks_used": 0,
        "quality_score": None,
    }

    with (
        patch(
            "app.services.chat_service.get_service_client",
            return_value=mock_service_client,
        ),
        patch(
            "app.services.chat_service.generate_basic_response",
            new=AsyncMock(return_value=fallback_response),
        ),
        patch.dict(sys.modules, {}, clear=False),
    ):
        sys.modules.pop("app.core.rag", None)
        response = client.post(
            "/guest-chat",
            json={"content": "Tell me about admissions"},
        )

    assert response.status_code == 200
    assert response.json()["content"] == "Fallback answer"
    assert response.json()["sources"] == []
    assert response.json()["metadata"]["fallback_used"] is True
    assert response.json()["metadata"]["chunks_used"] == 0
    assert response.json()["metadata"]["quality_score"] is None
    assert response.json()["metadata"]["fallback_reason"].startswith(
        "Guest RAG failed:"
    )


def test_get_chat_history():
    user_id = str(uuid4())
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = SimpleNamespace(
        data=[{"id": "conv-1", "title": "First Chat"}]
    )

    with patch("app.services.chat_service.supabase", mock_supabase):
        response = client.get(f"/chat/history/?user_id={user_id}")

    assert response.status_code == 200
    assert response.json() == [{"id": "conv-1", "title": "First Chat"}]


def test_get_conversation_messages():
    app.dependency_overrides[get_current_user] = mock_current_user
    conversation_id = str(uuid4())

    conversations_table = MagicMock()
    conversations_table.select.return_value.eq.return_value.execute.return_value = (
        SimpleNamespace(data=[{"user_id": "11111111-1111-1111-1111-111111111111"}])
    )

    messages_table = MagicMock()
    messages_table.select.return_value.eq.return_value.order.return_value.execute.return_value = SimpleNamespace(
        data=[
            {
                "id": "message-1",
                "role": "user",
                "content": "Hello",
                "created_at": "2024-01-04T10:00:00Z",
                "metadata": None,
            }
        ]
    )

    mock_service_client = MagicMock()
    mock_service_client.table.side_effect = lambda table_name: {
        "conversations": conversations_table,
        "messages": messages_table,
    }[table_name]

    with patch(
        "app.services.chat_service.get_service_client",
        return_value=mock_service_client,
    ):
        response = client.get(f"/chat/conversation/{conversation_id}/messages")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "conversation_id": conversation_id,
        "messages": [
            {
                "id": "message-1",
                "role": "user",
                "content": "Hello",
                "created_at": "2024-01-04T10:00:00Z",
                "metadata": None,
            }
        ],
    }


def test_chat_rate_limiting():
    app.dependency_overrides[get_current_user] = mock_current_user
    clear_rate_limit_cache()
    conv_id = str(uuid4())
    user_id = "11111111-1111-1111-1111-111111111111"

    profiles_table = MagicMock()
    profiles_table.select.return_value.eq.return_value.execute.return_value = (
        SimpleNamespace(data=[{"college_id": "test-college-id", "role": "student"}])
    )

    conversations_table = MagicMock()
    conversations_table.select.return_value.eq.return_value.execute.return_value = (
        SimpleNamespace(data=[])
    )
    conversations_table.insert.return_value.execute.return_value = SimpleNamespace(
        data=[{"id": conv_id}]
    )

    messages_table = MagicMock()
    messages_table.insert.return_value.execute.side_effect = [
        SimpleNamespace(data=[{"id": f"user-{index}"}])
        if index % 2 == 0
        else SimpleNamespace(data=[{"id": f"assistant-{index}"}])
        for index in range(20)
    ]
    messages_table.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = SimpleNamespace(
        data=[]
    )

    mock_service_client = MagicMock()
    mock_service_client.table.side_effect = lambda table_name: {
        "profiles": profiles_table,
        "conversations": conversations_table,
        "messages": messages_table,
    }[table_name]

    with (
        patch(
            "app.services.chat_service.get_service_client",
            return_value=mock_service_client,
        ),
        patch.dict(
            sys.modules,
            {
                "app.core.rag": make_rag_module(
                    {
                        "response": "Test response",
                        "sources": [],
                        "chunks_used": 0,
                        "fallback_used": False,
                        "quality_score": 0.5,
                        "source_details": [],
                        "conversation_context_used": False,
                    }
                )
            },
        ),
    ):
        for index in range(11):
            response = client.post(
                "/chat/",
                json={
                    "conversation_id": conv_id,
                    "user_id": user_id,
                    "role": "user",
                    "content": f"Test message {index}",
                },
            )

            if index < 10:
                assert response.status_code == 200
            else:
                assert response.status_code == 429
                assert response.json()["detail"] == (
                    "Too many requests. Please wait before sending another message."
                )

    app.dependency_overrides.clear()
    clear_rate_limit_cache()
