#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
execute_sql_init.py
===================
Execute SQL directly to create tables in Supabase.

Run: python execute_sql_init.py
"""

import os
import sys
from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql

# Load env
load_dotenv()

# Get connection string
DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")

print("\n" + "="*70)
print("SUPABASE TABLE INITIALIZATION")
print("="*70)

if not DATABASE_URL:
    print("\n✗ DATABASE_URL not found in .env")
    print("\n💡 Manual action needed:")
    print("   1. Go to https://app.supabase.com")
    print("   2. Select your project")
    print("   3. Go to SQL Editor → New Query")
    print("   4. Paste contents of supabase_add_tables.sql")
    print("   5. Run it")
    sys.exit(1)

try:
    print("\nConnecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    print("✓ Connected to PostgreSQL database")
    
    # Read SQL file
    sql_file = "supabase_add_tables.sql"
    if not os.path.exists(sql_file):
        print(f"\n✗ {sql_file} not found")
        sys.exit(1)
    
    with open(sql_file, 'r') as f:
        sql_content = f.read()
    
    print(f"\nExecuting SQL from {sql_file}...")
    
    # Execute SQL
    cursor.execute(sql_content)
    conn.commit()
    
    print("✓ SQL executed successfully!")
    print("\nTables created/verified:")
    
    # List created tables
    cursor.execute("""
        SELECT tablename FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename IN ('notes', 'audio_lessons', 'notes_access', 'textbook_chunks')
    """)
    
    tables = cursor.fetchall()
    for table in tables:
        print(f"  ✓ {table[0]}")
    
    cursor.close()
    conn.close()
    
    print("\n✅ Database tables are ready!")
    print("   Now run: python wire_all_to_supabase.py")

except psycopg2.Error as e:
    print(f"\n✗ Database error: {e}")
    print(f"   Error code: {e.pgcode}")
    print("\n💡 If you see FATAL errors, please run the SQL manually:")
    print("   1. Go to https://app.supabase.com/project/abzhedhtfognzzbuizfh/sql/new")
    print("   2. Paste contents of supabase_add_tables.sql")
    print("   3. Run it")
    sys.exit(1)

except Exception as e:
    print(f"\n✗ Error: {e}")
    sys.exit(1)
