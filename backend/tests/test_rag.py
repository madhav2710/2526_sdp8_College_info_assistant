import asyncio
import math
import os
import sys
import types

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from uuid import uuid4

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
os.environ.setdefault("SERVICE_ROLE_KEY", "test-service-key")

pypdf_module = types.ModuleType("pypdf")
setattr(pypdf_module, "PdfReader", object)
sys.modules.setdefault("pypdf", pypdf_module)

numpy_module = types.ModuleType("numpy")


class _FakeArray(list):
    @property
    def size(self):
        return len(self)


setattr(numpy_module, "float32", float)
setattr(numpy_module, "array", lambda values, dtype=None: _FakeArray(values))
setattr(
    numpy_module,
    "dot",
    lambda left, right: sum(a * b for a, b in zip(left, right)),
)
setattr(
    numpy_module,
    "linalg",
    types.SimpleNamespace(
        norm=lambda values: math.sqrt(sum(value * value for value in values))
    ),
)
sys.modules.setdefault("numpy", numpy_module)

from app.core.config import AIConfig, RAGConfig
from app.core.rag import (
    process_document,
    retrieve_relevant_chunks,
    _check_vector_storage_integrity,
    _retrieve_chunks_with_native_search,
    _retrieve_chunks_with_python_search,
    VectorStoreError,
    EmbeddingServiceError,
)


def test_process_document_success():
    if process_document is None:
        pytest.fail("Function process_document not found")

    document_id = str(uuid4())
    file_path = "colleges/123/syllabus.pdf"

    # Mock dependencies
    with (
        patch("app.core.rag.get_service_client") as mock_get_client,
        patch("app.core.rag.extract_text_from_pdf") as mock_extract,
        patch("app.core.rag.generate_embedding") as mock_embed,
        patch("app.core.rag.get_rag_config") as mock_get_config,
    ):
        # Mock RAG configuration
        mock_get_config.return_value = (
            RAGConfig(chunk_size=1500, chunk_overlap=300),
            AIConfig(gemini_api_key="test-key"),
        )

        mock_client = mock_get_client.return_value

        # Mock document details query
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "college_id": str(uuid4()),
                    "status": "approved",
                    "filename": "test.pdf",
                    "uploaded_by": str(uuid4()),
                }
            ]
        )

        # 1. Mock file download
        mock_client.storage.from_.return_value.download.return_value = b"pdf_content"

        # 2. Mock text extraction
        mock_extract.return_value = "Extracted text content from page 1."

        # 3. Mock embedding
        mock_embed.return_value = [0.1, 0.2, 0.3]

        # 4. Mock DB insert
        mock_client.table.return_value.insert.return_value = MagicMock(
            data=[{"id": "chunk-1"}]
        )

        # 5. Mock status update
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        # Run processing
        asyncio.run(process_document(document_id, file_path))

        # Assertions
        # Verify download
        mock_client.storage.from_.return_value.download.assert_called_with(file_path)

        # Verify extraction
        mock_extract.assert_called_once()

        # Verify embedding
        mock_embed.assert_called_once()

        # Verify chunks insertion
        assert mock_client.table.return_value.insert.called

        assert mock_client.table.return_value.delete.return_value.eq.return_value.execute.called

        # Verify status update
        assert mock_client.table.return_value.update.called


def test_rag_config_validation():
    """Test RAG configuration validation"""
    # Test valid configuration
    config = RAGConfig(chunk_size=1500, chunk_overlap=300, similarity_threshold=0.7)
    assert config.chunk_size == 1500
    assert config.chunk_overlap == 300
    assert config.validate() == []

    # Test invalid configuration - chunk_overlap >= chunk_size
    invalid_overlap = RAGConfig(chunk_size=300, chunk_overlap=300)
    assert (
        "RAG_CHUNK_OVERLAP must be less than RAG_CHUNK_SIZE"
        in invalid_overlap.validate()
    )

    # Test invalid similarity threshold
    invalid_threshold = RAGConfig(similarity_threshold=1.5)
    assert (
        "RAG_SIMILARITY_THRESHOLD must be between 0.0 and 1.0"
        in invalid_threshold.validate()
    )


def test_vector_storage_integrity_check():
    """Test vector storage integrity checking functionality"""
    college_id = str(uuid4())

    with patch("app.core.rag.get_service_client") as mock_get_client:
        mock_client = mock_get_client.return_value

        # Mock chunks without embeddings
        mock_client.table.return_value.select.return_value.eq.return_value.is_.return_value.execute.return_value = MagicMock(
            data=[{"id": str(uuid4()), "document_id": str(uuid4())}]
        )

        # Mock orphaned chunks check
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": str(uuid4()), "document_id": str(uuid4())}]
        )

        # Mock valid documents check
        mock_client.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(
            data=[]  # No valid documents, so all chunks are orphaned
        )

        # Mock embedding dimension check
        mock_client.table.return_value.select.return_value.eq.return_value.not_.is_.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"id": str(uuid4()), "embedding": [0.1] * 768}]  # Correct dimension
        )

        # Should not raise an exception for warnings
        asyncio.run(_check_vector_storage_integrity(mock_client, college_id))

        # Test dimension mismatch
        mock_client.table.return_value.select.return_value.eq.return_value.not_.is_.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"id": str(uuid4()), "embedding": [0.1] * 512}]  # Wrong dimension
        )

        with pytest.raises(VectorStoreError):
            asyncio.run(_check_vector_storage_integrity(mock_client, college_id))


def test_retrieve_chunks_with_native_search():
    """Test native pgvector search functionality"""
    college_id = str(uuid4())
    document_id = str(uuid4())
    query_embedding = [0.1] * 768

    with patch("app.core.rag.get_service_client") as mock_get_client:
        mock_client = mock_get_client.return_value

        # Mock successful RPC call
        mock_client.rpc.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "id": str(uuid4()),
                    "document_id": document_id,
                    "college_id": college_id,
                    "content": "Test content",
                    "metadata": {"chunk_index": 0},
                    "similarity": 0.85,
                }
            ]
        )

        # Mock document lookup - need to match the document_id
        mock_client.table.return_value.select.return_value.in_.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": document_id, "filename": "test.pdf"}]
        )

        result = asyncio.run(
            _retrieve_chunks_with_native_search(
                mock_client, query_embedding, college_id, 5, 0.7
            )
        )

        assert result is not None
        assert len(result) == 1
        assert result[0]["content"] == "Test content"
        assert result[0]["similarity"] == 0.85
        assert result[0]["filename"] == "test.pdf"

        # Test RPC function not available
        mock_client.rpc.return_value.execute.side_effect = Exception(
            "Function not found"
        )

        result = asyncio.run(
            _retrieve_chunks_with_native_search(
                mock_client, query_embedding, college_id, 5, 0.7
            )
        )

        assert result is None


def test_retrieve_chunks_with_python_search():
    """Test Python-based similarity search fallback"""
    college_id = str(uuid4())
    document_id = str(uuid4())
    query_embedding = [0.1] * 768

    with patch("app.core.rag.get_service_client") as mock_get_client:
        mock_client = mock_get_client.return_value

        # Mock chunks data
        mock_client.table.return_value.select.return_value.eq.return_value.not_.is_.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "id": str(uuid4()),
                    "document_id": document_id,
                    "college_id": college_id,
                    "content": "Test content",
                    "embedding": [0.2] * 768,  # Similar embedding
                    "metadata": {"chunk_index": 0},
                }
            ]
        )

        # Mock document lookup
        mock_client.table.return_value.select.return_value.in_.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": document_id, "filename": "test.pdf", "status": "completed"}]
        )

        result = asyncio.run(
            _retrieve_chunks_with_python_search(
                mock_client, query_embedding, college_id, 5, 0.5
            )
        )

        assert len(result) == 1
        assert result[0]["content"] == "Test content"
        assert "similarity" in result[0]
        assert result[0]["filename"] == "test.pdf"


def test_enhanced_retrieve_relevant_chunks():
    """Test the enhanced retrieve_relevant_chunks function"""
    college_id = str(uuid4())
    query = "What are the admission requirements?"

    with (
        patch("app.core.rag.get_rag_config") as mock_get_config,
        patch("app.core.rag.get_service_client") as mock_get_client,
        patch("app.core.rag.generate_embedding") as mock_embed,
        patch("app.core.rag._check_vector_storage_integrity") as mock_integrity,
        patch("app.core.rag._retrieve_chunks_with_native_search") as mock_native,
        patch("app.core.rag._retrieve_chunks_with_python_search") as mock_python,
    ):
        # Mock configuration
        mock_get_config.return_value = (
            RAGConfig(max_chunks_per_query=5, similarity_threshold=0.7),
            AIConfig(gemini_api_key="test-key"),
        )

        # Mock embedding generation
        mock_embed.return_value = [0.1] * 768

        # Mock integrity check (no issues)
        mock_integrity.return_value = None

        # Mock native search success
        mock_native.return_value = [
            {
                "id": str(uuid4()),
                "document_id": str(uuid4()),
                "college_id": college_id,
                "content": "Test content",
                "chunk_index": 0,
                "filename": "test.pdf",
                "similarity": 0.85,
            }
        ]

        result = asyncio.run(retrieve_relevant_chunks(query, college_id))

        assert len(result) == 1
        assert result[0]["content"] == "Test content"

        # Test fallback to Python search
        mock_native.return_value = None  # Native search fails
        mock_python.return_value = [
            {
                "id": str(uuid4()),
                "document_id": str(uuid4()),
                "college_id": college_id,
                "content": "Fallback content",
                "chunk_index": 0,
                "filename": "test.pdf",
                "similarity": 0.75,
            }
        ]

        result = asyncio.run(retrieve_relevant_chunks(query, college_id))

        assert len(result) == 1
        assert result[0]["content"] == "Fallback content"

        # Test error handling
        mock_embed.side_effect = EmbeddingServiceError("API error")

        with pytest.raises(VectorStoreError):
            asyncio.run(retrieve_relevant_chunks(query, college_id))


def test_configurable_parameters():
    """Test that similarity thresholds and result limits are properly configurable"""
    college_id = str(uuid4())
    query = "Test query"

    with (
        patch("app.core.rag.get_rag_config") as mock_get_config,
        patch("app.core.rag.get_service_client") as mock_get_client,
        patch("app.core.rag.generate_embedding") as mock_embed,
        patch("app.core.rag._check_vector_storage_integrity") as mock_integrity,
        patch("app.core.rag._retrieve_chunks_with_native_search") as mock_native,
        patch("app.core.rag._retrieve_chunks_with_python_search") as mock_python,
    ):
        # Mock configuration with custom values
        mock_get_config.return_value = (
            RAGConfig(max_chunks_per_query=10, similarity_threshold=0.8),
            AIConfig(gemini_api_key="test-key"),
        )

        mock_embed.return_value = [0.1] * 768
        mock_integrity.return_value = None
        mock_native.return_value = None  # Force fallback to Python search
        mock_python.return_value = []

        # Test with custom parameters
        asyncio.run(
            retrieve_relevant_chunks(
                query, college_id, top_k=3, similarity_threshold=0.9
            )
        )

        # Verify that custom parameters were passed to the search function
        mock_python.assert_called_once()
        args = mock_python.call_args[0]
        assert args[3] == 3  # top_k
        assert args[4] == 0.9  # similarity_threshold
