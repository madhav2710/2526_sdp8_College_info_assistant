import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from uuid import uuid4

try:
    from app.core.rag import (
        process_document, get_rag_config, RAGConfig, 
        retrieve_relevant_chunks, _check_vector_storage_integrity,
        _retrieve_chunks_with_native_search, _retrieve_chunks_with_python_search,
        VectorStoreError, EmbeddingServiceError
    )
except ImportError:
    process_document = None
    get_rag_config = None
    RAGConfig = None
    retrieve_relevant_chunks = None
    _check_vector_storage_integrity = None
    _retrieve_chunks_with_native_search = None
    _retrieve_chunks_with_python_search = None
    VectorStoreError = None
    EmbeddingServiceError = None

@pytest.mark.asyncio
async def test_process_document_success():
    if process_document is None:
        pytest.fail("Function process_document not found")

    document_id = str(uuid4())
    file_path = "colleges/123/syllabus.pdf"
    
    # Mock dependencies
    with patch("app.core.rag.get_service_client") as mock_get_client, \
         patch("app.core.rag.extract_text_from_pdf") as mock_extract, \
         patch("app.core.rag.generate_embedding") as mock_embed, \
         patch("app.core.rag.get_rag_config") as mock_get_config:
        
        # Mock RAG configuration
        mock_config = RAGConfig(
            gemini_api_key="test-key",
            chunk_size=1500,
            chunk_overlap=300
        )
        mock_get_config.return_value = mock_config
        
        mock_client = mock_get_client.return_value
        
        # Mock document details query
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{
                "college_id": str(uuid4()),
                "status": "approved",
                "filename": "test.pdf",
                "uploaded_by": str(uuid4())
            }]
        )
        
        # 1. Mock file download
        mock_client.storage.from_.return_value.download.return_value = b"pdf_content"
        
        # 2. Mock text extraction
        mock_extract.return_value = "Extracted text content from page 1."
        
        # 3. Mock embedding
        mock_embed.return_value = [0.1, 0.2, 0.3]
        
        # 4. Mock DB insert
        mock_client.table.return_value.insert.return_value = MagicMock(data=[{"id": "chunk-1"}])
        
        # 5. Mock status update
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        
        # Run processing
        await process_document(document_id, file_path)
        
        # Assertions
        # Verify download
        mock_client.storage.from_.return_value.download.assert_called_with(file_path)
        
        # Verify extraction
        mock_extract.assert_called_once()
        
        # Verify embedding
        mock_embed.assert_called_once()
        
        # Verify chunks insertion
        assert mock_client.table.return_value.insert.called
        
        # Verify status update
        assert mock_client.table.return_value.update.called

@pytest.mark.asyncio 
async def test_rag_config_validation():
    """Test RAG configuration validation"""
    if RAGConfig is None:
        pytest.fail("RAGConfig class not found")
    
    # Test valid configuration
    config = RAGConfig(
        gemini_api_key="test-key",
        chunk_size=1500,
        chunk_overlap=300,
        similarity_threshold=0.7
    )
    assert config.chunk_size == 1500
    assert config.chunk_overlap == 300
    
    # Test invalid configuration - chunk_overlap >= chunk_size
    with pytest.raises(Exception):  # Should raise ConfigurationError
        RAGConfig(
            gemini_api_key="test-key",
            chunk_size=300,
            chunk_overlap=300  # Equal to chunk_size, should fail
        )
    
    # Test invalid similarity threshold
    with pytest.raises(Exception):  # Should raise ConfigurationError
        RAGConfig(
            gemini_api_key="test-key",
            similarity_threshold=1.5  # > 1.0, should fail
        )


@pytest.mark.asyncio
async def test_vector_storage_integrity_check():
    """Test vector storage integrity checking functionality"""
    if _check_vector_storage_integrity is None:
        pytest.fail("_check_vector_storage_integrity function not found")
    
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
        await _check_vector_storage_integrity(mock_client, college_id)
        
        # Test dimension mismatch
        mock_client.table.return_value.select.return_value.eq.return_value.not_.is_.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"id": str(uuid4()), "embedding": [0.1] * 512}]  # Wrong dimension
        )
        
        with pytest.raises(VectorStoreError):
            await _check_vector_storage_integrity(mock_client, college_id)


@pytest.mark.asyncio
async def test_retrieve_chunks_with_native_search():
    """Test native pgvector search functionality"""
    if _retrieve_chunks_with_native_search is None:
        pytest.fail("_retrieve_chunks_with_native_search function not found")
    
    college_id = str(uuid4())
    document_id = str(uuid4())
    query_embedding = [0.1] * 768
    
    with patch("app.core.rag.get_service_client") as mock_get_client:
        mock_client = mock_get_client.return_value
        
        # Mock successful RPC call
        mock_client.rpc.return_value.execute.return_value = MagicMock(
            data=[{
                "id": str(uuid4()),
                "document_id": document_id,
                "college_id": college_id,
                "content": "Test content",
                "metadata": {"chunk_index": 0},
                "similarity": 0.85
            }]
        )
        
        # Mock document lookup - need to match the document_id
        mock_client.table.return_value.select.return_value.in_.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": document_id, "filename": "test.pdf"}]
        )
        
        result = await _retrieve_chunks_with_native_search(
            mock_client, query_embedding, college_id, 5, 0.7
        )
        
        assert result is not None
        assert len(result) == 1
        assert result[0]["content"] == "Test content"
        assert result[0]["similarity"] == 0.85
        assert result[0]["filename"] == "test.pdf"
        
        # Test RPC function not available
        mock_client.rpc.return_value.execute.side_effect = Exception("Function not found")
        
        result = await _retrieve_chunks_with_native_search(
            mock_client, query_embedding, college_id, 5, 0.7
        )
        
        assert result is None


@pytest.mark.asyncio
async def test_retrieve_chunks_with_python_search():
    """Test Python-based similarity search fallback"""
    if _retrieve_chunks_with_python_search is None:
        pytest.fail("_retrieve_chunks_with_python_search function not found")
    
    college_id = str(uuid4())
    document_id = str(uuid4())
    query_embedding = [0.1] * 768
    
    with patch("app.core.rag.get_service_client") as mock_get_client:
        mock_client = mock_get_client.return_value
        
        # Mock chunks data
        mock_client.table.return_value.select.return_value.eq.return_value.not_.is_.return_value.execute.return_value = MagicMock(
            data=[{
                "id": str(uuid4()),
                "document_id": document_id,
                "college_id": college_id,
                "content": "Test content",
                "embedding": [0.2] * 768,  # Similar embedding
                "metadata": {"chunk_index": 0}
            }]
        )
        
        # Mock document lookup
        mock_client.table.return_value.select.return_value.in_.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": document_id, "filename": "test.pdf", "status": "completed"}]
        )
        
        result = await _retrieve_chunks_with_python_search(
            mock_client, query_embedding, college_id, 5, 0.5
        )
        
        assert len(result) == 1
        assert result[0]["content"] == "Test content"
        assert "similarity" in result[0]
        assert result[0]["filename"] == "test.pdf"


@pytest.mark.asyncio
async def test_enhanced_retrieve_relevant_chunks():
    """Test the enhanced retrieve_relevant_chunks function"""
    if retrieve_relevant_chunks is None:
        pytest.fail("retrieve_relevant_chunks function not found")
    
    college_id = str(uuid4())
    query = "What are the admission requirements?"
    
    with patch("app.core.rag.get_rag_config") as mock_get_config, \
         patch("app.core.rag.get_service_client") as mock_get_client, \
         patch("app.core.rag.generate_embedding") as mock_embed, \
         patch("app.core.rag._check_vector_storage_integrity") as mock_integrity, \
         patch("app.core.rag._retrieve_chunks_with_native_search") as mock_native, \
         patch("app.core.rag._retrieve_chunks_with_python_search") as mock_python:
        
        # Mock configuration
        mock_config = RAGConfig(
            gemini_api_key="test-key",
            max_chunks_per_query=5,
            similarity_threshold=0.7
        )
        mock_get_config.return_value = mock_config
        
        # Mock embedding generation
        mock_embed.return_value = [0.1] * 768
        
        # Mock integrity check (no issues)
        mock_integrity.return_value = None
        
        # Mock native search success
        mock_native.return_value = [{
            "id": str(uuid4()),
            "document_id": str(uuid4()),
            "college_id": college_id,
            "content": "Test content",
            "chunk_index": 0,
            "filename": "test.pdf",
            "similarity": 0.85
        }]
        
        result = await retrieve_relevant_chunks(query, college_id)
        
        assert len(result) == 1
        assert result[0]["content"] == "Test content"
        
        # Test fallback to Python search
        mock_native.return_value = None  # Native search fails
        mock_python.return_value = [{
            "id": str(uuid4()),
            "document_id": str(uuid4()),
            "college_id": college_id,
            "content": "Fallback content",
            "chunk_index": 0,
            "filename": "test.pdf",
            "similarity": 0.75
        }]
        
        result = await retrieve_relevant_chunks(query, college_id)
        
        assert len(result) == 1
        assert result[0]["content"] == "Fallback content"
        
        # Test error handling
        mock_embed.side_effect = EmbeddingServiceError("API error")
        
        with pytest.raises(VectorStoreError):
            await retrieve_relevant_chunks(query, college_id)


@pytest.mark.asyncio
async def test_configurable_parameters():
    """Test that similarity thresholds and result limits are properly configurable"""
    if retrieve_relevant_chunks is None:
        pytest.fail("retrieve_relevant_chunks function not found")
    
    college_id = str(uuid4())
    query = "Test query"
    
    with patch("app.core.rag.get_rag_config") as mock_get_config, \
         patch("app.core.rag.get_service_client") as mock_get_client, \
         patch("app.core.rag.generate_embedding") as mock_embed, \
         patch("app.core.rag._check_vector_storage_integrity") as mock_integrity, \
         patch("app.core.rag._retrieve_chunks_with_native_search") as mock_native, \
         patch("app.core.rag._retrieve_chunks_with_python_search") as mock_python:
        
        # Mock configuration with custom values
        mock_config = RAGConfig(
            gemini_api_key="test-key",
            max_chunks_per_query=10,
            similarity_threshold=0.8
        )
        mock_get_config.return_value = mock_config
        
        mock_embed.return_value = [0.1] * 768
        mock_integrity.return_value = None
        mock_native.return_value = None  # Force fallback to Python search
        mock_python.return_value = []
        
        # Test with custom parameters
        await retrieve_relevant_chunks(query, college_id, top_k=3, similarity_threshold=0.9)
        
        # Verify that custom parameters were passed to the search function
        mock_python.assert_called_once()
        args = mock_python.call_args[0]
        assert args[3] == 3  # top_k
        assert args[4] == 0.9  # similarity_threshold
