import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from uuid import uuid4

try:
    from app.core.rag import process_document
except ImportError:
    process_document = None

@pytest.mark.asyncio
async def test_process_document_success():
    if process_document is None:
        pytest.fail("Function process_document not found")

    document_id = str(uuid4())
    file_path = "colleges/123/syllabus.pdf"
    
    # Mock dependencies
    with patch("app.core.rag.get_service_client") as mock_get_client, \
         patch("app.core.rag.extract_text_from_pdf") as mock_extract, \
         patch("app.core.rag.generate_embedding") as mock_embed:
        
        mock_client = mock_get_client.return_value
        
        # 1. Mock file download
        mock_client.storage.from_.return_value.download.return_value = b"pdf_content"
        
        # 2. Mock text extraction
        mock_extract.return_value = "Extracted text content from page 1."
        
        # 3. Mock embedding
        mock_embed.return_value = [0.1, 0.2, 0.3]
        
        # 4. Mock DB insert
        mock_client.table.return_value.insert.return_value = MagicMock(data=[{"id": "chunk-1"}])
        
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
