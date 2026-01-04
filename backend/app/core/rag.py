from app.core.database import get_service_client
import google.generativeai as genai
import os
from io import BytesIO
from pypdf import PdfReader
from uuid import UUID

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

        # 3. Generate Embedding
        chunk_text = text[:2000] if text else "Empty document"
        embedding = generate_embedding(chunk_text)
        
        # 4. Store Chunk
        chunk_data = {
            "document_id": document_id,
            "college_id": college_id,
            "content": chunk_text,
            "embedding": embedding
        }
        client.table("document_chunks").insert(chunk_data).execute()
        
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
