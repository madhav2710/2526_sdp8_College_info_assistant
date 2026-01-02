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
        print(f"Login error: {str(e)}") # Debugging
        if "Invalid login credentials" in str(e):
            raise HTTPException(status_code=401, detail="Invalid login credentials")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/chat/")
async def create_chat(message: ChatMessage):
    try:
        # Create a dictionary for Supabase
        # We convert the UUID to a string to be safe
        data_to_insert = {
            "conversation_id": str(message.conversation_id),
            "role": message.role,
            "content": message.content
        }

        # Insert the data into the 'messages' table
        response = supabase.table("messages").insert(data_to_insert).execute()

        return {"status": "Message sent", "data": response.data}

    except Exception as e:
        error_msg = str(e)
        # Provide more helpful error messages for common issues
        if "Invalid API key" in error_msg or "401" in error_msg:
            return {
                "error": "Invalid Supabase API key. Please check your .env file and ensure 'supabase_key' is set correctly.",
                "details": error_msg
            }
        return {"error": error_msg}
# 2. The Start Chat Endpoint
@app.post("/start_chat/")
async def start_chat(request: ChatRequest):
    try:
        # Prepare the data dictionary
        data_to_insert = {
            "user_id": str(request.user_id),
            "title": request.title
        }

        # Insert into Supabase
        # We use .execute() to actually run the command
        response = supabase.table("conversations").insert(data_to_insert).execute()

        return {"status": "Chat started", "data": response.data}

    except Exception as e:
        return {"error": str(e)}
    


@app.get("/chat_history/")
async def get_chat_history():
    return chat_history

@app.get("/")
async def root():
    return {"message": "Welcome to Our Application!"}

@app.get("/student/{student_id}")
async def get_student(student_id: int):
    return {"student_id": student_id, "name": "John Doe", "age": 21,"Query":"Sample Query"}