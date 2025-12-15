import psycopg2
from dotenv import load_dotenv
import os

# 1. Load the secrets from the .env file
load_dotenv()

try:
    # 2. Connect using the variables
    connection = psycopg2.connect(
        user=os.getenv("user"),
        password=os.getenv("password"),
        host=os.getenv("host"),
        port=os.getenv("port"),
        dbname=os.getenv("dbname")
    )
    print("✅ Connection successful!")
    
    # 3. Quick test query
    cursor = connection.cursor()
    cursor.execute("SELECT NOW();")
    result = cursor.fetchone()
    print("🕒 Current Database Time:", result)

    cursor.close()
    connection.close()

except Exception as e:
    print(f"❌ Failed to connect: {e}")