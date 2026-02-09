from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from uuid import UUID, uuid4
from datetime import datetime
import datetime as dt
import time
import asyncio
from typing import Optional
from app.core.database import supabase, get_service_client
from app.core.auth import get_current_user
from app.core.notifications import notification_manager
from app.models.notification import NotificationFilters, NotificationType
from app.core.workflow import validate_status_transition, log_status_change
from app.core.basic_chat import generate_basic_response
from app.core.config import validate_startup_configuration, get_system_config, ConfigurationError
import os
import hashlib
import mimetypes
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize and validate configuration at startup
try:
    validate_startup_configuration()
    system_config = get_system_config()
    logger.info(f"Configuration validated successfully: {system_config.application.app_name} v{system_config.application.app_version}")
    
    # Set logging level from configuration
    logging.getLogger().setLevel(system_config.application.log_level.value)
    
    if not system_config.ai.gemini_api_key:
        logger.warning("GEMINI_API_KEY not configured - RAG functionality will be limited")
    else:
        logger.info("RAG system fully configured and ready")
        
except ConfigurationError as e:
    logger.error(f"Configuration validation failed: {str(e)}")
    logger.error("Application startup failed due to invalid configuration")
    raise SystemExit(1)
except Exception as e:
    logger.error(f"Unexpected error during configuration validation: {str(e)}")
    logger.error("Application startup failed")
    raise SystemExit(1)

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

# File validation will use configuration values
def get_file_config():
    """Get file configuration from system config"""
    return get_system_config().file

def validate_file(file: UploadFile, file_content: bytes) -> tuple[bool, Optional[str]]:
    """
    Validate uploaded file using configuration settings.
    
    Returns:
        (is_valid, error_message)
    """
    file_config = get_file_config()
    max_file_size = file_config.max_file_size_mb * 1024 * 1024  # Convert MB to bytes
    allowed_extensions = set(file_config.allowed_file_extensions)
    
    # Check file size
    if len(file_content) > max_file_size:
        return False, f"File exceeds {file_config.max_file_size_mb}MB limit"
    
    if len(file_content) == 0:
        return False, "File is empty"
    
    # Check file extension
    file_ext = None
    if file.filename:
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            return False, f"Only {', '.join(allowed_extensions)} files are allowed"
    
    # Check MIME type (basic validation)
    allowed_mime_types = {
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain'
    }
    
    if file.content_type and file.content_type not in allowed_mime_types:
        return False, f"Invalid file type. Allowed types: {', '.join(allowed_mime_types)}"
    
    # Verify MIME type matches extension
    if file_ext and file.content_type:
        expected_mime = mimetypes.guess_type(file.filename)[0]
        if expected_mime and expected_mime != file.content_type:
            return False, "File type mismatch. Please ensure the file extension matches the file content."
    
    # Try to read file to check for corruption (basic check).
    # If optional PDF dependency (pypdf) is missing, skip deep PDF validation
    # instead of failing the upload.
    if file_ext == '.pdf':
        try:
            from io import BytesIO
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(file_content))
            if len(reader.pages) == 0:
                return False, "PDF file appears to be corrupted or empty"
        except ModuleNotFoundError:
            # pypdf not installed: skip advanced PDF validation
            pass
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

# <<<<<<< Updated upstream
class AdminCreateRequest(BaseModel):
    name: str
    email: EmailStr
    college_id: str
    password: str

class AdminUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    college_id: Optional[str] = None

class AdminStatusUpdateRequest(BaseModel):
    status: str

class CollegeCreateRequest(BaseModel):
    name: str
    code: str
    domain: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: Optional[bool] = True

class CollegeUpdateRequest(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    domain: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: Optional[bool] = None
# =======
async def _trigger_rag_processing_with_status_tracking(
    document_id: str, 
    filename: str, 
    approved_by: str
):
    """
    Enhanced RAG processing trigger with comprehensive status tracking and error handling.
    
    This function provides better integration between document approval and RAG processing,
    including detailed logging, error handling, and status updates.
    """
    client = get_service_client()
    
    try:
        logger.info(f"Starting RAG processing for document {document_id} ({filename})")
        
        # Update document status to indicate RAG processing has started
        try:
            client.table("documents").update({
                "status": "processing",
                "processing_started_at": datetime.now(dt.UTC).isoformat(),
                "processing_metadata": {
                    "triggered_by": "document_approval",
                    "approved_by": approved_by,
                    "processing_type": "immediate",
                    "start_time": datetime.now(dt.UTC).isoformat()
                }
            }).eq("id", document_id).execute()
            
            logger.info(f"Document {document_id} status updated to processing")
            
        except Exception as status_error:
            logger.error(f"Failed to update document status to processing: {str(status_error)}")
            # Continue with processing even if status update fails
        
        # Import and trigger RAG processing
        from app.core.rag import trigger_rag_processing
        await trigger_rag_processing(document_id)
        
        logger.info(f"RAG processing completed successfully for document {document_id} ({filename})")
        
    except Exception as e:
        logger.error(f"RAG processing failed for document {document_id} ({filename}): {str(e)}")
        
        # Update document status to failed with error details
        try:
            client.table("documents").update({
                "status": "failed",
                "error_message": f"RAG processing failed: {str(e)}",
                "failed_at": datetime.now(dt.UTC).isoformat(),
                "processing_metadata": {
                    "triggered_by": "document_approval",
                    "approved_by": approved_by,
                    "processing_type": "immediate",
                    "error": str(e),
                    "failed_at": datetime.now(dt.UTC).isoformat()
                }
            }).eq("id", document_id).execute()
            
            logger.info(f"Document {document_id} status updated to failed")
            
        except Exception as status_error:
            logger.error(f"Failed to update document status to failed: {str(status_error)}")
        
        # Create failure notification
        try:
            # Get document details for notification
            doc_res = client.table("documents").select("uploaded_by").eq("id", document_id).execute()
            if doc_res.data and doc_res.data[0]["uploaded_by"]:
                await notification_manager.create_document_notification(
                    recipient_ids=[UUID(doc_res.data[0]["uploaded_by"])],
                    notification_type=NotificationType.DOCUMENT_FAILED,
                    document_id=UUID(document_id),
                    document_filename=filename,
                    additional_metadata={
                        "error_message": str(e),
                        "processing_type": "immediate",
                        "failed_at": datetime.now(dt.UTC).isoformat()
                    }
                )
        except Exception as notification_error:
            logger.warning(f"Failed to create processing failure notification: {str(notification_error)}")

@app.post("/admin/trigger-rag-processing")
async def trigger_manual_rag_processing(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Manually trigger RAG processing for an approved document.
    
    This endpoint allows college admins to trigger RAG processing for documents
    that are approved but not yet processed.
    """
    if current_user["role"] != "college_admin":
        raise HTTPException(status_code=403, detail="Not authorized to trigger RAG processing")
    
    target_college_id = current_user["college_id"]
    if not target_college_id:
        raise HTTPException(status_code=400, detail="User is not associated with a college")
    
    try:
        client = get_service_client()
        
        # Verify document exists and belongs to the user's college
        doc_query = client.table("documents").select("*").eq("id", str(document_id)).eq("college_id", target_college_id).execute()
        
        if not doc_query.data:
            raise HTTPException(status_code=404, detail="Document not found or not accessible")
        
        document = doc_query.data[0]
        current_status = document["status"]
        filename = document["filename"]
        
        # Verify document is in a state that allows RAG processing
        if current_status not in ["approved", "failed"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Document must be approved or failed to trigger RAG processing. Current status: {current_status}"
            )
        
        # Update document status to processing
        client.table("documents").update({
            "status": "processing",
            "processing_started_at": datetime.now(dt.UTC).isoformat(),
            "processing_metadata": {
                "triggered_by": "manual_trigger",
                "triggered_by_user": current_user["user_id"],
                "processing_type": "manual",
                "start_time": datetime.now(dt.UTC).isoformat()
            }
        }).eq("id", str(document_id)).execute()
        
        # Log status change
        try:
            log_status_change(
                client=client,
                document_id=str(document_id),
                old_status=current_status,
                new_status="processing",
                changed_by=current_user["user_id"],
                comments="Manual RAG processing triggered"
            )
        except Exception as log_error:
            logger.warning(f"Failed to log status change: {str(log_error)}")
        
        # Trigger RAG processing
        background_tasks.add_task(
            _trigger_rag_processing_with_status_tracking,
            str(document_id),
            filename,
            current_user["user_id"]
        )
        
        logger.info(f"Manual RAG processing triggered for document {document_id} ({filename}) by user {current_user['user_id']}")
        
        return {
            "status": "success",
            "message": f"RAG processing started for document '{filename}'",
            "document": {
                "id": str(document_id),
                "filename": filename,
                "status": "processing",
                "triggered_by": current_user["user_id"],
                "triggered_at": datetime.now(dt.UTC).isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger manual RAG processing for document {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger RAG processing: {str(e)}")
# >>>>>>> Stashed changes


class GuestChatRequest(BaseModel):
    content: str
    college_id: Optional[str] = None


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    college_id: Optional[str] = None


class SetCollegeRequest(BaseModel):
    college_id: str


# Auth Endpoints
@app.post("/auth/signup")
async def signup(request: SignupRequest):
    """
    Sign up a new end-user (student role by default).
    This creates:
      - An auth user in Supabase (via regular client to trigger confirmation email)
      - A profile row in public.profiles (via admin client)
      - Sends a confirmation email to the user automatically
    
    The user must confirm their email before they can log in.
    """
    try:
        from app.core.database import supabase
        
        # Use regular client (not admin) to sign up - this automatically sends confirmation email
        try:
            auth_resp = supabase.auth.sign_up(
                {
                    "email": request.email,
                    "password": request.password,
                }
            )
        except Exception as e:
            msg = str(e)
            if "User already registered" in msg or "email_already_in_use" in msg or "already registered" in msg.lower():
                raise HTTPException(status_code=400, detail="An account with this email already exists")
            raise

        # Extract user from response
        user = None
        if hasattr(auth_resp, "user") and auth_resp.user:
            user = auth_resp.user
        elif hasattr(auth_resp, "data") and auth_resp.data:
            if isinstance(auth_resp.data, dict):
                user = auth_resp.data.get("user")
            else:
                user = getattr(auth_resp.data, "user", None)
        
        if not user:
            raise HTTPException(status_code=500, detail="Failed to create auth user")

        # Get user ID
        raw_user_id = None
        if hasattr(user, "id"):
            raw_user_id = user.id
        elif isinstance(user, dict):
            raw_user_id = user.get("id")
        
        if raw_user_id is None:
            raise HTTPException(status_code=500, detail="Auth user record is missing an id")
        user_id = str(raw_user_id)

        # Now use admin client to create the profile (since we need service role for table operations)
        client = get_service_client()

        # Optionally validate and attach college_id if provided
        college_id = None
        if request.college_id:
            college_check = (
                client.table("colleges")
                .select("id")
                .eq("id", request.college_id)
                .limit(1)
                .execute()
            )
            if not (college_check.data or []):
                raise HTTPException(status_code=400, detail="Invalid college selected")
            college_id = request.college_id

        # Create profile with default student role
        profile_data = {
            "id": user_id,
            "full_name": request.full_name,
            "role": "student",
            "college_id": college_id,
        }
        client.table("profiles").insert(profile_data).execute()

        return {
            "message": "Signup successful! Please check your email to confirm your account before logging in.",
            "email_sent": True
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Signup failed: {str(e)}")


@app.get("/public/colleges")
async def list_public_colleges():
    """Public list of colleges for end-user selection."""
    try:
        client = get_service_client()
        resp = client.table("colleges").select("id, name, domain, code").order("name").execute()
        return {"colleges": resp.data or []}
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to load colleges: {str(e)}")


@app.get("/user/profile")
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    """Get the current user's full profile information."""
    try:
        client = get_service_client()
        user_id = current_user["user_id"]
        
        # Get user email from auth using admin API
        user_email = None
        try:
            auth_user = client.auth.admin.get_user_by_id(user_id)
            if hasattr(auth_user, "user") and auth_user.user:
                user_email = auth_user.user.email
            elif isinstance(auth_user, dict) and "user" in auth_user:
                user_email = auth_user["user"].get("email")
            elif hasattr(auth_user, "data"):
                user_data = auth_user.data
                if isinstance(user_data, dict) and "user" in user_data:
                    user_email = user_data["user"].get("email")
                elif hasattr(user_data, "email"):
                    user_email = user_data.email
        except Exception as e:
            logger.warning(f"Could not fetch user email: {str(e)}")
        
        # Fetch profile with college name
        profile_query = client.table("profiles").select("full_name, role, college_id").eq("id", user_id).execute()
        
        if not profile_query.data:
            raise HTTPException(status_code=404, detail="User profile not found")
        
        profile = profile_query.data[0]
        college_name = None
        
        # Fetch college name if college_id exists
        if profile.get("college_id"):
            college_query = client.table("colleges").select("name").eq("id", profile["college_id"]).execute()
            if college_query.data:
                college_name = college_query.data[0]["name"]
        
        return {
            "user_id": user_id,
            "email": user_email,
            "full_name": profile.get("full_name"),
            "role": profile["role"],
            "college_id": profile.get("college_id"),
            "college_name": college_name
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch user profile: {str(e)}")


@app.post("/user/set-college")
async def set_user_college(
    request: SetCollegeRequest,
    current_user: dict = Depends(get_current_user),
):
    """Attach the logged-in user to a college (sets profiles.college_id)."""
    try:
        client = get_service_client()
        user_id = current_user["user_id"]

        # Validate college exists
        college_check = client.table("colleges").select("id").eq("id", request.college_id).limit(1).execute()
        if not (college_check.data or []):
            raise HTTPException(status_code=400, detail="Invalid college selected")

        client.table("profiles").update({"college_id": request.college_id}).eq("id", user_id).execute()
        return {"status": "success", "college_id": request.college_id}
    except HTTPException:
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to set college: {str(e)}")


@app.post("/auth/login")
async def login(request: LoginRequest):
    try:
        # Authenticate with Supabase
        auth_response = supabase.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password
        })
        
        # Fetch user profile with full details
        user_id = auth_response.user.id
        user_email = auth_response.user.email
        profile_response = supabase.table("profiles").select("role, college_id, full_name").eq("id", user_id).execute()
        
        if not profile_response.data:
            raise HTTPException(status_code=404, detail="User profile not found")
            
        profile = profile_response.data[0]
        
        return {
            "access_token": auth_response.session.access_token,
            "token_type": "bearer",
            "user_id": user_id,
            "email": user_email,
            "full_name": profile.get("full_name"),
            "role": profile["role"],
            "college_id": profile["college_id"]
        }
    except HTTPException:
        # Preserve explicit HTTPExceptions (e.g. 404 profile not found)
        raise
    except Exception as e:
        if "Invalid login credentials" in str(e):
            raise HTTPException(status_code=401, detail="Invalid login credentials")
        # For all other unexpected errors, surface a generic message
        raise HTTPException(status_code=400, detail="Login failed due to a server error. Please try again.")

@app.post("/chat/")
async def create_chat(message: ChatMessage, current_user: dict = Depends(get_current_user)):
    """
    Enhanced chat endpoint with improved RAG integration, error handling, and logging.
    
    Requirements addressed:
    - 5.3: Authentication enforcement
    - 5.4: Enhanced error handling and response formatting
    - 7.1: Proper logging for RAG operations
    """
    # Rate limiting: Track expensive RAG operations per user
    user_id_str = str(message.user_id)
    current_time = time.time()
    
    # Simple in-memory rate limiting (in production, use Redis or database)
    if not hasattr(create_chat, 'rate_limit_cache'):
        create_chat.rate_limit_cache = {}
    
    # Clean old entries (older than 1 minute)
    create_chat.rate_limit_cache = {
        uid: timestamps for uid, timestamps in create_chat.rate_limit_cache.items()
        if any(t > current_time - 60 for t in timestamps)
    }
    
    # Check rate limit (max 10 requests per minute per user)
    user_requests = create_chat.rate_limit_cache.get(user_id_str, [])
    recent_requests = [t for t in user_requests if t > current_time - 60]
    
    if len(recent_requests) >= 10:
        logger.warning(f"Rate limit exceeded for user {user_id_str}")
        raise HTTPException(
            status_code=429, 
            detail="Too many requests. Please wait before sending another message."
        )
    
    # Update rate limit cache
    recent_requests.append(current_time)
    create_chat.rate_limit_cache[user_id_str] = recent_requests
    
    # Enhanced logging for chat operations
    logger.info(f"Processing chat message from user {user_id_str} in conversation {message.conversation_id}")
    
    try:
        client = get_service_client()

        # 1. Enhanced authentication and authorization
        # Verify user exists and get college_id with proper error handling
        try:
            profile = client.table("profiles").select("college_id, role").eq("id", str(message.user_id)).execute()
            if not profile.data:
                logger.error(f"User profile not found for user_id: {message.user_id}")
                raise HTTPException(status_code=404, detail="User profile not found")
            
            college_id = profile.data[0]["college_id"]
            user_role = profile.data[0]["role"]
            
            if not college_id:
                logger.error(f"User {message.user_id} is not associated with a college")
                raise HTTPException(status_code=400, detail="User is not associated with a college")
            
            # Verify user has permission to access this conversation
            if current_user["user_id"] != str(message.user_id):
                logger.warning(f"User {current_user['user_id']} attempted to send message as user {message.user_id}")
                raise HTTPException(status_code=403, detail="Not authorized to send messages for this user")
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error during user authentication: {str(e)}")
            raise HTTPException(status_code=500, detail="Authentication error")

        # 2. Enhanced conversation management
        try:
            conv_check = client.table("conversations").select("id, user_id, college_id").eq("id", str(message.conversation_id)).execute()
            
            if not conv_check.data:
                # Create new conversation with enhanced metadata
                conversation_data = {
                    "id": str(message.conversation_id),
                    "user_id": str(message.user_id),
                    "college_id": college_id,
                    "title": message.content[:50] + ("..." if len(message.content) > 50 else ""),
                    "created_at": datetime.now(dt.UTC).isoformat()
                }
                client.table("conversations").insert(conversation_data).execute()
                logger.info(f"Created new conversation {message.conversation_id} for user {message.user_id}")
            else:
                # Verify user owns this conversation
                existing_conv = conv_check.data[0]
                if existing_conv["user_id"] != str(message.user_id):
                    logger.warning(f"User {message.user_id} attempted to access conversation {message.conversation_id} owned by {existing_conv['user_id']}")
                    raise HTTPException(status_code=403, detail="Not authorized to access this conversation")
                
                if existing_conv["college_id"] != college_id:
                    logger.warning(f"College ID mismatch for conversation {message.conversation_id}")
                    raise HTTPException(status_code=403, detail="College access violation")
                    
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error managing conversation {message.conversation_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Conversation management error")

        # 3. Store user message with enhanced error handling
        try:
            user_message_data = {
                "conversation_id": str(message.conversation_id),
                "role": "user",
                "content": message.content,
                "created_at": datetime.now(dt.UTC).isoformat()
            }
            user_message_response = client.table("messages").insert(user_message_data).execute()
            
            if not user_message_response.data:
                raise Exception("Failed to store user message")
                
            logger.debug(f"Stored user message in conversation {message.conversation_id}")
            
        except Exception as e:
            logger.error(f"Error storing user message: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to store message")

        # 4. Enhanced RAG response generation with comprehensive error handling
        rag_result = None
        response_metadata = {
            "rag_used": False,
            "fallback_used": False,
            "processing_time": 0,
            "error_details": None
        }
        
        start_time = time.time()
        
        # Import RAG modules - handle import errors gracefully
        try:
            from app.core.rag import generate_rag_response, RAGError, EmbeddingServiceError, VectorStoreError
            rag_available = True
        except (ImportError, ModuleNotFoundError) as import_error:
            logger.warning(f"RAG module not available: {str(import_error)}")
            rag_available = False
            EmbeddingServiceError = None
            VectorStoreError = None
            RAGError = None
        
        try:
            if not rag_available:
                raise ImportError("RAG module dependencies not installed")
                
            logger.info(f"Attempting RAG response for query: '{message.content[:100]}...' (college: {college_id})")
            
            # Retrieve conversation history for context maintenance (Requirement 4.5)
            conversation_history = []
            try:
                # Get last 10 messages from this conversation for context
                history_response = client.table("messages").select(
                    "role, content, created_at"
                ).eq("conversation_id", str(message.conversation_id)).order(
                    "created_at", desc=False
                ).limit(10).execute()
                
                if history_response.data:
                    # Exclude the current user message (it's not stored yet)
                    conversation_history = [
                        {
                            "role": msg["role"],
                            "content": msg["content"],
                            "created_at": msg["created_at"]
                        }
                        for msg in history_response.data
                    ]
                    logger.debug(f"Retrieved {len(conversation_history)} messages for conversation context")
                    
            except Exception as history_error:
                logger.warning(f"Failed to retrieve conversation history: {str(history_error)}")
                # Continue without history - not critical for basic functionality
            
            rag_result = await generate_rag_response(
                query=message.content,
                college_id=college_id,
                conversation_history=conversation_history
            )
            
            response_metadata["rag_used"] = True
            response_metadata["processing_time"] = time.time() - start_time
            
            if rag_result.get("fallback_used", False):
                response_metadata["fallback_used"] = True
                logger.warning(f"RAG fallback used for query: {message.content[:50]}...")
            else:
                quality_score = rag_result.get("quality_score", 0.0)
                logger.info(f"RAG response generated successfully using {rag_result.get('chunks_used', 0)} chunks from {len(rag_result.get('sources', []))} sources (quality: {quality_score:.2f})")
                
        except (ImportError, ModuleNotFoundError) as import_error:
            logger.warning(f"RAG not available, using basic chat: {str(import_error)}")
            rag_result = await generate_basic_response(
                query=message.content,
                college_id=college_id
            )
            response_metadata["fallback_used"] = True
            response_metadata["rag_used"] = False
                
        except Exception as e:
            # Check if this is a RAG-specific error (only if RAG is available)
            if rag_available and EmbeddingServiceError and isinstance(e, EmbeddingServiceError):
                logger.error(f"Embedding service error for user {message.user_id}: {str(e)}")
                response_metadata["error_details"] = f"AI service error: {str(e)}"
                
                # Fallback to basic chat for embedding service errors
                try:
                    rag_result = await generate_basic_response(
                        query=message.content,
                        college_id=college_id
                    )
                    response_metadata["fallback_used"] = True
                    logger.info(f"Fallback to basic chat successful for user {message.user_id}")
                except Exception as fallback_error:
                    logger.error(f"Basic chat fallback failed: {str(fallback_error)}")
                    raise HTTPException(status_code=503, detail="AI services are temporarily unavailable")
            elif rag_available and VectorStoreError and isinstance(e, VectorStoreError):
                logger.error(f"Vector store error for user {message.user_id}: {str(e)}")
                response_metadata["error_details"] = f"Document search error: {str(e)}"
                
                # Fallback to basic chat for vector store errors
                try:
                    rag_result = await generate_basic_response(
                        query=message.content,
                        college_id=college_id
                    )
                    response_metadata["fallback_used"] = True
                    logger.info(f"Fallback to basic chat successful after vector store error")
                except Exception as fallback_error:
                    logger.error(f"Basic chat fallback failed: {str(fallback_error)}")
                    raise HTTPException(status_code=503, detail="Document search is temporarily unavailable")
            elif rag_available and RAGError and isinstance(e, RAGError):
                logger.error(f"RAG system error for user {message.user_id}: {str(e)}")
                response_metadata["error_details"] = f"RAG system error: {str(e)}"
                
                # Fallback to basic chat for general RAG errors
                try:
                    rag_result = await generate_basic_response(
                        query=message.content,
                        college_id=college_id
                    )
                    response_metadata["fallback_used"] = True
                    logger.info(f"Fallback to basic chat successful after RAG error")
                except Exception as fallback_error:
                    logger.error(f"Basic chat fallback failed: {str(fallback_error)}")
                    raise HTTPException(status_code=503, detail="Chat service is temporarily unavailable")
            else:
                # Generic exception - fallback to basic chat
                logger.error(f"Unexpected error during RAG processing for user {message.user_id}: {str(e)}")
                response_metadata["error_details"] = f"Unexpected error: {str(e)}"
                
                # Final fallback to basic chat
                try:
                    rag_result = await generate_basic_response(
                        query=message.content,
                        college_id=college_id
                    )
                    response_metadata["fallback_used"] = True
                    logger.info(f"Final fallback to basic chat successful")
                except Exception as fallback_error:
                    logger.error(f"All fallback mechanisms failed: {str(fallback_error)}")
                    raise HTTPException(status_code=503, detail="All chat services are temporarily unavailable")
        
        # Ensure we have a valid response
        if not rag_result or not rag_result.get("response"):
            logger.error(f"No valid response generated for user {message.user_id}")
            raise HTTPException(status_code=500, detail="Failed to generate response")

        # 5. Enhanced response storage with graceful handling of missing columns
        try:
            # Prepare enhanced metadata for storage with source details
            sources_data = rag_result.get("sources", [])
            source_details = rag_result.get("source_details", [])
            chunks_used = rag_result.get("chunks_used", 0)
            quality_score = rag_result.get("quality_score", 0.0)
            conversation_context_used = rag_result.get("conversation_context_used", False)
            
            # Prepare basic message data that should always work
            assistant_message_data = {
                "conversation_id": str(message.conversation_id),
                "role": "assistant",
                "content": rag_result["response"],
                "created_at": datetime.now(dt.UTC).isoformat()
            }
            
            # Prepare enhanced metadata
            enhanced_metadata = {
                "rag_used": response_metadata["rag_used"],
                "fallback_used": response_metadata["fallback_used"],
                "chunks_used": chunks_used,
                "processing_time": response_metadata["processing_time"],
                "user_role": user_role,
                "college_id": college_id,
                "quality_score": quality_score,
                "conversation_context_used": conversation_context_used,
                "source_details": source_details  # Enhanced source information
            }
            
            # Try to store with all enhanced fields, gracefully handle missing columns
            attempts = [
                # Attempt 1: Full enhanced message with sources and metadata
                {**assistant_message_data, "sources": sources_data, "metadata": enhanced_metadata},
                # Attempt 2: With sources but no metadata
                {**assistant_message_data, "sources": sources_data},
                # Attempt 3: With metadata but no sources
                {**assistant_message_data, "metadata": enhanced_metadata},
                # Attempt 4: Basic message only
                assistant_message_data
            ]
            
            assistant_message_response = None
            last_error = None
            
            for i, attempt_data in enumerate(attempts):
                try:
                    assistant_message_response = client.table("messages").insert(attempt_data).execute()
                    if assistant_message_response.data:
                        if i > 0:
                            logger.warning(f"Message stored using fallback attempt {i+1} (some columns may be missing from database)")
                        break
                except Exception as attempt_error:
                    last_error = attempt_error
                    if i < len(attempts) - 1:  # Not the last attempt
                        error_msg = str(attempt_error).lower()
                        if "column" in error_msg or "metadata" in error_msg or "sources" in error_msg:
                            logger.debug(f"Attempt {i+1} failed due to missing column, trying next approach")
                            continue
                    # If it's not a column issue or it's the last attempt, don't continue
                    break
            
            if not assistant_message_response or not assistant_message_response.data:
                raise Exception(f"Failed to store assistant message after all attempts. Last error: {str(last_error)}")
                
            logger.info(f"Stored assistant response in conversation {message.conversation_id} (sources: {len(sources_data)}, chunks: {chunks_used}, quality: {quality_score:.2f})")
            
        except Exception as e:
            logger.error(f"Error storing assistant message: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to store response")

        # 6. Enhanced response formatting with comprehensive metadata
        response_data = {
            "status": "success",
            "message": "Message processed successfully",
            "role": "assistant",
            "content": rag_result["response"],
            "sources": sources_data,
            "conversation_id": str(message.conversation_id),
            "metadata": {
                "chunks_used": chunks_used,
                "rag_enabled": response_metadata["rag_used"],
                "fallback_used": response_metadata["fallback_used"],
                "processing_time_ms": round(response_metadata["processing_time"] * 1000, 2),
                "response_type": "rag" if response_metadata["rag_used"] and not response_metadata["fallback_used"] else "fallback",
                "college_id": college_id,
                "timestamp": datetime.now(dt.UTC).isoformat(),
                "quality_score": quality_score,
                "conversation_context_used": conversation_context_used,
                "source_details": source_details  # Enhanced source information with similarity scores
            }
        }
        
        # Add error details to response if available (for debugging)
        if response_metadata["error_details"] and logger.level <= logging.DEBUG:
            response_data["debug"] = {
                "error_details": response_metadata["error_details"]
            }
        
        logger.info(f"Chat response completed for user {message.user_id}: {response_data['metadata']['response_type']} response with {chunks_used} chunks (quality: {quality_score:.2f})")
        
        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing chat message for user {message.user_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail={
                "error": "Internal server error",
                "message": "An unexpected error occurred while processing your message",
                "timestamp": datetime.now(dt.UTC).isoformat()
            }
        )

@app.get("/config/status")
async def get_config_status(current_user: dict = Depends(get_current_user)):
    """
    Get configuration status and summary (admin only).
    
    Returns configuration validation status and non-sensitive configuration summary.
    """
    # Only allow super_admin to view configuration status
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Not authorized to view configuration status")
    
    try:
        from app.core.config import get_config_manager
        
        config_manager = get_config_manager()
        summary = config_manager.get_config_summary()
        
        return {
            "status": "success",
            "configuration_status": summary["status"],
            "validation_errors": summary.get("validation_errors", []),
            "config_summary": summary.get("config", {}),
            "timestamp": datetime.now(dt.UTC).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get configuration status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve configuration status")

@app.post("/config/validate")
async def validate_config(current_user: dict = Depends(get_current_user)):
    """
    Validate current configuration (admin only).
    
    Returns detailed validation results for troubleshooting.
    """
    # Only allow super_admin to validate configuration
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Not authorized to validate configuration")
    
    try:
        from app.core.config import get_config_manager
        
        config_manager = get_config_manager()
        validation_errors = config_manager.validate_current_config()
        
        return {
            "status": "success",
            "is_valid": len(validation_errors) == 0,
            "validation_errors": validation_errors,
            "error_count": len(validation_errors),
            "timestamp": datetime.now(dt.UTC).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to validate configuration: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to validate configuration")

@app.get("/system/health")
async def get_system_health(current_user: dict = Depends(get_current_user)):
    """
    Get comprehensive system health status including RAG services.
    
    Returns detailed health information for monitoring and troubleshooting.
    """
    # Allow both super_admin and college_admin to view system health
    if current_user["role"] not in ["super_admin", "college_admin"]:
        raise HTTPException(status_code=403, detail="Not authorized to view system health")
    
    try:
        from app.core.rag import get_rag_system_health
        
        health_status = await get_rag_system_health()
        
        return {
            "status": "success",
            "system_health": health_status,
            "timestamp": datetime.now(dt.UTC).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get system health: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system health")

@app.post("/system/health/reset")
async def reset_system_health(
    service_name: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Reset health status for services (admin only).
    
    Useful for clearing circuit breaker states and resetting failure counters.
    """
    # Only allow super_admin to reset system health
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Not authorized to reset system health")
    
    try:
        from app.core.rag import reset_service_health
        
        result = await reset_service_health(service_name)
        
        return {
            "status": "success",
            "reset_result": result,
            "timestamp": datetime.now(dt.UTC).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to reset system health: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to reset system health")


@app.post("/guest-chat")
async def guest_chat(request: GuestChatRequest):
    """
    Anonymous chat endpoint.
    - Does NOT require authentication
    - Does NOT store history per user
    - Uses selected college_id or defaults to first available college
    """
    try:
        client = get_service_client()

        # Use provided college_id or pick the first available college as default
        college_id = None
        if request.college_id:
            # Validate the provided college_id
            college_check = client.table("colleges").select("id").eq("id", request.college_id).limit(1).execute()
            if college_check.data:
                college_id = request.college_id
        
        if not college_id:
            # Pick the first available college as the default context
            colleges_resp = client.table("colleges").select("id").limit(1).execute()
            colleges = getattr(colleges_resp, "data", None) or colleges_resp.data
            if not colleges:
                return {
                    "content": "The system is not fully configured yet (no colleges found). Please contact the administrator.",
                    "sources": [],
                }
            college_id = colleges[0]["id"]

        rag_result = await generate_basic_response(
            query=request.content,
            college_id=college_id,
        )

        return {
            "content": rag_result.get("response", ""),
            "sources": rag_result.get("sources", []),
        }
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Guest chat failed: {str(e)}")

@app.get("/chat/history/")
async def get_chat_history(user_id: UUID):
    """Get list of conversations for a user."""
    try:
        conv_response = supabase.table("conversations").select("id, title, created_at, updated_at, college_id").eq("user_id", str(user_id)).order("created_at", desc=True).execute()
        return conv_response.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/chat/conversation/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get all messages for a specific conversation."""
    try:
        user_id = current_user["user_id"]
        client = get_service_client()
        
        # Verify user owns this conversation
        conv_check = client.table("conversations").select("user_id").eq("id", str(conversation_id)).execute()
        if not conv_check.data:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        if conv_check.data[0]["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to access this conversation")
        
        # Get messages for this conversation
        messages_response = (
            client.table("messages")
            .select("id, role, content, created_at, metadata")
            .eq("conversation_id", str(conversation_id))
            .order("created_at")
            .execute()
        )
        
        return {
            "conversation_id": str(conversation_id),
            "messages": messages_response.data or []
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation messages: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get conversation messages: {str(e)}")

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
                        async with httpx.AsyncClient(trust_env=False) as http_client:
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
            "ApiKey": service_key,
            "Content-Type": file.content_type,
            "x-upsert": "true" 
        }

        max_upload_attempts = 3
        last_upload_error = None
        upload_succeeded = False

        for attempt in range(1, max_upload_attempts + 1):
            try:
                async with httpx.AsyncClient(trust_env=False) as http_client:
                    r = await http_client.post(storage_url, content=file_content, headers=headers, timeout=60.0)

                if r.status_code in [200, 201]:
                    file_id = path  # Store path for cleanup if needed
                    upload_succeeded = True
                    break

                retryable_status_codes = {500, 502, 503, 504, 520, 522, 524}
                if r.status_code in retryable_status_codes and attempt < max_upload_attempts:
                    await asyncio.sleep(0.5 * attempt)
                    continue

                raise HTTPException(status_code=400, detail=f"File upload failed: {r.text}")

            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as upload_error:
                last_upload_error = upload_error
                if attempt < max_upload_attempts:
                    await asyncio.sleep(0.5 * attempt)
                    continue

            except HTTPException:
                raise

            except Exception as upload_error:
                last_upload_error = upload_error
                if attempt < max_upload_attempts:
                    await asyncio.sleep(0.5 * attempt)
                    continue

        if not upload_succeeded:
            logger.error(f"Storage upload failed after retries for path {path}: {last_upload_error}")
            raise HTTPException(
                status_code=502,
                detail="Could not connect to Supabase Storage. Please retry in a few seconds."
            )

        # Map content_type to expected DB enum/check if needed
        mime_to_type = {
            "application/pdf": "pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
            "text/plain": "txt"
        }
        file_type_val = mime_to_type.get(file.content_type, "other")

        # Insert metadata to DB with enhanced tracking and RAG processing integration
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
            "process_schedule": "immediate",  # Default to immediate processing after approval
            "upload_metadata": {
                "original_filename": original_filename,
                "content_type": file.content_type,
                "upload_timestamp": datetime.now(dt.UTC).isoformat(),
                "uploaded_by": current_user["user_id"],
                "rag_processing_enabled": True  # Flag to indicate RAG processing should be triggered
            }
        }

        # Use direct HTTP for DB Insert to ensure Service Key is used
        db_url = f"{SUPABASE_URL}/rest/v1/documents"
        db_headers = {
            "Authorization": f"Bearer {service_key}",
            "ApiKey": service_key,
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        async with httpx.AsyncClient(trust_env=False) as http_client:
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
                    async with httpx.AsyncClient(trust_env=False) as http_client:
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
        
        # Execute document query with enhanced RAG processing information
        documents_response = query.execute()
        documents = documents_response.data
        
        # Enhance documents with RAG processing status and progress indicators
        enhanced_documents = []
        for doc in documents:
            # Get chunk count for completed documents to show RAG readiness
            chunk_count = 0
            rag_ready = False
            processing_progress = None
            
            if doc.get("status") == "completed":
                try:
                    # Get chunk count for this document
                    chunk_query = client.table("document_chunks").select("id", count="exact").eq("document_id", doc["id"])
                    chunk_response = chunk_query.execute()
                    chunk_count = chunk_response.count if hasattr(chunk_response, 'count') else len(chunk_response.data or [])
                    rag_ready = chunk_count > 0
                except Exception as chunk_error:
                    logger.warning(f"Failed to get chunk count for document {doc['id']}: {str(chunk_error)}")
            
            # Extract processing progress from metadata if available
            processing_metadata = doc.get("processing_metadata", {})
            if doc.get("status") == "processing" and processing_metadata:
                processing_progress = {
                    "started_at": processing_metadata.get("start_time"),
                    "triggered_by": processing_metadata.get("triggered_by"),
                    "processing_type": processing_metadata.get("processing_type"),
                    "estimated_completion": None  # Could be calculated based on file size
                }
            
            # Create enhanced document object
            enhanced_doc = {
                **doc,
                "rag_status": {
                    "is_rag_ready": rag_ready,
                    "chunk_count": chunk_count,
                    "processing_progress": processing_progress,
                    "can_be_queried": rag_ready and doc.get("status") == "completed"
                }
            }
            enhanced_documents.append(enhanced_doc)
        
        documents = enhanced_documents
        
        # Calculate real-time statistics from database
        stats_query = client.table("documents").select("status").eq("college_id", target_college_id)
        stats_response = stats_query.execute()
        
        # Calculate statistics with RAG processing metrics
        statistics = {
            "total": 0,
            "uploaded": 0,
            "pending_approval": 0,
            "approved": 0,
            "rejected": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
            "rag_ready": 0,  # Documents that are completed and have chunks
            "processing_queue": 0  # Documents in processing state
        }
        
        for doc in stats_response.data:
            doc_status = doc.get("status", "unknown")
            statistics["total"] += 1
            if doc_status in statistics:
                statistics[doc_status] += 1
            
            # Count processing queue
            if doc_status == "processing":
                statistics["processing_queue"] += 1
        
        # Get RAG-ready count (completed documents with chunks)
        try:
            rag_ready_query = client.rpc("get_vector_storage_stats", {"target_college_id": target_college_id})
            rag_stats_response = rag_ready_query.execute()
            if rag_stats_response.data:
                rag_stats = rag_stats_response.data[0]
                statistics["rag_ready"] = rag_stats.get("completed_documents", 0)
        except Exception as rag_stats_error:
            logger.warning(f"Failed to get RAG statistics: {str(rag_stats_error)}")
            # Fallback: count completed documents as potentially RAG-ready
            statistics["rag_ready"] = statistics["completed"]
        
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
        
        retryable_status_codes = {500, 502, 503, 504, 520, 522, 524}
        max_attempts = 3
        r_db = None
        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(trust_env=False) as http_client:
                    r_db = await http_client.patch(db_url, json=update_data, headers=db_headers, timeout=20.0)

                if r_db.status_code in [200, 201]:
                    break

                if r_db.status_code in retryable_status_codes and attempt < max_attempts:
                    await asyncio.sleep(0.5 * attempt)
                    continue

                raise HTTPException(status_code=500, detail=f"Database update error: {r_db.text}")

            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as db_error:
                if attempt < max_attempts:
                    await asyncio.sleep(0.5 * attempt)
                    continue
                logger.error(f"Approve document DB connection failed after retries: {db_error}")
                raise HTTPException(
                    status_code=502,
                    detail="Could not connect to Supabase while approving document. Please retry."
                )

        updated_doc = r_db.json() if r_db else []
        
        # Record the approval in document_approvals table
        approval_data = {
            "document_id": str(request.document_id),
            "approved_by": current_user["user_id"],
            "action": "approved",
            "comments": request.comments
        }
        
        approval_url = f"{SUPABASE_URL}/rest/v1/document_approvals"
        try:
            async with httpx.AsyncClient(trust_env=False) as http_client:
                r_approval = await http_client.post(approval_url, json=approval_data, headers=db_headers, timeout=20.0)
                if r_approval.status_code not in [200, 201]:
                    # Log but don't fail the approval if approval record creation fails
                    print(f"Warning: Failed to create approval record: {r_approval.text}")
        except Exception as approval_record_error:
            print(f"Warning: Failed to create approval record: {approval_record_error}")
        
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
        
        # Enhanced RAG processing trigger with better error handling and status tracking
        if request.process_schedule == 'immediate':
            from app.core.rag import trigger_rag_processing
            
            # Log RAG processing initiation
            logger.info(f"Triggering immediate RAG processing for document {request.document_id} ({document['filename']})")
            
            # Add RAG processing task with enhanced error handling
            background_tasks.add_task(
                _trigger_rag_processing_with_status_tracking,
                str(request.document_id),
                document['filename'],
                current_user["user_id"]
            )
        
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
        
        retryable_status_codes = {500, 502, 503, 504, 520, 522, 524}
        max_attempts = 3
        r_db = None
        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(trust_env=False) as http_client:
                    r_db = await http_client.patch(db_url, json=update_data, headers=db_headers, timeout=20.0)

                if r_db.status_code in [200, 201]:
                    break

                if r_db.status_code in retryable_status_codes and attempt < max_attempts:
                    await asyncio.sleep(0.5 * attempt)
                    continue

                raise HTTPException(status_code=500, detail=f"Database update error: {r_db.text}")

            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as db_error:
                if attempt < max_attempts:
                    await asyncio.sleep(0.5 * attempt)
                    continue
                logger.error(f"Reject document DB connection failed after retries: {db_error}")
                raise HTTPException(
                    status_code=502,
                    detail="Could not connect to Supabase while rejecting document. Please retry."
                )

        updated_doc = r_db.json() if r_db else []
        
        # Record the rejection in document_approvals table
        approval_data = {
            "document_id": str(request.document_id),
            "approved_by": current_user["user_id"],
            "action": "rejected",
            "comments": request.reason
        }
        
        approval_url = f"{SUPABASE_URL}/rest/v1/document_approvals"
        try:
            async with httpx.AsyncClient(trust_env=False) as http_client:
                r_approval = await http_client.post(approval_url, json=approval_data, headers=db_headers, timeout=20.0)
                if r_approval.status_code not in [200, 201]:
                    # Log but don't fail the rejection if approval record creation fails
                    print(f"Warning: Failed to create rejection record: {r_approval.text}")
        except Exception as rejection_record_error:
            print(f"Warning: Failed to create rejection record: {rejection_record_error}")
        
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
        
        retryable_status_codes = {500, 502, 503, 504, 520, 522, 524}
        max_attempts = 3
        r_db = None
        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(trust_env=False) as http_client:
                    r_db = await http_client.patch(db_url, json=update_data, headers=db_headers, timeout=20.0)

                if r_db.status_code in [200, 201]:
                    break

                if r_db.status_code in retryable_status_codes and attempt < max_attempts:
                    await asyncio.sleep(0.5 * attempt)
                    continue

                raise HTTPException(status_code=500, detail=f"Database update error: {r_db.text}")

            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as db_error:
                if attempt < max_attempts:
                    await asyncio.sleep(0.5 * attempt)
                    continue
                logger.error(f"Schedule processing DB connection failed after retries: {db_error}")
                raise HTTPException(
                    status_code=502,
                    detail="Could not connect to Supabase while scheduling processing. Please retry."
                )

        updated_doc = r_db.json() if r_db else []
        
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
        # Include additional fields (code, description, logo_url, is_active)
        query = client.table("colleges").select("id, name, code, domain, description, logo_url, is_active, created_at")

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
                    "code": college.get("code"),
                    "domain": college.get("domain"),
                    "description": college.get("description"),
                    "admin_count": admin_count,
                }
            )

        return {"colleges": result}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to retrieve colleges: {str(e)}")


@app.post("/superadmin/colleges")
async def create_superadmin_college(
    request: CollegeCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a new college."""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Not authorized to create colleges")

    try:
        client = get_service_client()
        data = request.dict()

        # Normalize optional string fields
        for key in ["domain", "description", "logo_url"]:
            if data.get(key) is not None:
                data[key] = data[key].strip() or None

        resp = client.table("colleges").insert(data).execute()
        college = (resp.data or [None])[0]
        if not college:
            raise HTTPException(status_code=500, detail="Failed to create college")

        return {
            "id": college["id"],
            "name": college["name"],
            "code": college.get("code"),
            "domain": college.get("domain"),
            "description": college.get("description"),
            "logo_url": college.get("logo_url"),
            "is_active": college.get("is_active", True),
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        msg = str(e)
        # Map common uniqueness violations to user-friendly 400 errors
        if "colleges_name_key" in msg:
            raise HTTPException(status_code=400, detail="A college with this name already exists")
        if "colleges_code_key" in msg:
            raise HTTPException(status_code=400, detail="A college with this code already exists")
        if "colleges_domain_key" in msg:
            raise HTTPException(status_code=400, detail="A college with this domain already exists")
        raise HTTPException(status_code=500, detail=f"Failed to create college: {msg}")


@app.put("/superadmin/colleges/{college_id}")
async def update_superadmin_college(
    college_id: str,
    request: CollegeUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update an existing college."""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Not authorized to update colleges")

    try:
        client = get_service_client()
        updates = {k: v for k, v in request.dict().items() if v is not None}

        # Normalize optional string fields
        for key in ["domain", "description", "logo_url"]:
            if key in updates:
                updates[key] = updates[key].strip() or None

        if not updates:
            return {"status": "no_changes"}

        resp = client.table("colleges").update(updates).eq("id", college_id).execute()
        if not resp.data:
            raise HTTPException(status_code=404, detail="College not found")

        return {"status": "success"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        msg = str(e)
        if "colleges_name_key" in msg:
            raise HTTPException(status_code=400, detail="A college with this name already exists")
        if "colleges_code_key" in msg:
            raise HTTPException(status_code=400, detail="A college with this code already exists")
        if "colleges_domain_key" in msg:
            raise HTTPException(status_code=400, detail="A college with this domain already exists")
        raise HTTPException(status_code=500, detail=f"Failed to update college: {msg}")


@app.delete("/superadmin/colleges/{college_id}")
async def delete_superadmin_college(
    college_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a college. Related profiles/documents may block deletion via FKs."""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Not authorized to delete colleges")

    try:
        client = get_service_client()
        resp = client.table("colleges").delete().eq("id", college_id).execute()
        if not resp.data:
            raise HTTPException(status_code=404, detail="College not found")
        return {"status": "success"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        msg = str(e)
        raise HTTPException(status_code=500, detail=f"Failed to delete college: {msg}")


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


@app.post("/superadmin/admins")
async def create_superadmin_admin(
    request: AdminCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a new college admin user (auth user + profile)."""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Not authorized to create admins")

    try:
        client = get_service_client()

        # Create auth user using service role
        try:
            auth_resp = client.auth.admin.create_user(
                {
                    "email": request.email,
                    "password": request.password,
                    "email_confirm": True,
                }
            )
            # Extract user from response (handle different response formats)
            user = getattr(auth_resp, "user", None) or getattr(auth_resp, "data", {}).get("user")
            if not user:
                raise HTTPException(status_code=500, detail="Failed to create auth user")
            
            # Get user ID from the created user
            raw_user_id = getattr(user, "id", None)
            if raw_user_id is None and isinstance(user, dict):
                raw_user_id = user.get("id")
            if raw_user_id is None:
                raise HTTPException(status_code=500, detail="Auth user record is missing an id")
            user_id = str(raw_user_id)
        except HTTPException:
            raise
        except Exception as e:
            msg = str(e)
            duplicate_markers = [
                "User already registered",
                "email_already_in_use",
                "A user with this email address has already been registered",
            ]
            # If this is a duplicate-email error, return a clear error
            if any(marker in msg for marker in duplicate_markers):
                raise HTTPException(status_code=400, detail="An account with this email already exists")
            # For other errors, re-raise
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Failed to create auth user: {str(e)}")

        # Create or update profile row for this auth user (for role/college mapping)
        profile_data = {
            "id": user_id,
            "full_name": request.name,
            "role": "college_admin",
            "college_id": request.college_id,
        }
        client.table("profiles").upsert(profile_data).execute()

        # Your Supabase schema has public.admins.user_id -> public.users.id (NOT auth.users.id).
        # To satisfy that FK, ensure a row exists in public.users for this auth user id.
        # This assumes your public.users table has at least: id (uuid) and email (text, nullable or present).
        try:
            client.table("users").upsert(
                {"id": user_id, "email": request.email},
                on_conflict="id",
            ).execute()
        except Exception:
            # If the project doesn't have public.users (or columns differ), don't block admin creation
            # via profiles; but admins table sync below may still fail if FK is strict.
            pass

        # Also ensure an entry exists in the public.admins table that matches
        # your schema (user_id, college_id, is_super_admin, etc.). We use
        # upsert on (user_id, college_id) so this is idempotent.
        try:
            admin_row = {
                "user_id": user_id,
                "college_id": request.college_id,
                "is_super_admin": False,
            }
            client.table("admins").upsert(admin_row, on_conflict="user_id,college_id").execute()
        except Exception as admin_err:
            import traceback
            traceback.print_exc()
            # Most common: FK violation (public.users row missing) or duplicate (unique constraint)
            raise HTTPException(status_code=400, detail=f"Failed to create admin record: {str(admin_err)}")

        return {
            "id": user_id,
            "name": request.name,
            "email": request.email,
            "college_id": request.college_id,
            "status": "active",
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create admin: {str(e)}")


@app.put("/superadmin/admins/{admin_id}")
async def update_superadmin_admin(
    admin_id: str,
    request: AdminUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update an existing college admin's profile details."""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Not authorized to update admins")

    try:
        client = get_service_client()

        updates = {}
        if request.name is not None:
            updates["full_name"] = request.name
        if request.college_id is not None:
            updates["college_id"] = request.college_id

        if updates:
            client.table("profiles").update(updates).eq("id", admin_id).execute()

        # Note: Updating email in profiles doesn't change Supabase auth email; that
        # can be added later if needed.

        return {"status": "success"}
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to update admin: {str(e)}")


@app.delete("/superadmin/admins/{admin_id}")
async def delete_superadmin_admin(
    admin_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a college admin (profile and auth user)."""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Not authorized to delete admins")

    try:
        client = get_service_client()

        # Delete profile first
        client.table("profiles").delete().eq("id", admin_id).execute()

        # Best-effort delete of auth user; ignore failures here
        try:
            client.auth.admin.delete_user(admin_id)
        except Exception:
            pass

        return {"status": "success"}
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to delete admin: {str(e)}")


@app.patch("/superadmin/admins/{admin_id}/toggle-status")
async def toggle_superadmin_admin_status(
    admin_id: str,
    request: AdminStatusUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Toggle admin status. For now this simply stores a status field in profiles
    without enforcing any additional rules.
    """
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Not authorized to update admin status")

    try:
        client = get_service_client()
        client.table("profiles").update({"status": request.status}).eq("id", admin_id).execute()
        return {"status": "success"}
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to update admin status: {str(e)}")


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
