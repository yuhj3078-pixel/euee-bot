
import os
import sys
import asyncio
from dotenv import load_dotenv
from pathlib import Path

# Load env from .env
load_dotenv(Path('.env'))

# Add current dir to path
sys.path.append(os.getcwd())

import db_supabase as db
import ai
import notes
from config import SUBJECTS

async def verify_features():
    print("Starting Real-Feature Verification...")
    
    # 1. Database Connectivity
    print("\n[1] Database Check:")
    try:
        user_count = db._get_supabase().table("users").select("count", count="exact").execute().count
        print(f"OK: Supabase connected. Total users in DB: {user_count}")
        
        # Check critical tables
        tables = ["users", "wrong_questions", "payment_attempts", "battles", "boss_fights"]
        for t in tables:
            try:
                db._get_supabase().table(t).select("count", count="exact").limit(1).execute()
                print(f"  - Table '{t}': OK Exist")
            except Exception as e:
                print(f"  - Table '{t}': Error: {str(e)[:50]}...")
    except Exception as e:
        print(f"Database check failed: {e}")

    # 2. AI Content Generation
    print("\n[2] AI Generation Check (Quiz/Practice):")
    try:
        # Test question generation for Math
        q = await asyncio.to_thread(ai.generate_exam_question, "math", lang="en")
        if q and q.get("question"):
            print(f"OK: AI Question Generation: OK (Subject: Math)")
            print(f"   Q: {q['question'][:50]}...")
        else:
            print("Error: AI Question Generation: Failed (returned empty or invalid)")
    except Exception as e:
        print(f"AI Generation check failed: {e}")

    # 3. Static Assets (Notes/Textbooks)
    print("\n[3] Static Assets Check:")
    asset_dirs = ["notes", "textbooks", "audio_lessons"]
    for d in asset_dirs:
        path = Path(d)
        if path.exists() and any(path.iterdir()):
            files = list(path.iterdir())
            print(f"OK: Folder '{d}': Found {len(files)} files (e.g., {files[0].name})")
        else:
            print(f"Warning: Folder '{d}': Empty or Missing")

    # 4. Auth & Tier Logic
    print("\n[4] Auth & Tier Logic Check:")
    try:
        test_id = 999999999
        db.update_user(test_id, {"name": "VerifyBot", "tier": "max", "subscription_active": True})
        tier = db.normalize_tier("max")
        has_boss = db.has_access(tier, "boss_fight")
        print(f"OK: Tier 'max' has 'boss_fight' access: {has_boss}")
        db._get_supabase().table("users").delete().eq("telegram_id", test_id).execute()
        print("OK: Temp test user cleaned up.")
    except Exception as e:
        print(f"Auth logic check failed: {e}")

    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    asyncio.run(verify_features())
