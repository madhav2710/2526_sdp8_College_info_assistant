from app.core.database import get_service_client
from app.core.config import get_system_config, ConfigurationError
import google.generativeai as genai
import os
import time
import logging
from io import BytesIO
from pypdf import PdfReader
from uuid import UUID
import re
from typing import List, Optional, Dict, Any
import numpy as np
from dataclasses import dataclass
from enum import Enum
import asyncio
import traceback
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger(__name__)

class RAGError(Exception):
    """Base exception for RAG-related errors"""
    pass

class EmbeddingServiceError(RAGError):
    """Raised when embedding service fails"""
    pass

class VectorStoreError(RAGError):
    """Raised when vector storage operations fail"""
    pass

class DocumentProcessingError(RAGError):
    """Raised when document processing fails"""
    pass

class ServiceUnavailableError(RAGError):
    """Raised when a service is temporarily unavailable"""
    pass

class RateLimitError(RAGError):
    """Raised when rate limits are exceeded"""
    pass

class CircuitBreakerError(RAGError):
    """Raised when circuit breaker is open"""
    pass

@dataclass
class ServiceHealth:
    """Track service health status"""
    service_name: str
    is_healthy: bool = True
    last_failure: Optional[datetime] = None
    failure_count: int = 0
    last_success: Optional[datetime] = None
    circuit_breaker_open: bool = False
    circuit_breaker_open_until: Optional[datetime] = None

class ServiceHealthManager:
    """Manage health status of external services"""
    
    def __init__(self):
        self._services: Dict[str, ServiceHealth] = {}
        self._failure_threshold = 5  # Open circuit after 5 failures
        self._circuit_breaker_timeout = 300  # 5 minutes
        self._health_check_interval = 60  # 1 minute
    
    def get_service_health(self, service_name: str) -> ServiceHealth:
        """Get or create service health status"""
        if service_name not in self._services:
            self._services[service_name] = ServiceHealth(service_name=service_name)
        return self._services[service_name]
    
    def record_success(self, service_name: str) -> None:
        """Record successful service operation"""
        health = self.get_service_health(service_name)
        health.is_healthy = True
        health.last_success = datetime.utcnow()
        health.failure_count = 0
        health.circuit_breaker_open = False
        health.circuit_breaker_open_until = None
        logger.debug(f"Service {service_name} health: SUCCESS")
    
    def record_failure(self, service_name: str, error: Exception) -> None:
        """Record service failure and update circuit breaker status"""
        health = self.get_service_health(service_name)
        health.last_failure = datetime.utcnow()
        health.failure_count += 1
        
        # Check if we should open circuit breaker
        if health.failure_count >= self._failure_threshold:
            health.circuit_breaker_open = True
            health.circuit_breaker_open_until = datetime.utcnow() + timedelta(seconds=self._circuit_breaker_timeout)
            health.is_healthy = False
            logger.error(f"Circuit breaker OPENED for service {service_name} after {health.failure_count} failures")
        else:
            logger.warning(f"Service {service_name} failure {health.failure_count}/{self._failure_threshold}: {str(error)}")
    
    def is_circuit_breaker_open(self, service_name: str) -> bool:
        """Check if circuit breaker is open for a service"""
        health = self.get_service_health(service_name)
        
        if not health.circuit_breaker_open:
            return False
        
        # Check if circuit breaker timeout has expired
        if health.circuit_breaker_open_until and datetime.utcnow() > health.circuit_breaker_open_until:
            # Reset circuit breaker to half-open state
            health.circuit_breaker_open = False
            health.circuit_breaker_open_until = None
            health.failure_count = 0
            logger.info(f"Circuit breaker HALF-OPEN for service {service_name} - allowing test requests")
            return False
        
        return True
    
    def get_all_service_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all tracked services"""
        status = {}
        for service_name, health in self._services.items():
            status[service_name] = {
                "is_healthy": health.is_healthy,
                "failure_count": health.failure_count,
                "last_failure": health.last_failure.isoformat() if health.last_failure else None,
                "last_success": health.last_success.isoformat() if health.last_success else None,
                "circuit_breaker_open": health.circuit_breaker_open,
                "circuit_breaker_open_until": health.circuit_breaker_open_until.isoformat() if health.circuit_breaker_open_until else None
            }
        return status

# Global service health manager
_service_health_manager = ServiceHealthManager()

def get_rag_config():
    """Get RAG configuration from the centralized configuration system"""
    try:
        system_config = get_system_config()
        return system_config.rag, system_config.ai
    except ConfigurationError as e:
        logger.error(f"Failed to get RAG configuration: {str(e)}")
        raise

def get_service_health_manager() -> ServiceHealthManager:
    """Get the global service health manager"""
    return _service_health_manager

def retry_with_backoff(max_retries: int = None, delay: float = None, backoff_factor: float = None, max_delay: float = None, service_name: str = None):
    """
    Enhanced decorator for retrying functions with exponential backoff and circuit breaker support.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries
        backoff_factor: Multiplier for delay after each failure
        max_delay: Maximum delay between retries
        service_name: Name of service for circuit breaker tracking
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            rag_config, ai_config = get_rag_config()
            retries = max_retries if max_retries is not None else ai_config.max_retries
            current_delay = delay if delay is not None else ai_config.retry_delay
            factor = backoff_factor if backoff_factor is not None else ai_config.retry_backoff_factor
            max_delay_limit = max_delay if max_delay is not None else ai_config.max_retry_delay
            
            health_manager = get_service_health_manager()
            
            # Check circuit breaker if service name provided
            if service_name and health_manager.is_circuit_breaker_open(service_name):
                logger.error(f"Circuit breaker is OPEN for service {service_name} - failing fast")
                raise CircuitBreakerError(f"Service {service_name} is currently unavailable (circuit breaker open)")
            
            last_exception = None
            
            for attempt in range(retries + 1):
                try:
                    result = func(*args, **kwargs)
                    
                    # Record success if service name provided
                    if service_name:
                        health_manager.record_success(service_name)
                    
                    if attempt > 0:
                        logger.info(f"Function {func.__name__} succeeded on attempt {attempt + 1}/{retries + 1}")
                    
                    return result
                    
                except Exception as e:
                    last_exception = e
                    
                    # Record failure if service name provided
                    if service_name:
                        health_manager.record_failure(service_name, e)
                    
                    # Check if this is a rate limit error
                    if "quota" in str(e).lower() or "rate" in str(e).lower():
                        # For rate limits, use longer delays
                        rate_limit_delay = min(current_delay * 3, 300)  # Max 5 minutes
                        logger.warning(f"Rate limit detected in {func.__name__}, attempt {attempt + 1}/{retries + 1}. Waiting {rate_limit_delay}s before retry...")
                        if attempt < retries:
                            time.sleep(rate_limit_delay)
                        continue
                    
                    if attempt == retries:
                        logger.error(f"Function {func.__name__} failed after {retries + 1} attempts: {str(e)}")
                        
                        # Log detailed error information for debugging
                        logger.error(f"Final failure details for {func.__name__}:")
                        logger.error(f"  - Error type: {type(e).__name__}")
                        logger.error(f"  - Error message: {str(e)}")
                        logger.error(f"  - Function args: {args}")
                        logger.error(f"  - Function kwargs: {kwargs}")
                        
                        # Include stack trace for debugging
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(f"Stack trace for {func.__name__} failure:\n{traceback.format_exc()}")
                        
                        raise e
                    
                    logger.warning(f"Function {func.__name__} failed on attempt {attempt + 1}/{retries + 1}: {str(e)}. Retrying in {current_delay}s...")
                    time.sleep(current_delay)
                    current_delay = min(current_delay * factor, max_delay_limit)
            
            raise last_exception
        return wrapper
    return decorator

def extract_text_from_pdf(file_content: bytes) -> str:
    """
    Extract text from PDF with enhanced error handling and validation.
    
    Args:
        file_content: PDF file content as bytes
        
    Returns:
        Extracted text string
        
    Raises:
        DocumentProcessingError: If PDF processing fails
    """
    if not file_content:
        raise DocumentProcessingError("Empty file content provided")
    
    try:
        reader = PdfReader(BytesIO(file_content))
        
        if len(reader.pages) == 0:
            raise DocumentProcessingError("PDF contains no pages")
        
        text = ""
        pages_processed = 0
        
        for page_num, page in enumerate(reader.pages):
            try:
                if page_text := page.extract_text():
                    text += page_text + "\n"
                    pages_processed += 1
                else:
                    logger.warning(f"No text found on page {page_num + 1}")
            except Exception as e:
                logger.warning(f"Failed to extract text from page {page_num + 1}: {str(e)}")
                continue
        
        if not text.strip():
            raise DocumentProcessingError(f"No text could be extracted from PDF ({len(reader.pages)} pages processed)")
        
        logger.info(f"Successfully extracted text from {pages_processed}/{len(reader.pages)} pages")
        return text.strip()
        
    except DocumentProcessingError:
        raise
    except Exception as e:
        logger.error(f"PDF processing failed: {str(e)}")
        raise DocumentProcessingError(f"Failed to process PDF: {str(e)}")

def chunk_text(text: str, chunk_size: int = None, chunk_overlap: int = None) -> List[str]:
    """
    Split text into overlapping chunks for better context retention.
    
    Args:
        text: The text to chunk
        chunk_size: Maximum characters per chunk (uses config default if None)
        chunk_overlap: Characters to overlap between chunks (uses config default if None)
    
    Returns:
        List of text chunks
        
    Raises:
        DocumentProcessingError: If chunking fails
    """
    if not text:
        return []
    
    try:
        rag_config, ai_config = get_rag_config()
        chunk_size = chunk_size or rag_config.chunk_size
        chunk_overlap = chunk_overlap or rag_config.chunk_overlap
        
        # Validate parameters
        if chunk_size <= 0:
            raise DocumentProcessingError("chunk_size must be positive")
        if chunk_overlap < 0:
            raise DocumentProcessingError("chunk_overlap cannot be negative")
        if chunk_overlap >= chunk_size:
            raise DocumentProcessingError("chunk_overlap must be less than chunk_size")
        
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        # Try to split on sentences first for better semantic boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        current_chunk = ""
        for sentence in sentences:
            # If adding this sentence would exceed chunk_size, save current chunk and start new one
            if len(current_chunk) + len(sentence) > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                # Start new chunk with overlap from previous chunk
                overlap_start = max(0, len(current_chunk) - chunk_overlap)
                current_chunk = current_chunk[overlap_start:] + " " + sentence
            else:
                current_chunk += " " + sentence if current_chunk else sentence
        
        # Add the last chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        # Fallback: if sentence splitting didn't work well (no chunks or oversized chunks), 
        # use simple character-based splitting
        if len(chunks) == 0 or any(len(chunk) > chunk_size for chunk in chunks):
            chunks = []
            for i in range(0, len(text), chunk_size - chunk_overlap):
                chunk = text[i:i + chunk_size]
                if chunk.strip():
                    chunks.append(chunk.strip())
        
        if not chunks:
            raise DocumentProcessingError("Failed to create any text chunks")
        
        logger.info(f"Created {len(chunks)} chunks from text of length {len(text)}")
        return chunks
        
    except DocumentProcessingError:
        raise
    except Exception as e:
        logger.error(f"Text chunking failed: {str(e)}")
        raise DocumentProcessingError(f"Failed to chunk text: {str(e)}")

@retry_with_backoff(service_name="gemini_embedding")
def generate_embedding(text: str) -> list[float]:
    """
    Generate embeddings for text using Google's embedding model with enhanced retry logic and circuit breaker.
    
    Args:
        text: Text to generate embeddings for
        
    Returns:
        List of embedding values
        
    Raises:
        EmbeddingServiceError: If embedding generation fails after retries
        CircuitBreakerError: If service is temporarily unavailable
    """
    if not text.strip():
        raise EmbeddingServiceError("Cannot generate embedding for empty text")
    
    rag_config, ai_config = get_rag_config()
    
    if not ai_config.gemini_api_key or ai_config.gemini_api_key == "REPLACE_WITH_YOUR_VALID_GEMINI_API_KEY":
        logger.warning("GEMINI_API_KEY not configured or using placeholder - returning zero embedding")
        return [0.0] * 768  # Return zero embedding as fallback
    
    try:
        result = genai.embed_content(
            model=ai_config.embedding_model,
            content=text,
            task_type="retrieval_document",
            title="College Document"
        )
        
        if not result or 'embedding' not in result:
            raise EmbeddingServiceError("Invalid response from embedding service")
        
        embedding = result['embedding']
        if not embedding or len(embedding) == 0:
            raise EmbeddingServiceError("Empty embedding returned from service")
        
        logger.debug(f"Generated embedding of dimension {len(embedding)} for text of length {len(text)}")
        return embedding
        
    except Exception as e:
        logger.error(f"Embedding generation failed: {str(e)}")
        
        # Enhanced error classification for better handling
        error_str = str(e).lower()
        if "quota" in error_str or "rate" in error_str:
            raise RateLimitError(f"Rate limit or quota exceeded: {str(e)}")
        elif "api" in error_str or "key" in error_str or "auth" in error_str:
            raise EmbeddingServiceError(f"API authentication error: {str(e)}")
        elif "network" in error_str or "connection" in error_str or "timeout" in error_str:
            raise ServiceUnavailableError(f"Network connectivity error: {str(e)}")
        else:
            raise EmbeddingServiceError(f"Embedding service error: {str(e)}")

async def process_document(document_id: str, file_path: str):
    """
    Process a document with enhanced error handling, comprehensive logging, and graceful degradation.
    
    Args:
        document_id: UUID of the document to process
        file_path: Storage path of the document file
        
    Raises:
        DocumentProcessingError: If document processing fails
        VectorStoreError: If vector storage operations fail
    """
    client = get_service_client()
    rag_config, ai_config = get_rag_config()
    
    # Enhanced logging for document processing start
    logger.info(f"Starting document processing for document_id: {document_id}")
    logger.info(f"Processing configuration - chunk_size: {rag_config.chunk_size}, chunk_overlap: {rag_config.chunk_overlap}")
    
    processing_start_time = time.time()
    processing_stats = {
        "document_id": document_id,
        "start_time": datetime.utcnow().isoformat(),
        "file_path": file_path,
        "chunks_created": 0,
        "embedding_failures": 0,
        "total_processing_time": 0,
        "stages_completed": []
    }
    
    try:
        # Stage 1: Get document details and verify it's approved
        logger.info(f"Stage 1: Retrieving document details for {document_id}")
        try:
            doc_res = client.table("documents").select("college_id, status, filename, uploaded_by").eq("id", document_id).execute()
            if not doc_res.data:
                raise DocumentProcessingError(f"Document {document_id} not found in database")
            
            document = doc_res.data[0]
            college_id = document["college_id"]
            filename = document["filename"]
            uploaded_by = document["uploaded_by"]
            
            processing_stats["college_id"] = college_id
            processing_stats["filename"] = filename
            processing_stats["uploaded_by"] = uploaded_by
            
            # Only process approved documents
            if document["status"] != "approved":
                raise DocumentProcessingError(f"Document {document_id} is not approved for processing. Current status: {document['status']}")

            logger.info(f"Document details retrieved: {filename} (college: {college_id})")
            processing_stats["stages_completed"].append("document_details_retrieved")
            
        except DocumentProcessingError:
            raise
        except Exception as e:
            error_msg = f"Failed to retrieve document details: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Database query error details: {traceback.format_exc()}")
            raise DocumentProcessingError(error_msg)

        # Stage 2: Update status to 'processing' before starting
        logger.info(f"Stage 2: Updating document status to processing")
        try:
            client.table("documents").update({"status": "processing"}).eq("id", document_id).execute()
            processing_stats["stages_completed"].append("status_updated_to_processing")
        except Exception as e:
            error_msg = f"Failed to update document status to processing: {str(e)}"
            logger.error(error_msg)
            raise DocumentProcessingError(error_msg)

        # Stage 3: Download file with enhanced error handling and retry logic
        logger.info(f"Stage 3: Downloading file from storage path: {file_path}")
        file_content = None
        download_attempts = 0
        max_download_attempts = 3
        
        while download_attempts < max_download_attempts:
            try:
                file_content = client.storage.from_("documents").download(file_path)
                if not file_content:
                    raise DocumentProcessingError("Downloaded file is empty")
                
                logger.info(f"File downloaded successfully: {len(file_content)} bytes")
                processing_stats["file_size_bytes"] = len(file_content)
                processing_stats["stages_completed"].append("file_downloaded")
                break
                
            except Exception as e:
                download_attempts += 1
                error_msg = f"Download attempt {download_attempts}/{max_download_attempts} failed: {str(e)}"
                logger.warning(error_msg)
                
                if download_attempts >= max_download_attempts:
                    logger.error(f"All download attempts failed for document {document_id}")
                    raise DocumentProcessingError(f"Failed to download file from storage after {max_download_attempts} attempts: {str(e)}")
                
                # Wait before retry
                await asyncio.sleep(2 ** download_attempts)  # Exponential backoff
        
        # Stage 4: Extract Text with enhanced error handling
        logger.info(f"Stage 4: Extracting text from PDF")
        try:
            text = extract_text_from_pdf(file_content)
            processing_stats["extracted_text_length"] = len(text)
            processing_stats["stages_completed"].append("text_extracted")
            logger.info(f"Text extracted successfully: {len(text)} characters")
        except DocumentProcessingError:
            raise
        except Exception as e:
            error_msg = f"Text extraction failed: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Text extraction error details: {traceback.format_exc()}")
            raise DocumentProcessingError(error_msg)

        # Stage 5: Split text into chunks with enhanced error handling
        logger.info(f"Stage 5: Splitting text into chunks")
        try:
            text_chunks = chunk_text(text, rag_config.chunk_size, rag_config.chunk_overlap)
            processing_stats["total_chunks"] = len(text_chunks)
            processing_stats["stages_completed"].append("text_chunked")
            logger.info(f"Text split into {len(text_chunks)} chunks")
        except DocumentProcessingError:
            raise
        except Exception as e:
            error_msg = f"Text chunking failed: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Text chunking error details: {traceback.format_exc()}")
            raise DocumentProcessingError(error_msg)
        
        # Stage 6: Generate embeddings and store chunks with enhanced error handling
        logger.info(f"Stage 6: Generating embeddings and storing chunks")
        chunks_to_insert = []
        chunk_counter = 0
        embedding_failures = 0
        embedding_successes = 0
        
        # Process chunks in batches to avoid overwhelming the embedding service
        batch_size = 10
        for batch_start in range(0, len(text_chunks), batch_size):
            batch_end = min(batch_start + batch_size, len(text_chunks))
            batch_chunks = text_chunks[batch_start:batch_end]
            
            logger.info(f"Processing chunk batch {batch_start//batch_size + 1}/{(len(text_chunks) + batch_size - 1)//batch_size} ({len(batch_chunks)} chunks)")
            
            for chunk_content in batch_chunks:
                if not chunk_content.strip():
                    continue  # Skip empty chunks, but don't increment counter
                
                try:
                    embedding = generate_embedding(chunk_content)
                    
                    chunk_data = {
                        "document_id": document_id,
                        "college_id": college_id,
                        "content": chunk_content,
                        "embedding": embedding,
                        "metadata": {
                            "chunk_index": chunk_counter,
                            "chunk_length": len(chunk_content),
                            "processing_timestamp": datetime.utcnow().isoformat()
                        }
                    }
                    chunks_to_insert.append(chunk_data)
                    chunk_counter += 1
                    embedding_successes += 1
                    
                    if chunk_counter % 10 == 0:
                        logger.info(f"Processed {chunk_counter} chunks successfully")
                    
                except (EmbeddingServiceError, RateLimitError, ServiceUnavailableError, CircuitBreakerError) as e:
                    embedding_failures += 1
                    logger.warning(f"Failed to generate embedding for chunk {chunk_counter}: {str(e)}")
                    
                    # Enhanced failure handling with different strategies based on error type
                    if isinstance(e, RateLimitError):
                        logger.warning(f"Rate limit encountered, waiting before continuing...")
                        await asyncio.sleep(30)  # Wait 30 seconds for rate limit
                    elif isinstance(e, CircuitBreakerError):
                        logger.error(f"Circuit breaker is open for embedding service, stopping processing")
                        break
                    
                    # If too many embedding failures, fail the entire process
                    failure_rate = embedding_failures / (embedding_failures + embedding_successes) if (embedding_failures + embedding_successes) > 0 else 1.0
                    if failure_rate > 0.5 and embedding_failures > 5:  # More than 50% failures and at least 5 failures
                        error_msg = f"Too many embedding failures ({embedding_failures}/{embedding_failures + embedding_successes}) - failure rate: {failure_rate:.2%}"
                        logger.error(error_msg)
                        raise DocumentProcessingError(error_msg)
                    
                    continue
                except Exception as e:
                    embedding_failures += 1
                    logger.error(f"Unexpected error generating embedding for chunk {chunk_counter}: {str(e)}")
                    logger.error(f"Embedding error details: {traceback.format_exc()}")
                    continue
            
            # Small delay between batches to be respectful to the API
            if batch_end < len(text_chunks):
                await asyncio.sleep(1)
        
        processing_stats["chunks_created"] = len(chunks_to_insert)
        processing_stats["embedding_failures"] = embedding_failures
        processing_stats["embedding_successes"] = embedding_successes
        
        if not chunks_to_insert:
            error_msg = f"No chunks could be processed successfully. Embedding failures: {embedding_failures}, Successes: {embedding_successes}"
            logger.error(error_msg)
            raise DocumentProcessingError(error_msg)
        
        logger.info(f"Successfully processed {len(chunks_to_insert)} chunks with {embedding_failures} failures")
        processing_stats["stages_completed"].append("embeddings_generated")
        
        # Stage 7: Insert all chunks at once with enhanced error handling
        logger.info(f"Stage 7: Storing {len(chunks_to_insert)} chunks in database")
        try:
            # Insert in smaller batches to avoid database limits
            insert_batch_size = 50
            total_inserted = 0
            
            for batch_start in range(0, len(chunks_to_insert), insert_batch_size):
                batch_end = min(batch_start + insert_batch_size, len(chunks_to_insert))
                batch_data = chunks_to_insert[batch_start:batch_end]
                
                try:
                    client.table("document_chunks").insert(batch_data).execute()
                    total_inserted += len(batch_data)
                    logger.debug(f"Inserted batch {batch_start//insert_batch_size + 1}: {len(batch_data)} chunks")
                except Exception as e:
                    logger.error(f"Failed to insert chunk batch {batch_start//insert_batch_size + 1}: {str(e)}")
                    raise VectorStoreError(f"Failed to store chunk batch in database: {str(e)}")
            
            logger.info(f"Successfully stored {total_inserted} chunks in database for document {filename}")
            processing_stats["stages_completed"].append("chunks_stored")
            
        except VectorStoreError:
            raise
        except Exception as e:
            error_msg = f"Failed to store chunks in database: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Database insertion error details: {traceback.format_exc()}")
            raise VectorStoreError(error_msg)
        
        # Stage 8: Update Status to completed with processed timestamp and statistics
        logger.info(f"Stage 8: Updating document status to completed")
        try:
            processing_stats["total_processing_time"] = time.time() - processing_start_time
            processing_stats["end_time"] = datetime.utcnow().isoformat()
            
            client.table("documents").update({
                "status": "completed",
                "processed_at": datetime.utcnow().isoformat(),
                "processing_stats": processing_stats
            }).eq("id", document_id).execute()
            
            processing_stats["stages_completed"].append("status_updated_to_completed")
            
        except Exception as e:
            logger.error(f"Failed to update document status to completed: {str(e)}")
            # Don't fail the entire process for status update failure, but log it
        
        # Stage 9: Create notification for successful processing
        logger.info(f"Stage 9: Creating success notification")
        try:
            if uploaded_by:
                from app.core.notifications import notification_manager
                from app.models.notification import NotificationType
                
                await notification_manager.create_document_notification(
                    recipient_ids=[UUID(uploaded_by)],
                    notification_type=NotificationType.DOCUMENT_PROCESSED,
                    document_id=UUID(document_id),
                    document_filename=filename,
                    additional_metadata={
                        "processed_at": datetime.utcnow().isoformat(),
                        "chunks_created": len(chunks_to_insert),
                        "embedding_failures": embedding_failures,
                        "processing_time_seconds": processing_stats["total_processing_time"]
                    }
                )
                processing_stats["stages_completed"].append("success_notification_sent")
        except Exception as e:
            # Log notification error but don't fail the processing
            logger.warning(f"Failed to create processing completion notification: {str(e)}")

        # Final success logging
        logger.info(f"Successfully completed processing document {document_id} ({filename})")
        logger.info(f"Processing summary: {len(chunks_to_insert)} chunks created, {embedding_failures} embedding failures, {processing_stats['total_processing_time']:.2f}s total time")

    except (DocumentProcessingError, VectorStoreError, EmbeddingServiceError):
        raise
    except Exception as e:
        error_msg = f"Unexpected error processing document {document_id}: {str(e)}"
        logger.error(error_msg)
        logger.error(f"Unexpected error details: {traceback.format_exc()}")
        raise DocumentProcessingError(error_msg)
    
    finally:
        # Enhanced cleanup and failure handling
        try:
            # Check if processing failed and update status accordingly
            doc_res = client.table("documents").select("status").eq("id", document_id).execute()
            if doc_res.data and doc_res.data[0]["status"] == "processing":
                # If still in processing state, something went wrong
                processing_stats["total_processing_time"] = time.time() - processing_start_time
                processing_stats["end_time"] = datetime.utcnow().isoformat()
                processing_stats["failed"] = True
                
                error_msg = "Processing failed due to unexpected error"
                
                # Get document details for notification (if available)
                try:
                    doc_res = client.table("documents").select("filename, uploaded_by").eq("id", document_id).execute()
                    if doc_res.data:
                        filename = doc_res.data[0]["filename"]
                        uploaded_by = doc_res.data[0]["uploaded_by"]
                    else:
                        filename = "Unknown Document"
                        uploaded_by = None
                except:
                    filename = "Unknown Document"
                    uploaded_by = None
                
                # Update document status to failed with detailed error information
                client.table("documents").update({
                    "status": "failed", 
                    "error_message": error_msg,
                    "processing_stats": processing_stats,
                    "failed_at": datetime.utcnow().isoformat()
                }).eq("id", document_id).execute()
                
                logger.error(f"Document {document_id} marked as failed with processing stats: {processing_stats}")
                
                # Create notification for processing failure
                try:
                    if uploaded_by:
                        from app.core.notifications import notification_manager
                        from app.models.notification import NotificationType
                        
                        await notification_manager.create_document_notification(
                            recipient_ids=[UUID(uploaded_by)],
                            notification_type=NotificationType.DOCUMENT_FAILED,
                            document_id=UUID(document_id),
                            document_filename=filename,
                            additional_metadata={
                                "error_message": error_msg,
                                "processing_stats": processing_stats,
                                "failed_at": datetime.utcnow().isoformat()
                            }
                        )
                except Exception as notification_error:
                    logger.warning(f"Failed to create processing failure notification: {str(notification_error)}")
                    
        except Exception as cleanup_error:
            logger.error(f"Error during cleanup for document {document_id}: {str(cleanup_error)}")
            logger.error(f"Cleanup error details: {traceback.format_exc()}")

async def trigger_rag_processing(document_id: str):
    """
    Trigger RAG processing for an approved document with enhanced error handling.
    
    Args:
        document_id: UUID of the document to process
        
    Raises:
        DocumentProcessingError: If processing cannot be triggered
    """
    client = get_service_client()
    
    try:
        # Get document details
        doc_res = client.table("documents").select("storage_path, status, filename").eq("id", document_id).execute()
        if not doc_res.data:
            raise DocumentProcessingError(f"Document {document_id} not found")
        
        document = doc_res.data[0]
        filename = document.get("filename", "Unknown")
        
        # Verify document is approved
        if document["status"] != "approved":
            raise DocumentProcessingError(f"Document {document_id} ({filename}) is not approved for processing. Current status: {document['status']}")
        
        if not document.get("storage_path"):
            raise DocumentProcessingError(f"Document {document_id} ({filename}) has no storage path")
        
        logger.info(f"Triggering RAG processing for document {document_id} ({filename})")
        
        # Start processing
        await process_document(document_id, document["storage_path"])
        
    except (DocumentProcessingError, VectorStoreError, EmbeddingServiceError):
        raise
    except Exception as e:
        error_msg = f"Failed to trigger processing: {str(e)}"
        logger.error(f"Error triggering RAG processing for document {document_id}: {error_msg}")
        
        # Update document status to failed
        try:
            client.table("documents").update({
                "status": "failed",
                "error_message": error_msg
            }).eq("id", document_id).execute()
        except Exception as update_error:
            logger.error(f"Failed to update document status after trigger failure: {str(update_error)}")
        
        raise DocumentProcessingError(error_msg)


async def _check_vector_storage_integrity(client, college_id: str) -> None:
    """
    Check vector storage integrity for a college.
    
    Args:
        client: Supabase client
        college_id: College ID to check
        
    Raises:
        VectorStoreError: If integrity issues are found
    """
    try:
        # Check for chunks without embeddings
        chunks_without_embeddings = client.table("document_chunks").select(
            "id, document_id"
        ).eq("college_id", college_id).is_("embedding", "null").execute()
        
        if chunks_without_embeddings.data:
            logger.warning(f"Found {len(chunks_without_embeddings.data)} chunks without embeddings for college {college_id}")
        
        # Check for orphaned chunks (chunks without valid documents)
        orphaned_chunks = client.table("document_chunks").select(
            "id, document_id"
        ).eq("college_id", college_id).execute()
        
        if orphaned_chunks.data:
            document_ids = [chunk["document_id"] for chunk in orphaned_chunks.data]
            valid_docs = client.table("documents").select("id").in_("id", document_ids).execute()
            valid_doc_ids = {doc["id"] for doc in valid_docs.data}
            
            orphaned_count = sum(1 for chunk in orphaned_chunks.data 
                               if chunk["document_id"] not in valid_doc_ids)
            
            if orphaned_count > 0:
                logger.warning(f"Found {orphaned_count} orphaned chunks for college {college_id}")
        
        # Check for embedding dimension consistency
        chunks_with_embeddings = client.table("document_chunks").select(
            "id, embedding"
        ).eq("college_id", college_id).not_.is_("embedding", "null").limit(10).execute()
        
        if chunks_with_embeddings.data:
            expected_dim = 768  # Google Gemini embedding dimension
            for chunk in chunks_with_embeddings.data:
                if chunk.get("embedding") and len(chunk["embedding"]) != expected_dim:
                    raise VectorStoreError(f"Embedding dimension mismatch: expected {expected_dim}, got {len(chunk['embedding'])}")
        
    except Exception as e:
        if isinstance(e, VectorStoreError):
            raise
        logger.error(f"Vector storage integrity check failed: {str(e)}")
        raise VectorStoreError(f"Integrity check failed: {str(e)}")


async def _retrieve_chunks_with_native_search(
    client, query_embedding: List[float], college_id: str, 
    top_k: int, similarity_threshold: float
) -> Optional[List[dict]]:
    """
    Retrieve chunks using native pgvector search function.
    
    Returns:
        List of chunks if successful, None if function doesn't exist
    """
    try:
        # Try to use the match_documents RPC function
        result = client.rpc("match_documents", {
            "query_embedding": query_embedding,
            "target_college_id": college_id,
            "match_threshold": similarity_threshold,
            "match_count": top_k
        }).execute()
        
        if not result.data:
            return []
        
        # Get document filenames for the results
        document_ids = list(set([chunk["document_id"] for chunk in result.data]))
        docs_response = client.table("documents").select(
            "id, filename"
        ).in_("id", document_ids).eq("status", "completed").execute()
        doc_map = {doc["id"]: doc["filename"] for doc in docs_response.data}
        
        # Format results to match expected structure
        formatted_chunks = []
        for chunk in result.data:
            if chunk["document_id"] in doc_map:
                metadata = chunk.get("metadata", {}) if chunk.get("metadata") else {}
                formatted_chunks.append({
                    "id": chunk["id"],
                    "document_id": chunk["document_id"],
                    "college_id": chunk["college_id"],
                    "content": chunk["content"],
                    "chunk_index": metadata.get("chunk_index", 0),
                    "filename": doc_map[chunk["document_id"]],
                    "similarity": chunk["similarity"]
                })
        
        return formatted_chunks
        
    except Exception as e:
        # If RPC function doesn't exist or fails, return None to trigger fallback
        logger.debug(f"Native vector search failed: {str(e)}")
        return None


async def _retrieve_chunks_with_python_search(
    client, query_embedding: List[float], college_id: str, 
    top_k: int, similarity_threshold: float
) -> List[dict]:
    """
    Retrieve chunks using Python-based similarity calculation (fallback method).
    """
    # Fetch all chunks for the college with better error handling
    try:
        all_chunks_response = client.table("document_chunks").select(
            "id, document_id, college_id, content, embedding, metadata"
        ).eq("college_id", college_id).not_.is_("embedding", "null").execute()
    except Exception as e:
        raise VectorStoreError(f"Failed to fetch chunks from database: {str(e)}")
    
    if not all_chunks_response.data:
        logger.info(f"No chunks found for college {college_id}")
        return []
    
    # Get document info with error handling
    try:
        document_ids = list(set([chunk["document_id"] for chunk in all_chunks_response.data]))
        docs_response = client.table("documents").select(
            "id, filename, status"
        ).in_("id", document_ids).eq("status", "completed").execute()
        doc_map = {doc["id"]: doc["filename"] for doc in docs_response.data}
    except Exception as e:
        raise VectorStoreError(f"Failed to fetch document information: {str(e)}")
    
    # Calculate cosine similarity for each chunk with enhanced error handling
    def cosine_similarity(vec1: list, vec2: list) -> float:
        """Calculate cosine similarity between two vectors with error handling"""
        try:
            vec1_arr = np.array(vec1, dtype=np.float32)
            vec2_arr = np.array(vec2, dtype=np.float32)
            
            # Check for valid vectors
            if vec1_arr.size == 0 or vec2_arr.size == 0:
                return 0.0
            
            dot_product = np.dot(vec1_arr, vec2_arr)
            norm1 = np.linalg.norm(vec1_arr)
            norm2 = np.linalg.norm(vec2_arr)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
                
            return float(dot_product / (norm1 * norm2))
        except Exception as e:
            logger.warning(f"Similarity calculation failed: {str(e)}")
            return 0.0
    
    # Score and filter chunks
    scored_chunks = []
    processing_errors = 0
    
    for chunk in all_chunks_response.data:
        try:
            # Skip chunks from documents not in completed status
            if chunk["document_id"] not in doc_map:
                continue
            
            # Skip chunks without embeddings (should be filtered by query, but double-check)
            if not chunk.get("embedding"):
                continue
            
            # Validate embedding dimensions
            if len(chunk["embedding"]) != len(query_embedding):
                logger.warning(f"Embedding dimension mismatch for chunk {chunk['id']}")
                continue
            
            similarity = cosine_similarity(query_embedding, chunk["embedding"])
            
            if similarity >= similarity_threshold:
                metadata = chunk.get("metadata", {}) if chunk.get("metadata") else {}
                scored_chunks.append({
                    "id": chunk["id"],
                    "document_id": chunk["document_id"],
                    "college_id": chunk["college_id"],
                    "content": chunk["content"],
                    "chunk_index": metadata.get("chunk_index", 0),
                    "filename": doc_map[chunk["document_id"]],
                    "similarity": similarity
                })
        except Exception as e:
            processing_errors += 1
            logger.warning(f"Error processing chunk {chunk.get('id', 'unknown')}: {str(e)}")
            continue
    
    if processing_errors > 0:
        logger.warning(f"Encountered {processing_errors} errors while processing chunks")
    
    # Sort by similarity (highest first) and take top_k
    scored_chunks.sort(key=lambda x: x["similarity"], reverse=True)
    result_chunks = scored_chunks[:top_k]
    
    return result_chunks

async def retrieve_relevant_chunks(
    query: str, 
    college_id: str, 
    top_k: int = None,
    similarity_threshold: float = None
) -> List[dict]:
    """
    Retrieve relevant document chunks for a query using enhanced vector similarity search.
    
    Args:
        query: User's question
        college_id: Filter chunks by college
        top_k: Number of chunks to retrieve (uses config default if None)
        similarity_threshold: Minimum similarity score (uses config default if None)
    
    Returns:
        List of relevant chunks with metadata
        
    Raises:
        VectorStoreError: If vector storage operations fail
        EmbeddingServiceError: If embedding generation fails
    """
    if not query.strip():
        logger.warning("Empty query provided to retrieve_relevant_chunks")
        return []
    
    rag_config, ai_config = get_rag_config()
    top_k = top_k if top_k is not None else rag_config.max_chunks_per_query
    similarity_threshold = similarity_threshold if similarity_threshold is not None else rag_config.similarity_threshold
    
    if not ai_config.gemini_api_key:
        logger.warning("GEMINI_API_KEY not configured - cannot retrieve chunks")
        raise VectorStoreError("Vector search service not configured")
    
    try:
        client = get_service_client()
        
        # 1. Validate inputs with enhanced error handling
        try:
            UUID(college_id)  # Validate UUID format
        except (ValueError, TypeError) as e:
            raise VectorStoreError(f"Invalid college_id format: {college_id}")
        
        # Ensure parameters are within safe and reasonable ranges
        top_k = max(1, min(top_k, 50))  # Limit between 1-50
        similarity_threshold = max(0.0, min(similarity_threshold, 1.0))  # Limit between 0-1
        
        # 2. Generate embedding for the query with enhanced error handling
        try:
            query_embedding = generate_embedding(query)
        except EmbeddingServiceError as e:
            logger.error(f"Failed to generate query embedding: {str(e)}")
            raise VectorStoreError(f"Query embedding generation failed: {str(e)}")
        
        if not query_embedding or len(query_embedding) == 0:
            raise VectorStoreError("Empty query embedding generated")
        
        # 3. Perform vector storage integrity check
        try:
            await _check_vector_storage_integrity(client, college_id)
        except VectorStoreError as e:
            logger.warning(f"Vector storage integrity check failed: {str(e)}")
            # Continue with retrieval but log the issue
        
        # 4. Try to use native pgvector function first (optimized path)
        try:
            result_chunks = await _retrieve_chunks_with_native_search(
                client, query_embedding, college_id, top_k, similarity_threshold
            )
            if result_chunks is not None:
                logger.info(f"Retrieved {len(result_chunks)} chunks using native vector search")
                return result_chunks
        except Exception as e:
            logger.warning(f"Native vector search failed, falling back to Python implementation: {str(e)}")
        
        # 5. Fallback to Python-based similarity calculation
        result_chunks = await _retrieve_chunks_with_python_search(
            client, query_embedding, college_id, top_k, similarity_threshold
        )
        
        logger.info(f"Retrieved {len(result_chunks)} relevant chunks for query: '{query[:50]}...'")
        return result_chunks
        
        # 1. Generate embedding for the query with retry logic
        try:
            query_embedding = generate_embedding(query)
        except EmbeddingServiceError as e:
            logger.error(f"Failed to generate query embedding: {str(e)}")
            raise
        
        if not query_embedding:
            raise EmbeddingServiceError("Empty query embedding generated")
        
        # Validate and sanitize inputs to prevent injection attacks
        # college_id should be a valid UUID string
        try:
            UUID(college_id)  # Validate UUID format
        except (ValueError, TypeError):
            raise ValueError(f"Invalid college_id format: {college_id}")
        
        # Ensure top_k and similarity_threshold are within safe ranges
        top_k = max(1, min(top_k, 50))  # Limit between 1-50
        similarity_threshold = max(0.0, min(similarity_threshold, 1.0))  # Limit between 0-1
        
        # Note: For production, use pgvector's native similarity search for better performance
        # To implement native pgvector search safely, create a PostgreSQL function that uses
        # parameterized queries. Example:
        # CREATE OR REPLACE FUNCTION match_document_chunks(
        #   query_embedding vector(768),
        #   target_college_id uuid,
        #   match_threshold float,
        #   match_count int
        # ) RETURNS TABLE(...) AS $$ ... $$ LANGUAGE sql;
        
        # Current implementation: Fetch chunks and calculate similarity in Python
        # This is safe from SQL injection as it uses Supabase's parameterized queries
        all_chunks_response = client.table("document_chunks").select(
            "id, document_id, college_id, content, embedding, metadata"
        ).eq("college_id", college_id).execute()
        
        # This is the old implementation - should not be reached due to the new implementation above
        # But keeping it as fallback for now
        return []
        
    except (VectorStoreError, EmbeddingServiceError):
        raise
    except Exception as e:
        logger.error(f"Unexpected error retrieving chunks: {str(e)}")
        raise VectorStoreError(f"Chunk retrieval failed: {str(e)}")


@retry_with_backoff(service_name="gemini_generation")
async def generate_rag_response(
    query: str,
    college_id: str,
    context_chunks: List[dict] = None,
    conversation_history: List[dict] = None
) -> dict:
    """
    Generate a response using RAG with enhanced fallback mechanisms, comprehensive error handling,
    and graceful degradation for service failures.
    
    Args:
        query: User's question
        college_id: College ID for filtering documents
        context_chunks: Pre-retrieved chunks (if None, will retrieve automatically)
        conversation_history: Previous messages for context maintenance
    
    Returns:
        Dictionary with enhanced response, sources, and metadata including fallback information
        
    Raises:
        EmbeddingServiceError: If AI service fails
        VectorStoreError: If chunk retrieval fails
        CircuitBreakerError: If service is temporarily unavailable
    """
    if not query.strip():
        return {
            "response": "Please provide a question to get started.",
            "sources": [],
            "source_details": [],
            "fallback_used": False,
            "quality_score": 0.0,
            "error_details": None
        }
    
    rag_config, ai_config = get_rag_config()
    health_manager = get_service_health_manager()
    
    # Enhanced logging for RAG response generation
    logger.info(f"Generating RAG response for query: '{query[:100]}...' (college: {college_id})")
    response_start_time = time.time()
    
    # Check if AI service is available
    if not ai_config.gemini_api_key or ai_config.gemini_api_key == "REPLACE_WITH_YOUR_VALID_GEMINI_API_KEY":
        logger.warning("GEMINI_API_KEY not configured or using placeholder - falling back to basic response")
        from app.core.basic_chat import generate_basic_response
        basic_result = await generate_basic_response(query, college_id)
        basic_result["fallback_used"] = True
        basic_result["fallback_reason"] = "AI service not configured"
        return basic_result
    
    # Check circuit breaker for embedding service
    if health_manager.is_circuit_breaker_open("gemini_embedding"):
        logger.warning("Embedding service circuit breaker is open - falling back to basic response")
        from app.core.basic_chat import generate_basic_response
        basic_result = await generate_basic_response(query, college_id)
        basic_result["fallback_used"] = True
        basic_result["fallback_reason"] = "Embedding service circuit breaker open"
        return basic_result
    
    # Check circuit breaker for generation service
    if health_manager.is_circuit_breaker_open("gemini_generation"):
        logger.warning("Generation service circuit breaker is open - falling back to basic response")
        from app.core.basic_chat import generate_basic_response
        basic_result = await generate_basic_response(query, college_id)
        basic_result["fallback_used"] = True
        basic_result["fallback_reason"] = "Generation service circuit breaker open"
        return basic_result

    try:
        # Stage 1: Retrieve relevant chunks if not provided
        if context_chunks is None:
            try:
                logger.info(f"Retrieving relevant chunks for query")
                context_chunks = await retrieve_relevant_chunks(
                    query, 
                    college_id, 
                    top_k=rag_config.max_chunks_per_query, 
                    similarity_threshold=rag_config.similarity_threshold
                )
                logger.info(f"Retrieved {len(context_chunks)} relevant chunks")
                
            except (VectorStoreError, EmbeddingServiceError, CircuitBreakerError) as e:
                logger.error(f"Failed to retrieve chunks: {str(e)}")
                logger.error(f"Chunk retrieval error details: {traceback.format_exc()}")
                
                # Fallback to basic chat for chunk retrieval failures
                logger.info("Falling back to basic chat due to chunk retrieval failure")
                from app.core.basic_chat import generate_basic_response
                basic_result = await generate_basic_response(query, college_id)
                basic_result["fallback_used"] = True
                basic_result["fallback_reason"] = f"Chunk retrieval failed: {str(e)}"
                basic_result["error_details"] = str(e)
                return basic_result
            
            except Exception as e:
                logger.error(f"Unexpected error during chunk retrieval: {str(e)}")
                logger.error(f"Unexpected chunk retrieval error details: {traceback.format_exc()}")
                
                # Fallback to basic chat for unexpected errors
                from app.core.basic_chat import generate_basic_response
                basic_result = await generate_basic_response(query, college_id)
                basic_result["fallback_used"] = True
                basic_result["fallback_reason"] = f"Unexpected chunk retrieval error: {str(e)}"
                basic_result["error_details"] = str(e)
                return basic_result
        
        # Stage 2: Handle case where no relevant chunks are found
        if not context_chunks:
            logger.info("No relevant chunks found for query")
            return {
                "response": "I couldn't find relevant information in the available documents to answer your question. Please try rephrasing or contact your college administration for more details.",
                "sources": [],
                "source_details": [],
                "fallback_used": False,
                "quality_score": 0.0,
                "no_relevant_content": True
            }
        
        # Stage 3: Enhanced context formatting with comprehensive error handling
        try:
            logger.info(f"Formatting context from {len(context_chunks)} chunks")
            formatted_context_sections = []
            source_details = []
            
            for i, chunk in enumerate(context_chunks):
                if not chunk.get('filename') or not chunk.get('content'):
                    logger.warning(f"Skipping chunk {i} due to missing filename or content")
                    continue
                
                # Create detailed source information
                source_detail = {
                    "filename": chunk['filename'],
                    "similarity_score": round(chunk.get('similarity', 0.0), 3),
                    "chunk_index": chunk.get('chunk_index', i),
                    "document_id": chunk.get('document_id'),
                    "relevance_rank": i + 1
                }
                source_details.append(source_detail)
                
                # Format context with clear structure and metadata
                section_header = f"**Source {i+1}: {chunk['filename']}** (Relevance: {source_detail['similarity_score']:.1%})"
                section_content = chunk['content'].strip()
                
                formatted_section = f"{section_header}\n{section_content}"
                formatted_context_sections.append(formatted_section)
            
            if not formatted_context_sections:
                logger.warning("No valid content found in chunks after formatting")
                return {
                    "response": "I found relevant documents but couldn't process their content. Please try again or contact support.",
                    "sources": [],
                    "source_details": [],
                    "fallback_used": False,
                    "quality_score": 0.0,
                    "context_formatting_failed": True
                }
            
            # Join sections with clear separators
            context_text = "\n\n" + "="*50 + "\n\n".join(formatted_context_sections)
            logger.info(f"Context formatted successfully: {len(context_text)} characters")
            
        except Exception as e:
            logger.error(f"Failed to build enhanced context from chunks: {str(e)}")
            logger.error(f"Context formatting error details: {traceback.format_exc()}")
            
            # Fallback to basic chat for context formatting failures
            from app.core.basic_chat import generate_basic_response
            basic_result = await generate_basic_response(query, college_id)
            basic_result["fallback_used"] = True
            basic_result["fallback_reason"] = f"Context formatting failed: {str(e)}"
            basic_result["error_details"] = str(e)
            return basic_result
        
        # Stage 4: Get unique source documents with enhanced metadata
        sources = list(set([
            chunk['filename'] for chunk in context_chunks 
            if chunk.get('filename')
        ]))
        
        # Stage 5: Build conversation context for continuity
        conversation_context = ""
        if conversation_history and len(conversation_history) > 0:
            try:
                # Include last 3 exchanges for context while keeping prompt manageable
                recent_history = conversation_history[-6:]  # Last 3 user-assistant pairs
                
                conversation_parts = []
                for msg in recent_history:
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '').strip()
                    if content and role in ['user', 'assistant']:
                        # Truncate very long messages to keep context manageable
                        if len(content) > 200:
                            content = content[:200] + "..."
                        conversation_parts.append(f"{role.title()}: {content}")
                
                if conversation_parts:
                    conversation_context = f"""
**Previous Conversation Context:**
{chr(10).join(conversation_parts)}

**Current Question Context:**
The user is now asking a new question that may relate to the previous conversation.
"""
                    logger.info(f"Conversation context built: {len(conversation_parts)} messages")
                    
            except Exception as e:
                logger.warning(f"Failed to build conversation context: {str(e)}")
                conversation_context = ""  # Continue without conversation context
        
        # Stage 6: Enhanced prompt with better structure and quality guidelines
        prompt = f"""You are a helpful college information assistant. Answer the user's question based ONLY on the provided context from college documents.

**Instructions:**
1. Use ONLY information from the provided context. Do not use external knowledge.
2. Maintain conversation continuity by referencing previous context when relevant.
3. Format your answer clearly with proper structure:
   - Use bullet points or numbered lists when listing items
   - Use bold text for important terms (use **term**)
   - Maintain proper formatting for course codes, credits, subjects
   - If listing courses/subjects, present them in a clear table-like format
4. If the context contains structured data (like course lists), preserve that structure in your answer.
5. Be concise but comprehensive.
6. If information is missing, clearly state what is not available.
7. Always cite your sources by mentioning the document name when referencing specific information.

{conversation_context}

**Document Context (ranked by relevance):**
{context_text}

**User Question:**
{query}

**Your Answer (cite sources when referencing specific information):**"""
        
        # Stage 7: Generate response using Gemini with enhanced error handling and fallback
        try:
            logger.info("Generating AI response using Gemini")
            model = genai.GenerativeModel(ai_config.generation_model)
            response = model.generate_content(prompt)
            
            if not response or not response.text:
                raise EmbeddingServiceError("Empty response from AI service")
            
            response_text = response.text.strip()
            
            if not response_text:
                raise EmbeddingServiceError("AI service returned empty response")
            
            logger.info(f"AI response generated successfully: {len(response_text)} characters")
            
        except Exception as e:
            logger.error(f"AI response generation failed: {str(e)}")
            logger.error(f"AI generation error details: {traceback.format_exc()}")
            
            # Enhanced error classification for better fallback handling
            error_str = str(e).lower()
            if "quota" in error_str or "rate" in error_str:
                logger.warning("Rate limit detected in AI generation - falling back to basic response")
                from app.core.basic_chat import generate_basic_response
                basic_result = await generate_basic_response(query, college_id)
                basic_result["fallback_used"] = True
                basic_result["fallback_reason"] = f"AI service rate limit: {str(e)}"
                basic_result["error_details"] = str(e)
                return basic_result
            elif "api" in error_str or "key" in error_str or "auth" in error_str:
                logger.error("AI service authentication error - falling back to basic response")
                from app.core.basic_chat import generate_basic_response
                basic_result = await generate_basic_response(query, college_id)
                basic_result["fallback_used"] = True
                basic_result["fallback_reason"] = f"AI service authentication error: {str(e)}"
                basic_result["error_details"] = str(e)
                return basic_result
            else:
                logger.error("General AI service error - falling back to basic response")
                from app.core.basic_chat import generate_basic_response
                basic_result = await generate_basic_response(query, college_id)
                basic_result["fallback_used"] = True
                basic_result["fallback_reason"] = f"AI service error: {str(e)}"
                basic_result["error_details"] = str(e)
                return basic_result
        
        # Stage 8: Response quality validation
        try:
            quality_score = _validate_response_quality(response_text, context_chunks, query)
            logger.info(f"Response quality score: {quality_score:.2f}")
        except Exception as e:
            logger.warning(f"Response quality validation failed: {str(e)}")
            quality_score = 0.5  # Default score if validation fails
        
        # Stage 9: Final response assembly
        processing_time = time.time() - response_start_time
        
        logger.info(f"RAG response generated successfully in {processing_time:.2f}s using {len(context_chunks)} chunks from {len(sources)} sources (quality: {quality_score:.2f})")
        
        return {
            "response": response_text,
            "sources": sources,
            "source_details": source_details,
            "chunks_used": len(context_chunks),
            "fallback_used": False,
            "quality_score": quality_score,
            "conversation_context_used": bool(conversation_history),
            "processing_time": processing_time,
            "service_health": health_manager.get_all_service_status()
        }
        
    except (EmbeddingServiceError, VectorStoreError, CircuitBreakerError):
        # These are expected errors that should be re-raised for proper handling
        raise
    except Exception as e:
        logger.error(f"Unexpected error generating RAG response: {str(e)}")
        logger.error(f"Unexpected RAG error details: {traceback.format_exc()}")
        
        # Final fallback to basic chat for any unexpected errors
        try:
            from app.core.basic_chat import generate_basic_response
            basic_result = await generate_basic_response(query, college_id)
            basic_result["fallback_used"] = True
            basic_result["fallback_reason"] = f"Unexpected RAG error: {str(e)}"
            basic_result["error_details"] = str(e)
            return basic_result
        except Exception as fallback_error:
            logger.error(f"Even basic chat fallback failed: {str(fallback_error)}")
            # Return a minimal response as last resort
            return {
                "response": "I'm experiencing technical difficulties and cannot process your request right now. Please try again later or contact support.",
                "sources": [],
                "source_details": [],
                "fallback_used": True,
                "fallback_reason": f"All systems failed: RAG error: {str(e)}, Fallback error: {str(fallback_error)}",
                "quality_score": 0.0,
                "error_details": f"RAG: {str(e)}, Fallback: {str(fallback_error)}",
                "system_failure": True
            }


def _validate_response_quality(response_text: str, context_chunks: List[dict], query: str) -> float:
    """
    Validate response quality based on multiple criteria.
    
    Args:
        response_text: Generated response
        context_chunks: Source chunks used
        query: Original user query
    
    Returns:
        Quality score between 0.0 and 1.0
    """
    try:
        if not response_text or not response_text.strip():
            return 0.0
        
        quality_factors = []
        
        # 1. Response length appropriateness (not too short, not too long)
        response_length = len(response_text.strip())
        if 50 <= response_length <= 2000:
            length_score = 1.0
        elif response_length < 50:
            length_score = response_length / 50.0
        else:
            length_score = max(0.5, 2000 / response_length)
        quality_factors.append(length_score)
        
        # 2. Source citation check (mentions document names)
        source_names = [chunk.get('filename', '') for chunk in context_chunks if chunk.get('filename')]
        citations_found = sum(1 for source in source_names if source.lower() in response_text.lower())
        citation_score = min(1.0, citations_found / max(1, len(source_names)))
        quality_factors.append(citation_score)
        
        # 3. Query relevance (contains key terms from query)
        query_words = set(query.lower().split())
        response_words = set(response_text.lower().split())
        common_words = query_words.intersection(response_words)
        relevance_score = min(1.0, len(common_words) / max(1, len(query_words)))
        quality_factors.append(relevance_score)
        
        # 4. Structure quality (has proper formatting)
        structure_indicators = [
            '**' in response_text,  # Bold formatting
            '\n' in response_text,  # Line breaks
            any(marker in response_text for marker in ['•', '-', '1.', '2.', '*'])  # Lists
        ]
        structure_score = sum(structure_indicators) / len(structure_indicators)
        quality_factors.append(structure_score)
        
        # 5. Avoid generic responses
        generic_phrases = [
            "i don't have information",
            "please contact",
            "i cannot help",
            "i don't know"
        ]
        generic_count = sum(1 for phrase in generic_phrases if phrase in response_text.lower())
        generic_score = max(0.0, 1.0 - (generic_count * 0.3))
        quality_factors.append(generic_score)
        
        # Calculate weighted average
        weights = [0.15, 0.25, 0.25, 0.15, 0.20]  # Citation and relevance weighted higher
        quality_score = sum(factor * weight for factor, weight in zip(quality_factors, weights))
        
        return round(quality_score, 3)
        
    except Exception as e:
        logger.warning(f"Quality validation failed: {str(e)}")
        return 0.5  # Default middle score if validation fails


async def get_rag_system_health() -> Dict[str, Any]:
    """
    Get comprehensive health status of the RAG system including all services and components.
    
    Returns:
        Dictionary containing health status of all RAG system components
    """
    health_manager = get_service_health_manager()
    
    try:
        rag_config, ai_config = get_rag_config()
        client = get_service_client()
        
        health_status = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": "healthy",
            "services": health_manager.get_all_service_status(),
            "configuration": {
                "ai_service_configured": bool(ai_config.gemini_api_key),
                "embedding_model": ai_config.embedding_model,
                "generation_model": ai_config.generation_model,
                "chunk_size": rag_config.chunk_size,
                "similarity_threshold": rag_config.similarity_threshold,
                "max_chunks_per_query": rag_config.max_chunks_per_query
            },
            "database": {
                "status": "unknown",
                "total_documents": 0,
                "completed_documents": 0,
                "total_chunks": 0
            },
            "errors": []
        }
        
        # Test database connectivity
        try:
            doc_stats = client.table("documents").select("status", count="exact").execute()
            chunk_stats = client.table("document_chunks").select("id", count="exact").execute()
            
            health_status["database"]["status"] = "healthy"
            health_status["database"]["total_documents"] = doc_stats.count if hasattr(doc_stats, 'count') else len(doc_stats.data or [])
            health_status["database"]["total_chunks"] = chunk_stats.count if hasattr(chunk_stats, 'count') else len(chunk_stats.data or [])
            
            # Count completed documents
            if doc_stats.data:
                completed_count = sum(1 for doc in doc_stats.data if doc.get("status") == "completed")
                health_status["database"]["completed_documents"] = completed_count
            
        except Exception as e:
            health_status["database"]["status"] = "unhealthy"
            health_status["errors"].append(f"Database connectivity error: {str(e)}")
            health_status["overall_status"] = "degraded"
        
        # Test AI service connectivity if configured
        if ai_config.gemini_api_key:
            try:
                # Test embedding service
                test_embedding = generate_embedding("test")
                if test_embedding and len(test_embedding) > 0:
                    health_status["services"]["gemini_embedding"] = {
                        "status": "healthy",
                        "last_test": datetime.utcnow().isoformat()
                    }
                else:
                    health_status["services"]["gemini_embedding"] = {
                        "status": "unhealthy",
                        "error": "Empty embedding returned"
                    }
                    health_status["errors"].append("Embedding service returned empty result")
                    health_status["overall_status"] = "degraded"
                    
            except Exception as e:
                health_status["services"]["gemini_embedding"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                health_status["errors"].append(f"Embedding service error: {str(e)}")
                health_status["overall_status"] = "degraded"
        else:
            health_status["services"]["gemini_embedding"] = {
                "status": "not_configured",
                "message": "GEMINI_API_KEY not configured"
            }
            health_status["overall_status"] = "degraded"
        
        # Determine overall status
        unhealthy_services = sum(1 for service_status in health_status["services"].values() 
                               if isinstance(service_status, dict) and service_status.get("status") == "unhealthy")
        
        if unhealthy_services > 0:
            health_status["overall_status"] = "unhealthy" if unhealthy_services > 1 else "degraded"
        elif health_status["errors"]:
            health_status["overall_status"] = "degraded"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Failed to get RAG system health: {str(e)}")
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": "unhealthy",
            "error": f"Health check failed: {str(e)}",
            "services": {},
            "configuration": {},
            "database": {"status": "unknown"},
            "errors": [f"Health check system error: {str(e)}"]
        }


async def reset_service_health(service_name: str = None) -> Dict[str, Any]:
    """
    Reset health status for a specific service or all services.
    
    Args:
        service_name: Name of service to reset, or None to reset all
        
    Returns:
        Dictionary containing reset operation results
    """
    health_manager = get_service_health_manager()
    
    try:
        if service_name:
            # Reset specific service
            if service_name in health_manager._services:
                health = health_manager._services[service_name]
                health.is_healthy = True
                health.failure_count = 0
                health.circuit_breaker_open = False
                health.circuit_breaker_open_until = None
                health.last_failure = None
                
                logger.info(f"Reset health status for service: {service_name}")
                return {
                    "status": "success",
                    "message": f"Health status reset for service: {service_name}",
                    "service": service_name,
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                return {
                    "status": "error",
                    "message": f"Service not found: {service_name}",
                    "timestamp": datetime.utcnow().isoformat()
                }
        else:
            # Reset all services
            reset_count = 0
            for service_name, health in health_manager._services.items():
                health.is_healthy = True
                health.failure_count = 0
                health.circuit_breaker_open = False
                health.circuit_breaker_open_until = None
                health.last_failure = None
                reset_count += 1
            
            logger.info(f"Reset health status for {reset_count} services")
            return {
                "status": "success",
                "message": f"Health status reset for {reset_count} services",
                "services_reset": reset_count,
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Failed to reset service health: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to reset service health: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }
