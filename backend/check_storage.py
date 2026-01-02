import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url = os.getenv('supabase_url')
key = os.getenv('supabase_key')
service_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

if service_key:
    print("Using Service Role Key...")
    supabase: Client = create_client(url, service_key)
else:
    print("Using Anon Key...")
    supabase: Client = create_client(url, key)

def check_storage():
    try:
        print("Checking Storage Buckets...")
        buckets = supabase.storage.list_buckets()
        bucket_names = [b.name for b in buckets]
        print(f"Existing buckets: {bucket_names}")

        if "documents" not in bucket_names:
            print("Bucket 'documents' NOT found. Attempting to create...")
            try:
                supabase.storage.create_bucket("documents", options={"public": False})
                print("Bucket 'documents' created successfully.")
            except Exception as e:
                print(f"Failed to create bucket: {e}")
                return
        else:
            print("Bucket 'documents' exists.")

        # Test Upload
        print("\nTesting Upload...")
        try:
            res = supabase.storage.from_("documents").upload("test_check.txt", b"Hello World", {"content-type": "text/plain"})
            print(f"Upload successful: {res}")
            
            # Cleanup
            supabase.storage.from_("documents").remove(["test_check.txt"])
            print("Test file removed.")
            
        except Exception as e:
            print(f"Upload FAILED: {e}")
            print("Possible causes: RLS policies, Storage quotas, or invalid permissions.")

    except Exception as e:
        print(f"General Error: {e}")

if __name__ == "__main__":
    check_storage()
