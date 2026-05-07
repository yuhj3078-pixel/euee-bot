import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def test_conn():
    print(f"Connecting to {DATABASE_URL[:20]}...")
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
