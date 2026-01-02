import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url = os.getenv('supabase_url')
key = os.getenv('supabase_key')
supabase: Client = create_client(url, key)

def seed():
    email = 'test@college.edu'
    password = 'password123'
    
    print(f'Attempting to create user: {email}...')
    
    try:
        # 1. Create College
        college_data = {'name': 'Test University', 'domain': 'college.edu'}
        college = supabase.table('colleges').upsert(college_data, on_conflict='name').execute()
        college_id = college.data[0]['id']
        print(f'College verified: {college_id}')

        # 2. Sign up user
        try:
            auth_user = supabase.auth.sign_up({'email': email, 'password': password})
            user_id = auth_user.user.id
            print(f'User created in Auth: {user_id}')
        except Exception as e:
            if 'already registered' in str(e):
                # If user exists, sign in to get ID
                auth_user = supabase.auth.sign_in_with_password({'email': email, 'password': password})
                user_id = auth_user.user.id
                print(f'User already exists, ID: {user_id}')
            else:
                raise e

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

if __name__ == '__main__':
    seed()

