from fastapi import FastAPI
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv() # Load your environment variables

app = FastAPI()

class ChatMessage(BaseModel):
    conversation_id: UUID 
    role: str
    content: str
    # We make this optional so the Database can set the default time
    created_at: Optional[datetime] = None

chat_history=[]

@app.post("/chat/")
async def create_chat(message: ChatMessage):
    try:
        # 1. Connect
        conn = psycopg2.connect(
            user=os.getenv("user"),
            password=os.getenv("password"),
            host=os.getenv("host"),
            port=os.getenv("port"),
            dbname=os.getenv("dbname")
        )
        cursor = conn.cursor()

        # 2. The SQL Query
        query = "INSERT INTO messages (conversation_id, role, content) VALUES (%s, %s, %s)"

        # 3. Execute with Data (We need to fill this in!)
        cursor.execute(query, (str(message.conversation_id), message.role, message.content))
        
        # 4. Save and Close
        conn.commit()
        cursor.close()
        conn.close()

        return {"status": "Message sent", "data": message}

    except Exception as e:
        return {"error": str(e)}
    
    # chat_history.append(message)
    # bot_message = ChatMessage(user_id=-1, sender="bot", text="Hello! How can I assist you today?")
    # #//static data of bot#
    # chat_history.append(bot_message)
    # return {"User_message": message, "Bot_message": bot_message}


@app.get("/chat_history/")
async def get_chat_history():
    return chat_history

@app.get("/")
async def root():
    return {"message": "Welcome to Our Application!"}

@app.get("/student/{student_id}")
async def get_student(student_id: int):
    return {"student_id": student_id, "name": "John Doe", "age": 21,"Query":"Sample Query"}
