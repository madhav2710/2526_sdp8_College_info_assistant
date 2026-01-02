import os
from supabase import create_client, Client
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file in the backend directory
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

url: str = os.getenv("supabase_url")
key: str = os.getenv("supabase_key")
service_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    print("Warning: Supabase credentials not found in environment.")

supabase: Client = create_client(url, key) if url and key else None

def get_service_client() -> Client:
    if url and service_key:
        return create_client(url, service_key)
    return supabase # Fallback to anon key if service key missing (though ideally should fail or be handled)
