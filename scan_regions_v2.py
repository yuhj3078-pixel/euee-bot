import psycopg2
import os

regions = [
    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
    "eu-central-1", "eu-west-1", "eu-west-2", "eu-west-3",
    "ap-southeast-1", "ap-southeast-2", "ap-northeast-1", "ap-northeast-2", "ap-south-1",
    "sa-east-1", "ca-central-1"
]

ref = "abzhedhtfognzzbuizfh"
pw = "jhZgmOuF0SInOFbw"

found = False
for region in regions:
    host = f"aws-0-{region}.pooler.supabase.com"
    url = f"postgresql://postgres.{ref}:{pw}@{host}:6543/postgres"
    print(f"Checking {region}...")
    try:
        conn = psycopg2.connect(url, connect_timeout=2)
        print(f"MATCH FOUND: {region}")
        found = True
        conn.close()
        # Write to a file for the agent to read
        with open("found_region.txt", "w") as f:
            f.write(url)
        break
    except Exception:
        pass

if not found:
    print("No region matched.")
