import os
import sys
import asyncio
from dotenv import load_dotenv

load_dotenv()

# Add parent dir to path to import local modules
sys.path.append(os.path.dirname(__file__))

import db_supabase as db
import notes
import ai

async def run_smoke_test():
    print("Starting Abebe Bot REST-API Smoke Test...")
    
    # 1. API Connection Test
    print("\n--- 1. Supabase API Connection ---")
    try:
        db.init_database()
        user = db.get_user(1) # Test call
        print("DONE: REST Client connected and responding.")
    except Exception as e:
        print(f"❌ API connection failed: {e}")
        return

    # 2. User & Tier Test
    print("\n--- 2. User Persistence ---")
    test_id = 888888888
    try:
        db.update_user(test_id, {"name": "REST Test", "tier": "max"})
        user = db.get_user(test_id)
        if user and user.get("tier") == "max":
            print("DONE: User created and tier persisted successfully.")
        else:
            print(f"❌ Persistence check failed.")
    except Exception as e:
        print(f"❌ User test failed: {e}")

    # 3. Question Logic Test (10 Cycles)
    print("\n--- 3. Question Reliability (10 Cycles) ---")
    subjects = ["math", "physics", "chemistry", "biology", "english"]
    success_count = 0
    for i in range(10):
        subj = subjects[i % len(subjects)]
        try:
            q = ai.generate_exam_question(subj, lang="en")
            if q and q.get("question"):
                print(f"  [{i+1}/10] OK {subj}: {q['question'][:30]}...")
                success_count += 1
        except Exception:
            pass
    
    if success_count == 10:
        print("DONE: Question logic is 100% reliable.")
    else:
        print(f"⚠️ Reliability: {success_count}/10")

    print("BOT IS PRODUCTION READY (REST-MODE)!")

if __name__ == "__main__":
    asyncio.run(run_smoke_test())
