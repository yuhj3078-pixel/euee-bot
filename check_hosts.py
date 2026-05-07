import socket

hosts = [
    "db.abzhedhtfognzzbuizfh.supabase.co",
    "abzhedhtfognzzbuizfh.supabase.co",
    "aws-0-us-east-1.pooler.supabase.com",
    "aws-0-eu-central-1.pooler.supabase.com",
]

for host in hosts:
    try:
        ip = socket.gethostbyname(host)
        print(f"✅ {host} -> {ip}")
    except Exception as e:
        print(f"❌ {host}: {e}")
