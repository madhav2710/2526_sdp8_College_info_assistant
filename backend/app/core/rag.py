from app.core.database import get_service_client
import google.generativeai as genai
import os
from io import BytesIO
from pypdf import PdfReader

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
            "content": chunk_text,
            "embedding": embedding
        }
        client.table("document_chunks").insert(chunk_data).execute()
        
        # 5. Update Status
        client.table("documents").update({"status": "completed"}).eq("id", document_id).execute()

    except Exception as e:
        print(f"Error processing document {document_id}: {e}")
        client.table("documents").update({"status": "failed", "error_message": str(e)}).eq("id", document_id).execute()
