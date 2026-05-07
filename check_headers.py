import httpx

url = "https://abzhedhtfognzzbuizfh.supabase.co/rest/v1/"
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

headers = {"apikey": key, "Authorization": f"Bearer {key}"}

try:
    response = httpx.get(url, headers=headers)
    print("--- Headers ---")
    for k, v in response.headers.items():
        print(f"{k}: {v}")
except Exception as e:
    print(f"Error: {e}")
