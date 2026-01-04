from app.core.database import get_service_client
import google.generativeai as genai
import os
from io import BytesIO
from pypdf import PdfReader
from uuid import UUID
import re
from typing import List
import numpy as np

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

def extract_text_from_pdf(file_content: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(file_content))
        text = ""
        for page in reader.pages:
            if page_text := page.extract_text():
                text += page_text + "\n"
        return text
    except Exception as e:
        print(f"Error extracting text: {e}")
        return ""

def chunk_text(text: str, chunk_size: int = 1500, chunk_overlap: int = 300) -> List[str]:
    """
    Split text into overlapping chunks for better context retention.
    
    Args:
        text: The text to chunk
        chunk_size: Maximum characters per chunk (default 1500 - good for course catalogs)
        chunk_overlap: Characters to overlap between chunks (default 300 - maintains context)
    
    Returns:
        List of text chunks
    """
    if not text or len(text) <= chunk_size:
        return [text] if text else []
    
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
    
    # Fallback: if sentence splitting didn't work well, use simple character-based splitting
    if len(chunks) == 0:
        for i in range(0, len(text), chunk_size - chunk_overlap):
            chunk = text[i:i + chunk_size]
            if chunk.strip():
                chunks.append(chunk.strip())
    
    return chunks

def generate_embedding(text: str) -> list[float]:
    if not api_key:
        return [0.1] * 768
    try:
        result = genai.embed_content(
            model="models/embedding-001",
            content=text,
            task_type="retrieval_document",
            title="College Document"
        )
        return result['embedding']
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return [0.0] * 768

async def process_document(document_id: str, file_path: str):
    client = get_service_client() 
    
    try:
        # 0. Get document details and verify it's approved
        doc_res = client.table("documents").select("college_id, status, filename, uploaded_by").eq("id", document_id).execute()
        if not doc_res.data:
            raise Exception(f"Document {document_id} not found in database")
        
        document = doc_res.data[0]
        college_id = document["college_id"]
        filename = document["filename"]
        uploaded_by = document["uploaded_by"]
        
        # Only process approved documents
        if document["status"] != "approved":
            raise Exception(f"Document {document_id} is not approved for processing. Current status: {document['status']}")

        # Update status to 'processing' before starting
        client.table("documents").update({"status": "processing"}).eq("id", document_id).execute()

        # 1. Download file
        file_content = client.storage.from_("documents").download(file_path)
        
        # 2. Extract Text
        text = extract_text_from_pdf(file_content)
        
        if not text:
             print("Warning: No text extracted from PDF")
             raise Exception("No text could be extracted from the PDF")

        # 3. Split text into multiple chunks
        # Chunk size 1500 chars is good for structured data like course catalogs
        # Overlap of 300 chars ensures context is maintained between chunks
        text_chunks = chunk_text(text, chunk_size=1500, chunk_overlap=300)
        
        if not text_chunks:
            raise Exception("Failed to create text chunks from document")
        
        print(f"Created {len(text_chunks)} chunks from document")
        
        # 4. Generate embeddings and store each chunk
        chunks_to_insert = []
        chunk_counter = 0  # Separate counter for sequential chunk ordering
        for chunk_content in text_chunks:
            if not chunk_content.strip():
                continue  # Skip empty chunks, but don't increment counter
            
            embedding = generate_embedding(chunk_content)
            
            chunk_data = {
                "document_id": document_id,
                "college_id": college_id,
                "content": chunk_content,
                "embedding": embedding,
                "metadata": {"chunk_index": chunk_counter}  # Sequential index of actually stored chunks
            }
            chunks_to_insert.append(chunk_data)
            chunk_counter += 1  # Only increment when chunk is actually stored
        
        # Insert all chunks at once (more efficient)
        if chunks_to_insert:
            client.table("document_chunks").insert(chunks_to_insert).execute()
            print(f"Stored {len(chunks_to_insert)} chunks in database")
        
        # 5. Update Status to completed with processed timestamp
        from datetime import datetime
        client.table("documents").update({
            "status": "completed",
            "processed_at": datetime.utcnow().isoformat()
        }).eq("id", document_id).execute()
        
        # 6. Create notification for successful processing
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
                        "processed_at": datetime.utcnow().isoformat()
                    }
                )
        except Exception as e:
            # Log notification error but don't fail the processing
            print(f"Warning: Failed to create processing completion notification: {str(e)}")

    except Exception as e:
        print(f"Error processing document {document_id}: {e}")
        
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
        
        # Update document status to failed
        client.table("documents").update({
            "status": "failed", 
            "error_message": str(e)
        }).eq("id", document_id).execute()
        
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
                        "error_message": str(e)
                    }
                )
        except Exception as notification_error:
            # Log notification error but don't fail the processing
            print(f"Warning: Failed to create processing failure notification: {str(notification_error)}")

async def trigger_rag_processing(document_id: str):
    """
    Trigger RAG processing for an approved document.
    This function should be called after a document is approved.
    """
    client = get_service_client()
    
    try:
        # Get document details
        doc_res = client.table("documents").select("storage_path, status").eq("id", document_id).execute()
        if not doc_res.data:
            raise Exception(f"Document {document_id} not found")
        
        document = doc_res.data[0]
        
        # Verify document is approved
        if document["status"] != "approved":
            raise Exception(f"Document {document_id} is not approved for processing")
        
        # Start processing
        await process_document(document_id, document["storage_path"])
        
    except Exception as e:
        print(f"Error triggering RAG processing for document {document_id}: {e}")
        # Update document status to failed
        client.table("documents").update({
            "status": "failed",
            "error_message": f"Failed to trigger processing: {str(e)}"
        }).eq("id", document_id).execute()

async def retrieve_relevant_chunks(
    query: str, 
    college_id: str, 
    top_k: int = 5,
    similarity_threshold: float = 0.7
) -> List[dict]:
    """
    Retrieve relevant document chunks for a query using vector similarity search.
    
    Args:
        query: User's question
        college_id: Filter chunks by college
        top_k: Number of chunks to retrieve (default 5)
        similarity_threshold: Minimum similarity score (0.0-1.0, higher = more strict)
    
    Returns:
        List of relevant chunks with metadata
    """
    if not api_key:
        return []
    
    try:
        client = get_service_client()
        
        # 1. Generate embedding for the query
        query_embedding = generate_embedding(query)
        
        if not query_embedding:
            return []
        
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
        
        if not all_chunks_response.data:
            return []
        
        # Get document info
        document_ids = list(set([chunk["document_id"] for chunk in all_chunks_response.data]))
        docs_response = client.table("documents").select("id, filename, status").in_("id", document_ids).eq("status", "completed").execute()
        doc_map = {doc["id"]: doc["filename"] for doc in docs_response.data}
        
        # Calculate cosine similarity for each chunk
        def cosine_similarity(vec1: list, vec2: list) -> float:
            """Calculate cosine similarity between two vectors"""
            vec1_arr = np.array(vec1)
            vec2_arr = np.array(vec2)
            dot_product = np.dot(vec1_arr, vec2_arr)
            norm1 = np.linalg.norm(vec1_arr)
            norm2 = np.linalg.norm(vec2_arr)
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return dot_product / (norm1 * norm2)
        
        # Score and sort chunks
        scored_chunks = []
        for chunk in all_chunks_response.data:
            if chunk["document_id"] not in doc_map:
                continue
            
            # Skip chunks without embeddings
            if not chunk.get("embedding"):
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
        
        # Sort by similarity (highest first) and take top_k
        scored_chunks.sort(key=lambda x: x["similarity"], reverse=True)
        return scored_chunks[:top_k]
        
    except Exception as e:
        print(f"Error retrieving chunks: {e}")
        import traceback
        traceback.print_exc()
        return []

async def generate_rag_response(
    query: str,
    college_id: str,
    context_chunks: List[dict] = None
) -> dict:
    """
    Generate a response using RAG (Retrieval-Augmented Generation).
    
    Args:
        query: User's question
        college_id: College ID for filtering documents
        context_chunks: Pre-retrieved chunks (if None, will retrieve automatically)
    
    Returns:
        Dictionary with response text and sources
    """
    if not api_key:
        return {
            "response": "AI service is not configured. Please contact administrator.",
            "sources": []
        }
    
    try:
        # Retrieve relevant chunks if not provided
        if context_chunks is None:
            context_chunks = await retrieve_relevant_chunks(query, college_id, top_k=5, similarity_threshold=0.6)
        
        if not context_chunks:
            return {
                "response": "I couldn't find relevant information in the available documents to answer your question. Please try rephrasing or contact your college administration for more details.",
                "sources": []
            }
        
        # Build context from chunks
        context_text = "\n\n---\n\n".join([
            f"[From: {chunk['filename']}]\n{chunk['content']}" 
            for chunk in context_chunks
        ])
        
        # Get unique source documents
        sources = list(set([chunk['filename'] for chunk in context_chunks]))
        
        # Enhanced prompt for better formatting and structured responses
        prompt = f"""You are a helpful college information assistant. Answer the user's question based ONLY on the provided context from college documents.

**Instructions:**
1. Use ONLY information from the provided context. Do not use external knowledge.
2. Format your answer clearly with proper structure:
   - Use bullet points or numbered lists when listing items
   - Use bold text for important terms (use **term**)
   - Maintain proper formatting for course codes, credits, subjects
   - If listing courses/subjects, present them in a clear table-like format
3. If the context contains structured data (like course lists), preserve that structure in your answer.
4. Be concise but comprehensive.
5. If information is missing, clearly state what is not available.

**Context from documents:**
{context_text}

**User Question:**
{query}

**Your Answer:**"""
        
        # Generate response using Gemini
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        
        response_text = response.text if response.text else "I apologize, but I couldn't generate a response. Please try again."
        
        return {
            "response": response_text,
            "sources": sources,
            "chunks_used": len(context_chunks)
        }
        
    except Exception as e:
        print(f"Error generating RAG response: {e}")
        import traceback
        traceback.print_exc()
        return {
            "response": f"I encountered an error while processing your question: {str(e)}",
            "sources": []
        }
