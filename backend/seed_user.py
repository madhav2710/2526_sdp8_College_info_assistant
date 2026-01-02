import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url = os.getenv('supabase_url')
key = os.getenv('supabase_key')
service_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

# Use service key if available to bypass RLS for college creation
if service_key:
    print("Using Service Role Key (Bypassing RLS)...")
    supabase: Client = create_client(url, service_key)
else:
    print("Using Anon Key (Subject to RLS)...")
    supabase: Client = create_client(url, key)

def seed():
    email = 'test@college.edu'
    password = 'password123'
    
    print(f'Attempting to create user: {email}...')
    
    try:
        # 1. Create College
        college_data = {
            'name': 'Test University', 
            'domain': 'college.edu',
            'code': 'TEST001' # Add mandatory field
        }
        college = supabase.table('colleges').upsert(college_data, on_conflict='name').execute()
        college_id = college.data[0]['id']
        print(f'College verified: {college_id}')

        # 2. Sign up user
        user_id = None
        try:
            auth_response = supabase.auth.sign_up({'email': email, 'password': password})
            if auth_response.user:
                user_id = auth_response.user.id
                print(f'User created in Auth: {user_id}')
                 # Check if we have a session (User is confirmed)
                if not auth_response.session and not service_key:
                     print("\n!!! WARNING: User created but NO SESSION returned. !!!")
                     print("This usually means 'Confirm Email' is enabled in Supabase.")
                     print("ACTION REQUIRED: Go to Supabase Auth -> Users and manually confirm this user.")
                     print("THEN run this script again.")
                     return
        except Exception as e:
            if 'already registered' in str(e):
                # If user exists, sign in to get ID
                try:
                    auth_user = supabase.auth.sign_in_with_password({'email': email, 'password': password})
                    user_id = auth_user.user.id
                    print(f'User already exists, ID: {user_id}')
                except Exception as login_err:
                     print(f"Login failed (User might be unconfirmed): {login_err}")
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
            'full_name': 'Test Student',
            'role': 'student'
        }
        supabase.table('profiles').upsert(profile_data).execute()
        print('Profile created/updated successfully!')
        
        print('\n--- SEED COMPLETE ---')
        print(f'Email: {email}')
        print(f'Password: {password}')
        print('NOTE: If Email Confirmation is enabled in Supabase, you must manually confirm this user in the Supabase Dashboard before logging in.')

    except Exception as e:
        print(f'Error seeding: {e}')
        if "policy" in str(e) and not service_key:
            print("HINT: Add SUPABASE_SERVICE_ROLE_KEY to your .env to bypass RLS for creating colleges.")

if __name__ == '__main__':
    seed()

