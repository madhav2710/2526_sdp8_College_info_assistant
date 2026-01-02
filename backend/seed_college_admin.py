import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url = os.getenv('supabase_url')
key = os.getenv('supabase_key')
service_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

# Use service key if available to bypass RLS
if service_key:
    print("Using Service Role Key (Bypassing RLS)...")
    supabase: Client = create_client(url, service_key)
else:
    print("Using Anon Key (Subject to RLS)...")
    supabase: Client = create_client(url, key)

def seed():
    email = 'admin@test.edu'
    password = 'password123'

    print(f'Attempting to create College Admin: {email}...')

    try:
        # 1. Get or Create College
        college_data = {
            'name': 'Test University',
            'domain': 'test.edu',
            'code': 'TEST001'
        }
        # Try to find existing first
        college_res = supabase.table('colleges').select('*').eq('name', 'Test University').execute()
        
        if college_res.data:
            college_id = college_res.data[0]['id']
            print(f'Found existing college: {college_id}')
        else:
            college = supabase.table('colleges').upsert(college_data, on_conflict='name').execute()
            college_id = college.data[0]['id']
            print(f'Created new college: {college_id}')

        # 2. Sign up user
        user_id = None
        try:
            auth_response = supabase.auth.sign_up({'email': email, 'password': password})
            if auth_response.user:
                user_id = auth_response.user.id
                print(f'User created in Auth: {user_id}')
                if not auth_response.session and not service_key:
                     print("\n!!! WARNING: User created but NO SESSION returned. !!!")
                     print("This usually means 'Confirm Email' is enabled in Supabase.")
                     print("ACTION REQUIRED: Go to Supabase Auth -> Users and manually confirm this user.")
                     return
        except Exception as e:
            if 'already registered' in str(e):
                try:
                    auth_user = supabase.auth.sign_in_with_password({'email': email, 'password': password})
                    user_id = auth_user.user.id
                    print(f'User already exists, ID: {user_id}')
                except Exception as login_err:
                     print(f"Login failed: {login_err}")
                     return
            else:
                raise e

        if not user_id:
             print("Failed to resolve user ID")
             return

        # 3. Create Profile
        profile_data = {
            'id': user_id,
            'college_id': college_id,
            'full_name': 'Test College Admin',
            'role': 'college_admin'
        }
        supabase.table('profiles').upsert(profile_data).execute()
        print('College Admin Profile created/updated successfully!')

        print('\n--- SEED COMPLETE ---')
        print(f'Email: {email}')
        print(f'Password: {password}')

    except Exception as e:
        print(f'Error seeding: {e}')

if __name__ == '__main__':
    seed()
