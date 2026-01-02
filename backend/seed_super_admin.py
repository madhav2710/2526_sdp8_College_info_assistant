import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url = os.getenv('supabase_url')
key = os.getenv('supabase_key')
service_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

# Use service key if available (Bypasses RLS), otherwise use anon key
if service_key:
    print("Using Service Role Key (Bypassing RLS)...")
    supabase: Client = create_client(url, service_key)
else:
    print("Using Anon Key (Subject to RLS)...")
    supabase: Client = create_client(url, key)

def seed():
    email = 'admin@platform.com'
    password = 'adminpassword123'
    
    print(f'Attempting to create super admin: {email}...')
    
    try:
        user_id = None
        # 1. Sign up user
        try:
            auth_response = supabase.auth.sign_up({'email': email, 'password': password})
            if auth_response.user:
                user_id = auth_response.user.id
                print(f'User created/found in Auth: {user_id}')
                
                # Check if we have a session (User is confirmed)
                if not auth_response.session and not service_key:
                    print("\n!!! WARNING: User created but NO SESSION returned. !!!")
                    print("This usually means 'Confirm Email' is enabled in Supabase.")
                    print("ACTION REQUIRED: Go to Supabase Auth -> Users and manually confirm this user.")
                    print("THEN run this script again.")
                    return

        except Exception as e:
            if 'already registered' in str(e):
                # Try to sign in to get the session/ID
                try:
                    auth_response = supabase.auth.sign_in_with_password({'email': email, 'password': password})
                    user_id = auth_response.user.id
                    print(f'User logged in. ID: {user_id}')
                except Exception as login_error:
                    print(f"\nCould not log in: {login_error}")
                    print("If the user exists but is not confirmed, you must confirm them manually in Supabase.")
                    return
            else:
                raise e

        if not user_id:
            print("Failed to resolve User ID.")
            return

        # 2. Create Profile (no college_id for super admin)
        profile_data = {
            'id': user_id,
            'full_name': 'Global Super Admin',
            'role': 'super_admin'
        }
        
        # If using anon key, we are relying on the client's current session from the login/signup above.
        supabase.table('profiles').upsert(profile_data).execute()
        print('Super Admin Profile created successfully!')
        
        print('\n--- SEED COMPLETE ---')
        print(f'Email: {email}')
        print(f'Password: {password}')

    except Exception as e:
        print(f'\nError seeding: {e}')
        if "policy" in str(e):
             print("HINT: This is an RLS error. Either disable Email Confirmation OR add SUPABASE_SERVICE_ROLE_KEY to your .env file.")

if __name__ == '__main__':
    seed()

