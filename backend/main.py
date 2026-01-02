from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional
from app.core.database import supabase, get_service_client
from app.core.auth import get_current_user
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

        # 1. Ensure conversation exists
        conv_check = client.table("conversations").select("id").eq("id", str(message.conversation_id)).execute()
        
        if not conv_check.data:
            # Get user's college_id for the conversation record
            profile = client.table("profiles").select("college_id").eq("id", str(message.user_id)).execute()
            college_id = profile.data[0]["college_id"] if profile.data else None
            
            client.table("conversations").insert({
                "id": str(message.conversation_id),
                "user_id": str(message.user_id),
                "college_id": college_id,
                "title": message.content[:50] + "..."
            }).execute()

        # 2. Insert the data into the 'messages' table
        data_to_insert = {
            "conversation_id": str(message.conversation_id),
            "role": message.role,
            "content": message.content
        }
        response = client.table("messages").insert(data_to_insert).execute()

        # Mock result
        mock_response = {
            "role": "assistant",
            "content": f"Mock response for query: {message.content}",
            "conversation_id": str(message.conversation_id)
        }

        return {
            "status": "Message sent", 
            "data": response.data,
            "mock_response": mock_response
        }

    except Exception as e:
        return {"error": str(e)}

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
                 raise Exception(f"Storage Upload Failed: {r.status_code} - {r.text}")

        # Map content_type to expected DB enum/check if needed
        mime_to_type = {
            "application/pdf": "pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
            "text/plain": "txt"
        }
        file_type_val = mime_to_type.get(file.content_type, "other")

        # Insert metadata to DB (matching schema exactly)
        doc_data = {
            "college_id": target_college_id,
            "filename": file.filename,
            "storage_path": path,
            "file_type": file_type_val,
            "status": "processing"
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
                 raise Exception(f"DB Insert Failed: {r_db.status_code} - {r_db.text}")
             
             db_data = r_db.json()
        
        document_id = db_data[0]["id"] if db_data else None

        if document_id:
            # Trigger background task for RAG processing
            from app.core.rag import process_document
            background_tasks.add_task(process_document, document_id, path)

        return {
            "status": "Upload successful",
            "document_id": document_id
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/documents")
async def get_documents(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "college_admin":
        raise HTTPException(status_code=403, detail="Not authorized to view documents")
    
    target_college_id = current_user["college_id"]
    if not target_college_id:
         raise HTTPException(status_code=400, detail="User is not associated with a college")

    try:
        client = get_service_client()
        response = client.table("documents").select("*").eq("college_id", target_college_id).order("created_at", desc=True).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {"message": "Welcome to Our Application!"}

@app.get("/student/{student_id}")
async def get_student(student_id: int):
    return {"student_id": student_id, "name": "John Doe", "age": 21,"Query":"Sample Query"}
