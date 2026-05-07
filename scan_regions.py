import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

regions = [
    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
    "eu-central-1", "eu-west-1", "eu-west-2", "eu-west-3",
    "ap-southeast-1", "ap-southeast-2", "ap-northeast-1", "ap-northeast-2", "ap-south-1",
    "sa-east-1", "ca-central-1"
]

ref = "abzhedhtfognzzbuizfh"
pw = "jhZgmOuF0SInOFbw"

for region in regions:
    host = f"aws-0-{region}.pooler.supabase.com"
    url = f"postgresql://postgres.{ref}:{pw}@{host}:6543/postgres"
    print(f"Testing {region}...", end=" ", flush=True)
    try:
        conn = psycopg2.connect(url, connect_timeout=3)
        print("✅ FOUND!")
        conn.close()
        # Update .env
        with open(".env", "r") as f:
            lines = f.readlines()
        with open(".env", "w") as f:
            for line in lines:
                if line.startswith("DATABASE_URL="):
                    f.write(f"DATABASE_URL={url}\n")
                else:
                    f.write(line)
        break
    except Exception as e:
        if "Tenant or user not found" in str(e):
            print("❌ No")
        else:
            print(f"⚠️ {str(e)[:50]}")
