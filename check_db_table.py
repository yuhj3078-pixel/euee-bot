import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv(
    "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY"
)

supabase = create_client(url, key)

try:
    # Try a simple select to see what columns we get
    resp = supabase.table("payment_attempts").select("*").limit(0).execute()
    print("SUCCESS: payment_attempts table exists")
    # We can't easily get columns from an empty select result in the client sometimes,
    # but let's try to insert a row and see if it fails.
    # First, let's see if we have any users to use as a foreign key
    user_resp = supabase.table("users").select("telegram_id").limit(1).execute()
    if user_resp.data:
        telegram_id = user_resp.data[0]["telegram_id"]
        print(f"Found user with telegram_id={telegram_id}, using for test insert.")
    else:
        print("WARNING: No users found in users table. Skipping insert test.")
        telegram_id = None

    if telegram_id is not None:
        test_data = {
            "tx_id": "TEST_ID_123",
            "transaction_id": "TEST_ID_123",  # Must match tx_id based on save_payment_attempt
            "telegram_id": telegram_id,
            "username": "test_user",
            "plan_requested": "pro_monthly",
            "status": "PENDING",
            "screenshot_url": "",  # Empty string as placeholder
            "amount": 100,  # Example amount
            "source": "manual_review",  # Matches what's used in handlers.py
            "currency": "ETB",  # Default currency
            # created_at and updated_at will be set automatically by database defaults/triggers
        }
        resp = supabase.table("payment_attempts").insert(test_data).execute()
        print("SUCCESS: Inserted test row")
        # Clean up
        supabase.table("payment_attempts").delete().eq("tx_id", "TEST_ID_123").execute()
        print("SUCCESS: Deleted test row")
    else:
        print("SKIPPED: Insert test due to no users found.")
except Exception as e:
    print(f"ERROR: {e}")
