import os
from supabase import create_client, Client
from dotenv import load_dotenv
from pathlib import Path
import httpx

# Load environment variables from .env file in the backend directory
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Support both lowercase and uppercase env var names for Supabase
url: str = os.getenv("supabase_url") or os.getenv("SUPABASE_URL")
key: str = os.getenv("supabase_key") or os.getenv("SUPABASE_KEY")
service_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    raise ValueError("Supabase credentials not found in environment. Expected SUPABASE_URL/SUPABASE_KEY or supabase_url/supabase_key.")

# Set a longer timeout for large file uploads
timeout = httpx.Timeout(60.0, connect=10.0)

# Initialize Supabase client without deprecated ClientOptions
supabase: Client = create_client(url, key) if url and key else None

def get_service_client() -> Client:
    if url and service_key:
        return create_client(url, service_key)
    return supabase
