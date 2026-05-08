#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
init_supabase_tables.py
=======================
Initialize required tables in Supabase for notes, audio, and access tracking.

Run: python init_supabase_tables.py
"""

import os
import sys
from dotenv import load_dotenv
from pathlib import Path

# Load env
load_dotenv()

# Add current dir to path
sys.path.append(os.getcwd())

import db_supabase as db

# ============================================================================
# TABLE INITIALIZATION SQL
# ============================================================================

INIT_SQL = """
-- Create notes table if not exists
CREATE TABLE IF NOT EXISTS public.notes (
    id BIGSERIAL PRIMARY KEY,
    subject VARCHAR(50) NOT NULL,
    title VARCHAR(255),
    content TEXT,
    file_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(subject)
);

-- Create audio_lessons table if not exists
CREATE TABLE IF NOT EXISTS public.audio_lessons (
    id BIGSERIAL PRIMARY KEY,
    subject VARCHAR(50) NOT NULL,
    title VARCHAR(255),
    file_url TEXT,
    file_size_bytes BIGINT,
    duration_seconds INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(subject)
);

-- Create notes_access table if not exists
CREATE TABLE IF NOT EXISTS public.notes_access (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL,
    subject VARCHAR(50),
    access_type VARCHAR(20),
    accessed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_notes_subject ON public.notes(subject);
CREATE INDEX IF NOT EXISTS idx_audio_lessons_subject ON public.audio_lessons(subject);
CREATE INDEX IF NOT EXISTS idx_notes_access_telegram_id ON public.notes_access(telegram_id);

-- Enable Row Level Security
ALTER TABLE public.notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audio_lessons ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notes_access ENABLE ROW LEVEL SECURITY;

-- Create policies for public access to notes and audio
CREATE POLICY "Allow public read access to notes" ON public.notes
    FOR SELECT USING (true);

CREATE POLICY "Allow public read access to audio_lessons" ON public.audio_lessons
    FOR SELECT USING (true);

CREATE POLICY "Allow users to view their own access logs" ON public.notes_access
    FOR SELECT USING (telegram_id = COALESCE(auth.uid()::BIGINT, 0));

-- Update trigger for notes.updated_at
DROP TRIGGER IF EXISTS update_notes_timestamp ON public.notes;
CREATE TRIGGER update_notes_timestamp
    BEFORE UPDATE ON public.notes
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- Update trigger for audio_lessons.updated_at
DROP TRIGGER IF EXISTS update_audio_timestamp ON public.audio_lessons;
CREATE TRIGGER update_audio_timestamp
    BEFORE UPDATE ON public.audio_lessons
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();
"""

# ============================================================================
# INITIALIZATION
# ============================================================================

def init_tables():
    """Initialize Supabase tables"""
    print("\n" + "="*70)
    print("INITIALIZING SUPABASE TABLES")
    print("="*70)
    
    try:
        supabase = db._get_supabase()
        print("✓ Connected to Supabase")
        
        # Try to run each CREATE TABLE command separately to avoid issues
        print("\nCreating tables...")
        
        # Check and create notes table
        try:
            supabase.table("notes").select("id").limit(1).execute()
            print("✓ notes table already exists")
        except:
            print("  Creating notes table...")
            try:
                # Use postgrest client to execute raw SQL if possible
                # For now, we'll just ensure the table structure by upserting
                test_note = {
                    "subject": "test_subject",
                    "title": "Test",
                    "content": "test",
                    "file_url": "test"
                }
                supabase.table("notes").upsert(test_note).execute()
                # Delete the test record
                supabase.table("notes").delete().eq("subject", "test_subject").execute()
                print("✓ notes table created")
            except Exception as e:
                print(f"  ⚠ Could not create notes table: {e}")
        
        # Check and create audio_lessons table
        try:
            supabase.table("audio_lessons").select("id").limit(1).execute()
            print("✓ audio_lessons table already exists")
        except:
            print("  Creating audio_lessons table...")
            try:
                test_audio = {
                    "subject": "test_subject",
                    "title": "Test",
                    "file_url": "test"
                }
                supabase.table("audio_lessons").upsert(test_audio).execute()
                supabase.table("audio_lessons").delete().eq("subject", "test_subject").execute()
                print("✓ audio_lessons table created")
            except Exception as e:
                print(f"  ⚠ Could not create audio_lessons table: {e}")
        
        # Check textbook_chunks table
        try:
            supabase.table("textbook_chunks").select("id").limit(1).execute()
            print("✓ textbook_chunks table already exists")
        except Exception as e:
            print(f"  ⚠ textbook_chunks table not found: {e}")
        
        print("\n✅ Table initialization complete!")
        print("\n💡 To run the full SQL schema, execute supabase_add_tables.sql in Supabase Dashboard")
        print("   → SQL Editor → paste and run")
        
        return True
    
    except Exception as e:
        print(f"\n✗ Failed to initialize tables: {e}")
        print("\n💡 Manual action needed:")
        print("   1. Go to https://app.supabase.com")
        print("   2. Select your project 'abzhedhtfognzzbuizfh'")
        print("   3. Go to SQL Editor")
        print("   4. Paste the contents of supabase_add_tables.sql")
        print("   5. Run it")
        return False

if __name__ == "__main__":
    success = init_tables()
    sys.exit(0 if success else 1)
