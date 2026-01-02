from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from typing import Optional
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file in the backend directory
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Initialize Supabase Client
# Make sure these match the keys in your .env file exactly!
url: str = os.getenv("supabase_url")
key: str = os.getenv("supabase_key")

# Validate that environment variables are set
if not url or not key:
    missing_vars = []
    if not url:
        missing_vars.append("supabase_url")
    if not key:
        missing_vars.append("supabase_key")
    raise ValueError(
        f"Missing required environment variables: {', '.join(missing_vars)}. "
        "Please create a .env file in the backend directory with these variables set."
    )

supabase: Client = create_client(url, key)

app = FastAPI()

# Allow the frontend (Vite dev server) to call this API from the browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; you can restrict this later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ChatMessage(BaseModel):
    conversation_id: UUID 
    user_id: UUID # Added for auto-creation
    role: str
    content: str
    # We make this optional so the Database can set the default time
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
        # Use Service Role Key for background/system tasks to ensure reliability
        # In a production app, we would use proper RLS and session-based client
        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        client: Client = create_client(url, service_key) if service_key else supabase

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

        # Mock result to confirm message received and stored (as per requirement)
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
        # 1. Get all conversations for this user
        conv_response = supabase.table("conversations").select("*").eq("user_id", str(user_id)).order("created_at", desc=True).execute()
        
        # 2. For each conversation, get messages (Simplified for MVP)
        # In a real app, we might just return the list of conversations
        # or have a separate endpoint for messages. 
        # For now, let's return the list of conversations.
        return conv_response.data

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/")
async def root():
    return {"message": "Welcome to Our Application!"}

@app.get("/student/{student_id}")
async def get_student(student_id: int):
    return {"student_id": student_id, "name": "John Doe", "age": 21,"Query":"Sample Query"}