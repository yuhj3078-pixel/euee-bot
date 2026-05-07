import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")

supabase = create_client(url, key)

try:
    # Try a simple select to see what columns we get
    resp = supabase.table("payment_attempts").select("*").limit(0).execute()
    print("SUCCESS: payment_attempts table exists")
    # We can't easily get columns from an empty select result in the client sometimes,
    # but let's try to insert a row and see if it fails.
    test_data = {
        "tx_id": "TEST_ID_123",
        "telegram_id": 12345,
        "username": "test_user",
        "plan_requested": "pro_monthly",
        "status": "PENDING"
    }
    resp = supabase.table("payment_attempts").insert(test_data).execute()
    print("SUCCESS: Inserted test row")
    # Clean up
    supabase.table("payment_attempts").delete().eq("tx_id", "TEST_ID_123").execute()
    print("SUCCESS: Deleted test row")
except Exception as e:
    print(f"ERROR: {e}")
