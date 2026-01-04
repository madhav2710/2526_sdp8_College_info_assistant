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
import os

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

        # 4. Generate RAG response using the new retrieval system
        from app.core.rag import generate_rag_response
        
        rag_result = await generate_rag_response(
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

    try:
        # Use service client to bypass RLS for storage and DB
        client = get_service_client()
        
        file_content = await file.read()
        file_size = len(file_content)  # Calculate file size
        filename = f"{uuid4()}_{file.filename}"
        path = f"{target_college_id}/{filename}"

        # Upload to Supabase Storage using direct HTTP to ensure Service Key is used
        import httpx
        from app.core.database import url as supabase_url, service_key
        
        storage_url = f"{supabase_url}/storage/v1/object/documents/{path}"
        headers = {
            "Authorization": f"Bearer {service_key}",
            "Content-Type": file.content_type,
            "x-upsert": "true" 
        }
        
        async with httpx.AsyncClient() as http_client:
            r = await http_client.post(storage_url, content=file_content, headers=headers, timeout=60.0)
            if r.status_code not in [200, 201]:
                 raise HTTPException(status_code=400, detail=f"File upload failed: {r.text}")

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
            "filename": file.filename,
            "storage_path": path,
            "file_type": file_type_val,
            "file_size": file_size,
            "uploaded_by": current_user["user_id"],
            "status": "pending_approval"  # Changed to require approval before processing
        }

        # Use direct HTTP for DB Insert to ensure Service Key is used
        db_url = f"{supabase_url}/rest/v1/documents"
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
            raise HTTPException(status_code=500, detail="Failed to create document record")

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
            
            # Get uploader email
            uploader_query = client.table("profiles").select("email").eq("id", doc["uploaded_by"])
            uploader_response = uploader_query.execute()
            uploader_email = uploader_response.data[0]["email"] if uploader_response.data else "Unknown User"
            
            pending_documents.append({
                "id": doc["id"],
                "filename": doc["filename"],
                "file_type": doc["file_type"],
                "file_size": doc["file_size"],
                "college_id": doc["college_id"],
                "college_name": college_name,
                "uploaded_by": doc["uploaded_by"],
                "uploader_email": uploader_email,
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

class DocumentApprovalRequest(BaseModel):
    document_id: UUID
    comments: Optional[str] = None

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
        
        if document["status"] not in ["uploaded", "pending_approval"]:
            raise HTTPException(status_code=400, detail=f"Document cannot be approved. Current status: {document['status']}")
        
        # Update document status to 'approved' and add approval metadata
        update_data = {
            "status": "approved",
            "approved_by": current_user["user_id"],
            "approval_comments": request.comments,
            "updated_at": datetime.now(dt.UTC).isoformat()
        }
        
        # Use direct HTTP for DB update to ensure Service Key is used
        from app.core.database import url as supabase_url, service_key
        import httpx
        
        db_url = f"{supabase_url}/rest/v1/documents?id=eq.{request.document_id}"
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
        
        approval_url = f"{supabase_url}/rest/v1/document_approvals"
        async with httpx.AsyncClient() as http_client:
            r_approval = await http_client.post(approval_url, json=approval_data, headers=db_headers, timeout=10.0)
            if r_approval.status_code not in [200, 201]:
                # Log but don't fail the approval if approval record creation fails
                print(f"Warning: Failed to create approval record: {r_approval.text}")
        
        # Trigger RAG processing in background task
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
            "message": f"Document '{document['filename']}' has been approved for processing",
            "document": {
                "id": str(request.document_id),
                "filename": document["filename"],
                "status": "approved",
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
        
        if document["status"] not in ["uploaded", "pending_approval"]:
            raise HTTPException(status_code=400, detail=f"Document cannot be rejected. Current status: {document['status']}")
        
        # Update document status to 'rejected' and add rejection metadata
        update_data = {
            "status": "rejected",
            "approved_by": current_user["user_id"],  # Using same field for consistency
            "approval_comments": request.reason,
            "updated_at": datetime.now(dt.UTC).isoformat()
        }
        
        # Use direct HTTP for DB update to ensure Service Key is used
        from app.core.database import url as supabase_url, service_key
        import httpx
        
        db_url = f"{supabase_url}/rest/v1/documents?id=eq.{request.document_id}"
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
        
        approval_url = f"{supabase_url}/rest/v1/document_approvals"
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
