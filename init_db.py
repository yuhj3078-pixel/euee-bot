import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def init_db():
    if not DATABASE_URL:
        print("❌ DATABASE_URL not found in .env")
        return

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        print("🚀 Running schema setup...")
        with open("final_supabase_schema.sql", "r") as f:
            schema_sql = f.read()
            cur.execute(schema_sql)
            
        conn.commit()
        print("✅ Database initialized successfully!")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error initializing database: {e}")

if __name__ == "__main__":
    init_db()