import json
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")

def load_questions():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Supabase credentials missing")
        return

    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        with open("local_questions.json", "r") as f:
            questions = json.load(f)
            
        print(f"Loading {len(questions)} questions via REST API...")
        
        # Supabase Python client supports bulk insert
        response = supabase.table("real_exam_questions").insert(questions).execute()
        
        if response.data:
            print(f"DONE: {len(response.data)} questions loaded successfully!")
        else:
            print("Warning: No data returned from insert.")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    load_questions()
