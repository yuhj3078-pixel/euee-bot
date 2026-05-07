import httpx
import os

url = "https://abzhedhtfognzzbuizfh.supabase.co/rest/v1/"
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}"
}

try:
    response = httpx.get(url, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Body: {response.text[:200]}")
except Exception as e:
    print(f"Error: {e}")
