import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

# We use the direct host but enforce SSL, which is required by Supabase
DATABASE_URL = "postgresql://postgres:jhZgmOuF0SInOFbw@db.abzhedhtfognzzbuizfh.supabase.co:5432/postgres?sslmode=require"

def test_conn():
    print(f"Connecting to {DATABASE_URL[:40]}...")
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
        print("✅ Connected!")
        cur = conn.cursor()
        cur.execute("SELECT version();")
        print(f"Version: {cur.fetchone()}")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    test_conn()
