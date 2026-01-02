import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url = os.getenv('supabase_url')
key = os.getenv('supabase_key')
service_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

if service_key:
    supabase: Client = create_client(url, service_key)
else:
    supabase: Client = create_client(url, key)

def inspect():
    try:
        # Try to select one row to see keys
        print("Fetching one document...")
        res = supabase.table("documents").select("*").limit(1).execute()
        if res.data:
            print("Found row keys:", res.data[0].keys())
        else:
            print("No rows found. Checking error/schema...")
            
        # Try to insert a dummy with minimal fields to see what fails
        # Actually, let's just print the error if we try to select 'storage_path' specifically
        try:
            supabase.table("documents").select("storage_path").limit(1).execute()
            print("Column 'storage_path' exists.")
        except Exception as e:
            print(f"Column 'storage_path' check failed: {e}")

        try:
            supabase.table("documents").select("file_path").limit(1).execute()
            print("Column 'file_path' exists.")
        except Exception as e:
            print(f"Column 'file_path' check failed: {e}")

    except Exception as e:
        print(f"Inspection failed: {e}")

if __name__ == "__main__":
    inspect()
