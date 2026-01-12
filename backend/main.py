from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from uuid import UUID, uuid4
from datetime import datetime
import datetime as dt
from typing import Optional
from app.core.database import supabase, get_service_client
from app.core.auth import get_current_user
from app.core.notifications import notification_manager
from app.models.notification import NotificationFilters, NotificationType
from app.core.workflow import validate_status_transition, log_status_change
from app.core.basic_chat import generate_basic_response
import os
import hashlib
import mimetypes

app = FastAPI()

# Allow the frontend (Vite dev server) to call this API from the browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ChatMessage(BaseModel):
    conversation_id: UUID 
    user_id: UUID 
    role: str
    content: str
    created_at: Optional[datetime] = None

class ChatRequest(BaseModel):
    user_id: UUID
    title: str

# File validation constants
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt'}
ALLOWED_MIME_TYPES = {
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain'
}

def validate_file(file: UploadFile, file_content: bytes) -> tuple[bool, Optional[str]]:
    """
    Validate uploaded file.
    
    Returns:
        (is_valid, error_message)
    """
    # Check file size
    if len(file_content) > MAX_FILE_SIZE:
        return False, f"File exceeds {MAX_FILE_SIZE / (1024*1024):.0f}MB limit"
    
    if len(file_content) == 0:
        return False, "File is empty"
    
    # Check file extension
    file_ext = None
    if file.filename:
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            return False, f"Only {', '.join(ALLOWED_EXTENSIONS)} files are allowed"
    
    # Check MIME type
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        return False, f"Invalid file type. Allowed types: {', '.join(ALLOWED_MIME_TYPES)}"
    
    # Verify MIME type matches extension
    if file_ext and file.content_type:
        expected_mime = mimetypes.guess_type(file.filename)[0]
        if expected_mime and expected_mime != file.content_type:
            return False, "File type mismatch. Please ensure the file extension matches the file content."
    
    # Try to read file to check for corruption (basic check)
    try:
        if file_ext == '.pdf':
            from io import BytesIO
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(file_content))
            if len(reader.pages) == 0:
                return False, "PDF file appears to be corrupted or empty"
    except Exception as e:
        return False, f"File validation failed: {str(e)}"
    
    return True, None

def calculate_file_hash(file_content: bytes) -> str:
    """Calculate SHA256 hash of file content for duplicate detection."""
    return hashlib.sha256(file_content).hexdigest()

class DocumentApprovalRequest(BaseModel):
    document_id: UUID
    comments: Optional[str] = None
    process_schedule: Optional[str] = 'immediate'  # 'immediate', 'scheduled', 'manual'
    scheduled_at: Optional[datetime] = None

class DocumentRejectionRequest(BaseModel):
    document_id: UUID
    reason: str

class ScheduleProcessingRequest(BaseModel):
    document_id: UUID
    scheduled_at: datetime

# Auth Endpoints
@app.post("/auth/login")
async def login(request: LoginRequest):
    try:
        # Authenticate with Supabase
        auth_response = supabase.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password
        })
        
        # Fetch user profile for role and college_id
        user_id = auth_response.user.id
        profile_response = supabase.table("profiles").select("role, college_id").eq("id", user_id).execute()
        
        if not profile_response.data:
            raise HTTPException(status_code=404, detail="User profile not found")
            
        profile = profile_response.data[0]
        
        return {
            "access_token": auth_response.session.access_token,
            "token_type": "bearer",
            "user_id": user_id,
            "role": profile["role"],
            "college_id": profile["college_id"]
        }
    except Exception as e:
        if "Invalid login credentials" in str(e):
            raise HTTPException(status_code=401, detail="Invalid login credentials")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/chat/")
async def create_chat(message: ChatMessage):
    try:
        client = get_service_client()

        # 1. Get user's college_id
        profile = client.table("profiles").select("college_id").eq("id", str(message.user_id)).execute()
        if not profile.data:
            raise HTTPException(status_code=404, detail="User profile not found")
        
        college_id = profile.data[0]["college_id"]
        if not college_id:
            raise HTTPException(status_code=400, detail="User is not associated with a college")

        # 2. Ensure conversation exists
        conv_check = client.table("conversations").select("id").eq("id", str(message.conversation_id)).execute()
        
        if not conv_check.data:
            client.table("conversations").insert({
                "id": str(message.conversation_id),
                "user_id": str(message.user_id),
                "college_id": college_id,
                "title": message.content[:50] + "..."
            }).execute()

        # 3. Insert the user message into the 'messages' table
        user_message_data = {
            "conversation_id": str(message.conversation_id),
            "role": "user",
            "content": message.content
        }
        user_message_response = client.table("messages").insert(user_message_data).execute()

        # 4. Generate response (using basic chat for prototype, RAG can be enabled later)
        # Try RAG first, fallback to basic chat if RAG is not available
        try:
            from app.core.rag import generate_rag_response
            rag_result = await generate_rag_response(
                query=message.content,
                college_id=college_id
            )
        except Exception as e:
            # Fallback to basic chat if RAG fails
            print(f"RAG not available, using basic chat: {str(e)}")
            rag_result = await generate_basic_response(
                query=message.content,
                college_id=college_id
            )
        
        # 5. Store the assistant's response
        assistant_message_data = {
            "conversation_id": str(message.conversation_id),
            "role": "assistant",
            "content": rag_result["response"],
            "sources": rag_result.get("sources", [])  # Store sources as JSONB
        }
        assistant_message_response = client.table("messages").insert(assistant_message_data).execute()

        # 6. Return response with sources
        return {
            "status": "Message sent",
            "role": "assistant",
            "content": rag_result["response"],
            "sources": rag_result.get("sources", []),
            "conversation_id": str(message.conversation_id),
            "chunks_used": rag_result.get("chunks_used", 0)
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing chat message: {str(e)}")

@app.get("/chat/history/")
async def get_chat_history(user_id: UUID):
    try:
        conv_response = supabase.table("conversations").select("*").eq("user_id", str(user_id)).order("created_at", desc=True).execute()
        return conv_response.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/admin/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    college_id: str = Form(None),
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "college_admin":
        raise HTTPException(status_code=403, detail="Not authorized to upload documents")

    target_college_id = current_user["college_id"]
    if not target_college_id:
         raise HTTPException(status_code=400, detail="User is not associated with a college")

    file_id = None
    try:
        # Use service client to bypass RLS for storage and DB
        client = get_service_client()
        
        # Read and validate file
        file_content = await file.read()
        file_size = len(file_content)
        
        # Validate file
        is_valid, error_msg = validate_file(file, file_content)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Check for duplicate files (same hash + college_id)
        # Only consider documents in active/valid states as duplicates
        # Exclude rejected and failed documents to allow re-upload after deletion
        file_hash = calculate_file_hash(file_content)
        existing_docs = client.table("documents").select("id, storage_path, status").eq("college_id", target_college_id).eq("file_hash", file_hash).in_("status", ["pending_approval", "approved", "processing", "completed"]).execute()
        
        # Verify that the existing document's file still exists in storage
        if existing_docs.data:
            import httpx
            from app.core.database import url as supabase_url, service_key
            
            # Check if any of the existing documents still have files in storage
            for doc in existing_docs.data:
                storage_path = doc.get("storage_path")
                if storage_path:
                    check_url = f"{supabase_url}/storage/v1/object/documents/{storage_path}"
                    check_headers = {"Authorization": f"Bearer {service_key}"}
                    try:
                        async with httpx.AsyncClient() as http_client:
                            check_response = await http_client.head(check_url, headers=check_headers, timeout=10.0)
                            # If file exists in storage, it's a real duplicate
                            if check_response.status_code == 200:
                                raise HTTPException(status_code=400, detail="A file with identical content already exists. Please upload a different file.")
                    except Exception:
                        # If we can't check (network error, etc.), assume file doesn't exist and allow upload
                        continue
            # If we get here, all existing documents with this hash have been deleted from storage
            # So we can proceed with the upload
        
        # Sanitize filename
        original_filename = file.filename or "document"
        # Remove special characters but keep extension
        safe_filename = "".join(c for c in original_filename if c.isalnum() or c in "._- ")
        filename = f"{uuid4()}_{safe_filename}"
        path = f"{target_college_id}/{filename}"

        # Upload to Supabase Storage using direct HTTP to ensure Service Key is used
        import httpx
        from app.core.database import url as SUPABASE_URL, service_key
        
        storage_url = f"{SUPABASE_URL}/storage/v1/object/documents/{path}"
        headers = {
            "Authorization": f"Bearer {service_key}",
            "Content-Type": file.content_type,
            "x-upsert": "true" 
        }
        
        async with httpx.AsyncClient() as http_client:
            r = await http_client.post(storage_url, content=file_content, headers=headers, timeout=60.0)
            if r.status_code not in [200, 201]:
                 raise HTTPException(status_code=400, detail=f"File upload failed: {r.text}")
            file_id = path  # Store path for cleanup if needed

        # Map content_type to expected DB enum/check if needed
        mime_to_type = {
            "application/pdf": "pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
            "text/plain": "txt"
        }
        file_type_val = mime_to_type.get(file.content_type, "other")

        # Insert metadata to DB with enhanced tracking
        doc_data = {
            "college_id": target_college_id,
            "filename": original_filename,
            "storage_path": path,
            "file_type": file_type_val,
            "file_size": file_size,
            "uploaded_by": current_user["user_id"],
            "status": "pending_approval",  # Changed to require approval before processing
            "file_hash": file_hash,
            "validated_at": datetime.now(dt.UTC).isoformat(),
            "process_schedule": "manual"  # Default to manual processing
        }

        # Use direct HTTP for DB Insert to ensure Service Key is used
        db_url = f"{SUPABASE_URL}/rest/v1/documents"
        db_headers = {
            "Authorization": f"Bearer {service_key}",
            "ApiKey": service_key,
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        async with httpx.AsyncClient() as http_client:
             r_db = await http_client.post(db_url, json=doc_data, headers=db_headers, timeout=10.0)
             if r_db.status_code not in [200, 201]:
                 raise HTTPException(status_code=500, detail=f"Database error: {r_db.text}")
             
             db_data = r_db.json()
        
        document_record = db_data[0] if db_data else None
        
        if not document_record:
            # Rollback: Delete file if uploaded but DB insert failed
            if file_id:
                try:
                    delete_url = f"{SUPABASE_URL}/storage/v1/object/documents/{file_id}"
                    async with httpx.AsyncClient() as http_client:
                        await http_client.delete(delete_url, headers=headers, timeout=10.0)
                except Exception as cleanup_error:
                    print(f"Warning: Failed to cleanup orphaned file: {cleanup_error}")
            raise HTTPException(status_code=500, detail="Failed to create document record")
        
        # Log status change
        try:
            log_status_change(
                client=client,
                document_id=document_record["id"],
                old_status="uploaded",
                new_status="pending_approval",
                changed_by=current_user["user_id"],
                comments="Document uploaded"
            )
        except Exception as log_error:
            print(f"Warning: Failed to log status change: {log_error}")

        # Create notification for super admins about new document upload
        try:
            # Get all super admin user IDs
            client = get_service_client()
            super_admin_query = client.table("profiles").select("id").eq("role", "super_admin")
            super_admin_response = super_admin_query.execute()
            
            super_admin_ids = [UUID(admin["id"]) for admin in super_admin_response.data]
            
            if super_admin_ids:
                await notification_manager.create_document_notification(
                    recipient_ids=super_admin_ids,
                    notification_type=NotificationType.DOCUMENT_UPLOADED,
                    document_id=UUID(document_record["id"]),
                    document_filename=document_record["filename"],
                    additional_metadata={
                        "college_id": target_college_id,
                        "uploaded_by": current_user["user_id"]
                    }
                )
        except Exception as e:
            # Log notification error but don't fail the upload
            print(f"Warning: Failed to create upload notification: {str(e)}")

        # Return detailed acknowledgment with document metadata
        return {
            "status": "success",
            "message": "Document uploaded successfully. Awaiting super admin approval.",
            "document": {
                "id": document_record["id"],
                "filename": document_record["filename"],
                "file_type": document_record["file_type"],
                "file_size": document_record["file_size"],
                "status": document_record["status"],
                "uploaded_at": document_record["created_at"]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        # Rollback: Delete file if uploaded but operation failed
        if file_id:
            try:
                import httpx
                from app.core.database import url as SUPABASE_URL, service_key
                delete_url = f"{SUPABASE_URL}/storage/v1/object/documents/{file_id}"
                headers = {"Authorization": f"Bearer {service_key}"}
                async with httpx.AsyncClient() as http_client:
                    await http_client.delete(delete_url, headers=headers, timeout=10.0)
            except Exception as cleanup_error:
                print(f"Warning: Failed to cleanup orphaned file: {cleanup_error}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.get("/admin/query-history")
async def get_query_history(
    limit: Optional[int] = 10,
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "college_admin":
        raise HTTPException(status_code=403, detail="Not authorized to view query history")
    
    target_college_id = current_user["college_id"]
    if not target_college_id:
         raise HTTPException(status_code=400, detail="User is not associated with a college")

    try:
        client = get_service_client()
        
        # Get conversations for this college with recent messages
        query = (client.table("conversations")
                .select("id, title, created_at, messages(content, role, created_at)")
                .eq("college_id", target_college_id)
                .order("created_at", desc=True)
                .limit(limit))
        
        response = query.execute()
        
        # Format the query history
        query_history = []
        for conv in response.data:
            if conv.get("messages"):
                # Get the first user message as the query
                user_messages = [msg for msg in conv["messages"] if msg["role"] == "user"]
                if user_messages:
                    first_message = user_messages[0]
                    query_history.append({
                        "id": conv["id"],
                        "query": first_message["content"][:100] + "..." if len(first_message["content"]) > 100 else first_message["content"],
                        "title": conv["title"],
                        "created_at": conv["created_at"],
                        "message_count": len(conv["messages"])
                    })
        
        return {
            "query_history": query_history,
            "total_conversations": len(response.data)
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to retrieve query history: {str(e)}")

@app.get("/admin/documents")
async def get_documents(
    status: Optional[str] = None,
    sort_by: Optional[str] = "created_at",
    sort_order: Optional[str] = "desc",
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "college_admin":
        raise HTTPException(status_code=403, detail="Not authorized to view documents")
    
    target_college_id = current_user["college_id"]
    if not target_college_id:
         raise HTTPException(status_code=400, detail="User is not associated with a college")

    try:
        client = get_service_client()
        
        # Build query with filtering and sorting
        query = client.table("documents").select("*").eq("college_id", target_college_id)
        
        # Apply status filter if provided
        if status and status in ['uploaded', 'pending_approval', 'approved', 'rejected', 'processing', 'completed', 'failed']:
            query = query.eq("status", status)
        
        # Apply sorting
        valid_sort_fields = ['created_at', 'updated_at', 'filename', 'status', 'file_size']
        if sort_by in valid_sort_fields:
            desc = sort_order.lower() == 'desc'
            query = query.order(sort_by, desc=desc)
        else:
            query = query.order("created_at", desc=True)
        
        # Execute document query
        documents_response = query.execute()
        documents = documents_response.data
        
        # Calculate real-time statistics from database
        stats_query = client.table("documents").select("status").eq("college_id", target_college_id)
        stats_response = stats_query.execute()
        
        # Calculate statistics
        statistics = {
            "total": 0,
            "uploaded": 0,
            "pending_approval": 0,
            "approved": 0,
            "rejected": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0
        }
        
        for doc in stats_response.data:
            doc_status = doc.get("status", "unknown")
            statistics["total"] += 1
            if doc_status in statistics:
                statistics[doc_status] += 1
        
        # Get college information for dynamic data
        college_query = client.table("colleges").select("name").eq("id", target_college_id)
        college_response = college_query.execute()
        college_name = college_response.data[0]["name"] if college_response.data else "Unknown College"
        
        # Get user profile information
        profile_query = client.table("profiles").select("*").eq("id", current_user["user_id"])
        profile_response = profile_query.execute()
        user_profile = profile_response.data[0] if profile_response.data else {}
        
        return {
            "documents": documents,
            "statistics": statistics,
            "college_info": {
                "id": target_college_id,
                "name": college_name
            },
            "user_profile": {
                "id": user_profile.get("id"),
                "email": user_profile.get("email"),
                "role": user_profile.get("role"),
                "college_id": user_profile.get("college_id")
            },
            "filters": {
                "status": status,
                "sort_by": sort_by,
                "sort_order": sort_order
            }
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to retrieve documents: {str(e)}")

# Super Admin Endpoints
@app.get("/super-admin/pending-documents")
async def get_pending_documents(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Not authorized to view pending documents")
    
    try:
        client = get_service_client()
        
        # Get all documents with 'uploaded' or 'pending_approval' status
        query = (client.table("documents")
                .select("id, filename, file_type, file_size, college_id, uploaded_by, created_at")
                .in_("status", ["uploaded", "pending_approval"])
                .order("created_at", desc=False))  # Oldest first for FIFO processing
        
        response = query.execute()
        
        # Get college and user info separately to avoid join issues
        pending_documents = []
        for doc in response.data:
            # Get college name
            college_query = client.table("colleges").select("name").eq("id", doc["college_id"])
            college_response = college_query.execute()
            college_name = college_response.data[0]["name"] if college_response.data else "Unknown College"
            
            # Get uploader display name (profiles table has full_name, not email)
            uploader_name = "Unknown User"
            if doc.get("uploaded_by"):
                uploader_query = client.table("profiles").select("full_name").eq("id", doc["uploaded_by"])
                uploader_response = uploader_query.execute()
                if uploader_response.data:
                    uploader_name = uploader_response.data[0].get("full_name") or uploader_name
            
            pending_documents.append({
                "id": doc["id"],
                "filename": doc["filename"],
                "file_type": doc["file_type"],
                "file_size": doc["file_size"],
                "college_id": doc["college_id"],
                "college_name": college_name,
                "uploaded_by": doc["uploaded_by"],
                # Frontend expects this key; we return uploader name for display
                "uploader_email": uploader_name,
                "uploaded_at": doc["created_at"]
            })
        
        return {
            "pending_documents": pending_documents,
            "total_pending": len(pending_documents)
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to retrieve pending documents: {str(e)}")

@app.post("/super-admin/approve-document")
async def approve_document(
    request: DocumentApprovalRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Not authorized to approve documents")
    
    try:
        client = get_service_client()
        
        # First, verify the document exists and is in the correct status
        doc_query = client.table("documents").select("*").eq("id", str(request.document_id)).execute()
        
        if not doc_query.data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        document = doc_query.data[0]
        current_status = document["status"]
        
        # Validate status transition
        if not validate_status_transition(current_status, "approved"):
            raise HTTPException(status_code=400, detail=f"Invalid status transition from {current_status} to approved")
        
        # Validate process_schedule
        if request.process_schedule not in ['immediate', 'scheduled', 'manual']:
            raise HTTPException(status_code=400, detail="Invalid process_schedule. Must be 'immediate', 'scheduled', or 'manual'")
        
        # Validate scheduled_at if process_schedule is 'scheduled'
        if request.process_schedule == 'scheduled':
            if not request.scheduled_at:
                raise HTTPException(status_code=400, detail="scheduled_at is required when process_schedule is 'scheduled'")
            if request.scheduled_at <= datetime.now(dt.UTC):
                raise HTTPException(status_code=400, detail="scheduled_at must be in the future")
        
        # Update document status to 'approved' and add approval metadata
        update_data = {
            "status": "approved",
            "approved_by": current_user["user_id"],
            "approval_comments": request.comments,
            "updated_at": datetime.now(dt.UTC).isoformat(),
            "process_schedule": request.process_schedule,
            "scheduled_at": request.scheduled_at.isoformat() if request.scheduled_at else None
        }
        
        # If immediate processing, trigger it
        if request.process_schedule == 'immediate':
            update_data["status"] = "processing"  # Move directly to processing
        
        # Use direct HTTP for DB update to ensure Service Key is used
        from app.core.database import url as SUPABASE_URL, service_key
        import httpx
        
        db_url = f"{SUPABASE_URL}/rest/v1/documents?id=eq.{request.document_id}"
        db_headers = {
            "Authorization": f"Bearer {service_key}",
            "ApiKey": service_key,
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        async with httpx.AsyncClient() as http_client:
            r_db = await http_client.patch(db_url, json=update_data, headers=db_headers, timeout=10.0)
            if r_db.status_code not in [200, 201]:
                raise HTTPException(status_code=500, detail=f"Database update error: {r_db.text}")
            
            updated_doc = r_db.json()
        
        # Record the approval in document_approvals table
        approval_data = {
            "document_id": str(request.document_id),
            "approved_by": current_user["user_id"],
            "action": "approved",
            "comments": request.comments
        }
        
        approval_url = f"{SUPABASE_URL}/rest/v1/document_approvals"
        async with httpx.AsyncClient() as http_client:
            r_approval = await http_client.post(approval_url, json=approval_data, headers=db_headers, timeout=10.0)
            if r_approval.status_code not in [200, 201]:
                # Log but don't fail the approval if approval record creation fails
                print(f"Warning: Failed to create approval record: {r_approval.text}")
        
        # Log status change
        try:
            log_status_change(
                client=client,
                document_id=str(request.document_id),
                old_status=current_status,
                new_status=update_data["status"],
                changed_by=current_user["user_id"],
                comments=request.comments
            )
        except Exception as log_error:
            print(f"Warning: Failed to log status change: {log_error}")
        
        # Trigger RAG processing only if immediate
        if request.process_schedule == 'immediate':
            from app.core.rag import trigger_rag_processing
            background_tasks.add_task(trigger_rag_processing, str(request.document_id))
        
        # Create notification for college admin about document approval
        try:
            if document["uploaded_by"]:
                await notification_manager.create_document_notification(
                    recipient_ids=[UUID(document["uploaded_by"])],
                    notification_type=NotificationType.DOCUMENT_APPROVED,
                    document_id=request.document_id,
                    document_filename=document["filename"],
                    additional_metadata={
                        "approved_by": current_user["user_id"],
                        "approval_comments": request.comments
                    }
                )
        except Exception as e:
            # Log notification error but don't fail the approval
            print(f"Warning: Failed to create approval notification: {str(e)}")
        
        return {
            "status": "success",
            "message": f"Document '{document['filename']}' has been approved. Processing: {request.process_schedule}",
            "document": {
                "id": str(request.document_id),
                "filename": document["filename"],
                "status": update_data["status"],
                "process_schedule": request.process_schedule,
                "scheduled_at": request.scheduled_at.isoformat() if request.scheduled_at else None,
                "approved_by": current_user["user_id"],
                "approval_comments": request.comments,
                "approved_at": update_data["updated_at"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Approval failed: {str(e)}")

class DocumentRejectionRequest(BaseModel):
    document_id: UUID
    reason: str

@app.post("/super-admin/reject-document")
async def reject_document(
    request: DocumentRejectionRequest,
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Not authorized to reject documents")
    
    try:
        client = get_service_client()
        
        # First, verify the document exists and is in the correct status
        doc_query = client.table("documents").select("*").eq("id", str(request.document_id)).execute()
        
        if not doc_query.data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        document = doc_query.data[0]
        current_status = document["status"]
        
        # Validate status transition
        if not validate_status_transition(current_status, "rejected"):
            raise HTTPException(status_code=400, detail=f"Invalid status transition from {current_status} to rejected")
        
        # Update document status to 'rejected' and add rejection metadata
        update_data = {
            "status": "rejected",
            "approved_by": current_user["user_id"],  # Using same field for consistency
            "approval_comments": request.reason,
            "updated_at": datetime.now(dt.UTC).isoformat()
        }
        
        # Log status change
        try:
            log_status_change(
                client=client,
                document_id=str(request.document_id),
                old_status=current_status,
                new_status="rejected",
                changed_by=current_user["user_id"],
                comments=request.reason
            )
        except Exception as log_error:
            print(f"Warning: Failed to log status change: {log_error}")
        
        # Use direct HTTP for DB update to ensure Service Key is used
        from app.core.database import url as SUPABASE_URL, service_key
        import httpx
        
        db_url = f"{SUPABASE_URL}/rest/v1/documents?id=eq.{request.document_id}"
        db_headers = {
            "Authorization": f"Bearer {service_key}",
            "ApiKey": service_key,
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        async with httpx.AsyncClient() as http_client:
            r_db = await http_client.patch(db_url, json=update_data, headers=db_headers, timeout=10.0)
            if r_db.status_code not in [200, 201]:
                raise HTTPException(status_code=500, detail=f"Database update error: {r_db.text}")
            
            updated_doc = r_db.json()
        
        # Record the rejection in document_approvals table
        approval_data = {
            "document_id": str(request.document_id),
            "approved_by": current_user["user_id"],
            "action": "rejected",
            "comments": request.reason
        }
        
        approval_url = f"{SUPABASE_URL}/rest/v1/document_approvals"
        async with httpx.AsyncClient() as http_client:
            r_approval = await http_client.post(approval_url, json=approval_data, headers=db_headers, timeout=10.0)
            if r_approval.status_code not in [200, 201]:
                # Log but don't fail the rejection if approval record creation fails
                print(f"Warning: Failed to create rejection record: {r_approval.text}")
        
        # Create notification for college admin about document rejection
        try:
            if document["uploaded_by"]:
                await notification_manager.create_document_notification(
                    recipient_ids=[UUID(document["uploaded_by"])],
                    notification_type=NotificationType.DOCUMENT_REJECTED,
                    document_id=request.document_id,
                    document_filename=document["filename"],
                    additional_metadata={
                        "rejected_by": current_user["user_id"],
                        "rejection_reason": request.reason
                    }
                )
        except Exception as e:
            # Log notification error but don't fail the rejection
            print(f"Warning: Failed to create rejection notification: {str(e)}")
        
        return {
            "status": "success",
            "message": f"Document '{document['filename']}' has been rejected",
            "document": {
                "id": str(request.document_id),
                "filename": document["filename"],
                "status": "rejected",
                "rejected_by": current_user["user_id"],
                "rejection_reason": request.reason,
                "rejected_at": update_data["updated_at"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Rejection failed: {str(e)}")

@app.post("/super-admin/schedule-document-processing")
async def schedule_document_processing(
    request: ScheduleProcessingRequest,
    current_user: dict = Depends(get_current_user)
):
    """Schedule document processing for a future time."""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Not authorized to schedule processing")
    
    try:
        client = get_service_client()
        
        # Verify document exists and is approved
        doc_query = client.table("documents").select("*").eq("id", str(request.document_id)).execute()
        if not doc_query.data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        document = doc_query.data[0]
        if document["status"] != "approved":
            raise HTTPException(status_code=400, detail=f"Document must be approved to schedule processing. Current status: {document['status']}")
        
        # Validate scheduled_at is in the future
        if request.scheduled_at <= datetime.now(dt.UTC):
            raise HTTPException(status_code=400, detail="scheduled_at must be in the future")
        
        # Update document with scheduled processing
        update_data = {
            "process_schedule": "scheduled",
            "scheduled_at": request.scheduled_at.isoformat(),
            "updated_at": datetime.now(dt.UTC).isoformat()
        }
        
        from app.core.database import url as SUPABASE_URL, service_key
        import httpx
        
        db_url = f"{SUPABASE_URL}/rest/v1/documents?id=eq.{request.document_id}"
        db_headers = {
            "Authorization": f"Bearer {service_key}",
            "ApiKey": service_key,
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        async with httpx.AsyncClient() as http_client:
            r_db = await http_client.patch(db_url, json=update_data, headers=db_headers, timeout=10.0)
            if r_db.status_code not in [200, 201]:
                raise HTTPException(status_code=500, detail=f"Database update error: {r_db.text}")
            
            updated_doc = r_db.json()
        
        return {
            "status": "success",
            "message": f"Document '{document['filename']}' scheduled for processing",
            "document": {
                "id": str(request.document_id),
                "filename": document["filename"],
                "process_schedule": "scheduled",
                "scheduled_at": request.scheduled_at.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Scheduling failed: {str(e)}")

class TriggerProcessingRequest(BaseModel):
    document_id: UUID

@app.post("/super-admin/trigger-processing")
async def trigger_processing(
    request: TriggerProcessingRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Manually trigger processing for an approved document."""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Not authorized to trigger processing")
    
    try:
        client = get_service_client()
        
        # Verify document exists and is approved
        doc_query = client.table("documents").select("*").eq("id", str(request.document_id)).execute()
        if not doc_query.data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        document = doc_query.data[0]
        current_status = document["status"]
        
        # Validate status transition
        if current_status != "approved":
            raise HTTPException(status_code=400, detail=f"Document must be approved to trigger processing. Current status: {current_status}")
        
        # Update status to processing
        update_data = {
            "status": "processing",
            "process_schedule": "manual",
            "updated_at": datetime.now(dt.UTC).isoformat()
        }
        
        from app.core.database import url as SUPABASE_URL, service_key
        import httpx
        
        db_url = f"{SUPABASE_URL}/rest/v1/documents?id=eq.{request.document_id}"
        db_headers = {
            "Authorization": f"Bearer {service_key}",
            "ApiKey": service_key,
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        async with httpx.AsyncClient() as http_client:
            r_db = await http_client.patch(db_url, json=update_data, headers=db_headers, timeout=10.0)
            if r_db.status_code not in [200, 201]:
                raise HTTPException(status_code=500, detail=f"Database update error: {r_db.text}")
        
        # Log status change
        try:
            log_status_change(
                client=client,
                document_id=str(request.document_id),
                old_status=current_status,
                new_status="processing",
                changed_by=current_user["user_id"],
                comments="Manual processing trigger"
            )
        except Exception as log_error:
            print(f"Warning: Failed to log status change: {log_error}")
        
        # Trigger RAG processing
        from app.core.rag import trigger_rag_processing
        background_tasks.add_task(trigger_rag_processing, str(request.document_id))
        
        return {
            "status": "success",
            "message": f"Processing triggered for document '{document['filename']}'",
            "document": {
                "id": str(request.document_id),
                "filename": document["filename"],
                "status": "processing"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Trigger processing failed: {str(e)}")

@app.get("/super-admin/scheduled-documents")
async def get_scheduled_documents(current_user: dict = Depends(get_current_user)):
    """Get all documents scheduled for processing."""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Not authorized to view scheduled documents")
    
    try:
        client = get_service_client()
        
        # Get all scheduled documents
        query = (client.table("documents")
                .select("id, filename, file_type, file_size, college_id, scheduled_at, created_at")
                .eq("process_schedule", "scheduled")
                .eq("status", "approved")
                .order("scheduled_at", desc=False))
        
        response = query.execute()
        
        scheduled_documents = []
        for doc in response.data:
            # Get college name
            college_query = client.table("colleges").select("name").eq("id", doc["college_id"])
            college_response = college_query.execute()
            college_name = college_response.data[0]["name"] if college_response.data else "Unknown College"
            
            scheduled_documents.append({
                "id": doc["id"],
                "filename": doc["filename"],
                "file_type": doc["file_type"],
                "file_size": doc["file_size"],
                "college_id": doc["college_id"],
                "college_name": college_name,
                "scheduled_at": doc["scheduled_at"],
                "created_at": doc["created_at"]
            })
        
        return {
            "scheduled_documents": scheduled_documents,
            "total_scheduled": len(scheduled_documents)
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to retrieve scheduled documents: {str(e)}")


# Additional Super Admin APIs used by the Super Admin frontend
@app.get("/superadmin/stats")
async def get_superadmin_stats(current_user: dict = Depends(get_current_user)):
    """Global stats for the Super Admin dashboard."""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Not authorized to view superadmin stats")

    try:
        client = get_service_client()

        # Total colleges
        colleges_resp = client.table("colleges").select("id", count="exact").execute()
        total_colleges = colleges_resp.count or len(colleges_resp.data or [])

        # Total college admins
        admins_resp = (
            client.table("profiles")
            .select("id", count="exact")
            .eq("role", "college_admin")
            .execute()
        )
        total_admins = admins_resp.count or len(admins_resp.data or [])

        # Total documents
        documents_resp = client.table("documents").select("id", count="exact").execute()
        total_docs = documents_resp.count or len(documents_resp.data or [])

        # Total user queries (messages from users)
        messages_resp = (
            client.table("messages")
            .select("id", count="exact")
            .eq("role", "user")
            .execute()
        )
        total_queries = messages_resp.count or len(messages_resp.data or [])

        return {
            "colleges": total_colleges,
            "totalAdmins": total_admins,
            "totalDocs": total_docs,
            "totalQueries": total_queries,
            # For now this is a static value; could be derived from cluster status later
            "activeNodes": 12,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to retrieve superadmin stats: {str(e)}")


@app.get("/superadmin/colleges")
async def get_superadmin_colleges(
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """List all colleges for the Super Admin panel."""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Not authorized to view colleges")

    try:
        client = get_service_client()
        query = client.table("colleges").select("id, name, domain, created_at")

        if search:
            # Case-insensitive search on college name
            query = query.ilike("name", f"%{search}%")

        colleges_resp = query.execute()
        colleges = colleges_resp.data or []

        # For each college, compute admin_count (number of college_admin profiles)
        result = []
        for college in colleges:
            admin_count = 0
            try:
                admins_resp = (
                    client.table("profiles")
                    .select("id", count="exact")
                    .eq("role", "college_admin")
                    .eq("college_id", college["id"])
                    .execute()
                )
                admin_count = admins_resp.count or len(admins_resp.data or [])
            except Exception:
                admin_count = 0

            result.append(
                {
                    "id": college["id"],
                    "name": college["name"],
                    "domain": college.get("domain"),
                    "admin_count": admin_count,
                }
            )

        return {"colleges": result}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to retrieve colleges: {str(e)}")


@app.get("/superadmin/admins")
async def get_superadmin_admins(
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """List all college admins for the Super Admin panel."""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Not authorized to view admins")

    try:
        client = get_service_client()

        # Get all college admins
        admins_resp = (
            client.table("profiles")
            .select("id, college_id, full_name, role, created_at")
            .eq("role", "college_admin")
            .execute()
        )
        admins = admins_resp.data or []

        # Load college names for mapping
        college_ids = {a["college_id"] for a in admins if a.get("college_id")}
        college_map = {}
        if college_ids:
            colleges_resp = (
                client.table("colleges")
                .select("id, name")
                .in_("id", list(college_ids))
                .execute()
            )
            for c in colleges_resp.data or []:
                college_map[c["id"]] = c["name"]

        # Build response objects
        admin_list = []
        for a in admins:
            name = a.get("full_name") or "Unnamed Admin"
            college_id = a.get("college_id")
            college_name = college_map.get(college_id, "Unassigned")

            admin_item = {
                "id": a["id"],
                "name": name,
                # Email is stored in auth.users; for now we return placeholder to avoid errors in UI
                "email": "",
                "college_id": college_id,
                "college": college_name,
                # Profiles table has no explicit status; treat all as active for now
                "status": "active",
                "joined": a.get("created_at"),
            }
            admin_list.append(admin_item)

        # Optional in-memory search filtering across name, email and college
        if search:
            lowered = search.lower()
            admin_list = [
                a
                for a in admin_list
                if lowered in a["name"].lower()
                or lowered in (a["email"] or "").lower()
                or lowered in (a["college"] or "").lower()
            ]

        return {"admins": admin_list}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to retrieve admins: {str(e)}")


@app.get("/superadmin/documents")
async def get_superadmin_documents(
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Global document log grouped by college and uploader for Super Admin panel."""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Not authorized to view documents")

    try:
        client = get_service_client()

        docs_resp = (
            client.table("documents")
            .select("id, filename, file_type, file_size, college_id, uploaded_by, created_at")
            .execute()
        )
        docs = docs_resp.data or []

        if not docs:
            return {"groups": []}

        # Load related colleges and uploader profiles
        college_ids = {d["college_id"] for d in docs if d.get("college_id")}
        uploader_ids = {d["uploaded_by"] for d in docs if d.get("uploaded_by")}

        college_map = {}
        if college_ids:
            colleges_resp = (
                client.table("colleges")
                .select("id, name")
                .in_("id", list(college_ids))
                .execute()
            )
            for c in colleges_resp.data or []:
                college_map[c["id"]] = c["name"]

        uploader_map = {}
        if uploader_ids:
            profiles_resp = (
                client.table("profiles")
                .select("id, full_name")
                .in_("id", list(uploader_ids))
                .execute()
            )
            for p in profiles_resp.data or []:
                uploader_map[p["id"]] = p.get("full_name") or "Unknown Admin"

        # Group by (college_id, uploaded_by)
        groups_map = {}

        for doc in docs:
            college_id = doc.get("college_id")
            uploader_id = doc.get("uploaded_by")
            college_name = college_map.get(college_id, "Unknown College")
            admin_name = uploader_map.get(uploader_id, "Unknown Admin")

            key = (college_id, uploader_id)
            if key not in groups_map:
                groups_map[key] = {
                    "college": college_name,
                    "admin_name": admin_name,
                    "total_documents": 0,
                    "documents": [],
                }

            doc_item = {
                "id": doc["id"],
                "name": doc["filename"],
                "uploaded_at": doc.get("created_at"),
                "type": (doc.get("file_type") or "").upper(),
                "size": f"{doc.get('file_size', 0)} bytes" if doc.get("file_size") is not None else "",
            }
            groups_map[key]["documents"].append(doc_item)
            groups_map[key]["total_documents"] += 1

        groups = list(groups_map.values())

        # Optional search filtering across college, admin or document name
        if search:
            lowered = search.lower()
            filtered_groups = []
            for g in groups:
                if lowered in g["college"].lower() or lowered in g["admin_name"].lower():
                    filtered_groups.append(g)
                    continue

                # Check documents inside the group
                docs_match = [
                    d
                    for d in g["documents"]
                    if lowered in d["name"].lower()
                ]
                if docs_match:
                    g_copy = g.copy()
                    g_copy["documents"] = docs_match
                    g_copy["total_documents"] = len(docs_match)
                    filtered_groups.append(g_copy)

            groups = filtered_groups

        return {"groups": groups}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to retrieve documents: {str(e)}")


# Notification Endpoints
@app.get("/notifications")
async def get_notifications(
    unread_only: Optional[bool] = None,
    notification_type: Optional[str] = None,
    limit: Optional[int] = 50,
    offset: Optional[int] = 0,
    current_user: dict = Depends(get_current_user)
):
    """Get notifications for the current user with optional filtering"""
    try:
        # Validate notification type if provided
        validated_type = None
        if notification_type:
            try:
                validated_type = NotificationType(notification_type)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid notification type: {notification_type}")
        
        # Create filters
        filters = NotificationFilters(
            unread_only=unread_only,
            notification_type=validated_type,
            limit=min(limit, 100),  # Cap at 100
            offset=max(offset, 0)   # Ensure non-negative
        )
        
        # Get notifications
        notifications = await notification_manager.get_notifications(
            user_id=UUID(current_user["user_id"]),
            filters=filters
        )
        
        # Get unread count
        unread_count = await notification_manager.get_unread_count(
            user_id=UUID(current_user["user_id"])
        )
        
        return {
            "notifications": notifications,
            "unread_count": unread_count,
            "total_count": len(notifications),
            "filters": {
                "unread_only": unread_only,
                "notification_type": notification_type,
                "limit": limit,
                "offset": offset
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to retrieve notifications: {str(e)}")

@app.put("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Mark a specific notification as read"""
    try:
        success = await notification_manager.mark_as_read(
            notification_id=notification_id,
            user_id=UUID(current_user["user_id"])
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Notification not found or already read")
        
        return {
            "status": "success",
            "message": "Notification marked as read",
            "notification_id": str(notification_id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to mark notification as read: {str(e)}")

@app.delete("/notifications/{notification_id}")
async def delete_notification(
    notification_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Delete a specific notification"""
    try:
        success = await notification_manager.delete_notification(
            notification_id=notification_id,
            user_id=UUID(current_user["user_id"])
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        return {
            "status": "success",
            "message": "Notification deleted successfully",
            "notification_id": str(notification_id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to delete notification: {str(e)}")

@app.get("/notifications/unread-count")
async def get_unread_notification_count(current_user: dict = Depends(get_current_user)):
    """Get the count of unread notifications for the current user"""
    try:
        unread_count = await notification_manager.get_unread_count(
            user_id=UUID(current_user["user_id"])
        )
        
        return {
            "unread_count": unread_count
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get unread count: {str(e)}")

@app.get("/")
async def root():
    return {"message": "Welcome to Our Application!"}

@app.get("/student/{student_id}")
async def get_student(student_id: int):
    return {"student_id": student_id, "name": "John Doe", "age": 21,"Query":"Sample Query"}