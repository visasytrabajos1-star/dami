import os
import psycopg2
from dotenv import load_dotenv

# Force load .env
load_dotenv()

url = os.getenv("SUPABASE_DATABASE_URL")
if not url:
    url = os.getenv("DATABASE_URL")

print(f"Testing connection to: {url}")

try:
    conn = psycopg2.connect(url)
    print("Connection SUCCESS!")
    conn.close()
except Exception as e:
    print(f"Connection FAILED: {e}")
