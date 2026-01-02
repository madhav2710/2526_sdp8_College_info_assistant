import requests
import json

BASE_URL = "http://localhost:8000"
EMAIL = "admin@test.edu"
PASSWORD = "password123"

def test_flow():
    print(f"Testing login for {EMAIL}...")
    try:
        # 1. Login
        resp = requests.post(f"{BASE_URL}/auth/login", json={"email": EMAIL, "password": PASSWORD})
        if resp.status_code != 200:
            print(f"Login FAILED: {resp.status_code} - {resp.text}")
            return
        
        data = resp.json()
        token = data["access_token"]
        print("Login SUCCESS. Token received.")
        
        # 2. Get Documents
        headers = {"Authorization": f"Bearer {token}"}
        print("Testing GET /admin/documents...")
        resp = requests.get(f"{BASE_URL}/admin/documents", headers=headers)
        
        if resp.status_code == 200:
            print(f"GET /admin/documents SUCCESS. Found {len(resp.json())} docs.")
        else:
            print(f"GET /admin/documents FAILED: {resp.status_code} - {resp.text}")

    except Exception as e:
        print(f"Test Exception: {e}")

if __name__ == "__main__":
    test_flow()
