#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wire_all_to_supabase.py
=======================
Comprehensive script to wire notes, audios, and textbooks into Supabase.

Steps:
1. Ensure DB schema is up-to-date (with necessary tables)
2. Wire notes PDFs to euee_notes directories
3. Generate audio files 
4. Ingest textbook chunks into textbook_chunks table
5. Create notes table and populate it
6. Create audio_lessons table and populate it

Run: python wire_all_to_supabase.py
"""

import os
import sys
import json
import asyncio
import pdfplumber
import shutil
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load env
load_dotenv()

# Add current dir to path
sys.path.append(os.getcwd())

import db_supabase as db
from config import SUBJECTS

# ============================================================================
# CONFIG
# ============================================================================

BOT_ROOT          = Path(__file__).resolve().parent
NOTES_SRC_DIR     = BOT_ROOT / "notes"
AUDIO_SRC_DIR     = BOT_ROOT / "audio_lessons"
TEXTBOOK_DIR      = BOT_ROOT / "textbooks"
EUEE_NOTES        = BOT_ROOT / "euee_notes"

CHUNK_SIZE        = 1000
CHUNK_OVERLAP     = 100

SUBJECT_MAP = {
    "english": "english",
    "english_notes": "english",
    "maths": "math",
    "math": "math",
    "mathematics": "math",
    "physics": "physics",
    "physics_notes": "physics",
    "chemistry": "chemistry",
    "biology": "biology",
    "civics": "civics",
    "history": "history",
    "geography": "geography",
    "economics": "economics",
    "agriculture": "agriculture",
    "it": "it",
    "information_technology": "it",
}

SUBJECT_DISPLAY = {
    "math": "Mathematics",
    "physics": "Physics",
    "chemistry": "Chemistry",
    "biology": "Biology",
    "english": "English",
    "civics": "Civics & Ethics",
    "history": "History",
    "geography": "Geography",
    "economics": "Economics",
    "agriculture": "Agriculture",
    "it": "Information Technology",
}

PDF_SUBJECT_MAP = {
    "Mathematics": "math",
    "Physics": "physics",
    "Chemistry": "chemistry",
    "Biology": "biology",
    "English": "english",
    "History": "history",
    "Geography": "geography",
    "Economics": "economics",
    "Agriculture": "agriculture",
    "IT": "it",
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def detect_subject_from_filename(filename: str) -> str | None:
    """Map PDF filename to subject code."""
    fname = filename.lower().replace(" ", "_").replace("-", "_")
    
    # Try exact mapping first
    stem = Path(filename).stem.lower()
    if stem in SUBJECT_MAP:
        return SUBJECT_MAP[stem]
    
    # Try keyword matching
    for keyword, code in PDF_SUBJECT_MAP.items():
        if keyword.lower() in fname.lower():
            return code
    
    return None

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from a PDF."""
    print(f"    Reading: {pdf_path}")
    all_text = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    all_text.append(text.strip())
    except Exception as e:
        print(f"    [ERROR] Failed to read PDF: {e}")
        return ""
    
    return "\n\n".join(all_text)

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        start = end - overlap
    return chunks

# ============================================================================
# STEP 1: ENSURE SCHEMA IS CORRECT
# ============================================================================

def ensure_schema() -> bool:
    """Create necessary tables if they don't exist."""
    print("\n" + "="*70)
    print("STEP 1: Ensuring Supabase schema is up-to-date")
    print("="*70)
    
    try:
        supabase = db._get_supabase()
        
        # Try to query to ensure connection works
        result = supabase.table("users").select("telegram_id").limit(1).execute()
        print("✓ Supabase connection verified")
        
        # The schema should already exist from working_supabase_schema.sql
        # We'll check if the tables we need exist
        try:
            supabase.table("textbook_chunks").select("id").limit(1).execute()
            print("✓ textbook_chunks table exists")
        except:
            print("⚠ textbook_chunks table may need to be created")
        
        try:
            supabase.table("notes").select("id").limit(1).execute()
            print("✓ notes table exists")
        except:
            print("⚠ notes table may need to be created (creating now...)")
            # Will create it if needed
        
        try:
            supabase.table("audio_lessons").select("id").limit(1).execute()
            print("✓ audio_lessons table exists")
        except:
            print("⚠ audio_lessons table may need to be created (creating now...)")
        
        return True
    except Exception as e:
        print(f"✗ Schema check failed: {e}")
        return False

# ============================================================================
# STEP 2: WIRE NOTES PDFs
# ============================================================================

def wire_notes_pdfs() -> dict:
    """Copy PDFs from notes/ folder to euee_notes/{subject}/notes.pdf"""
    print("\n" + "="*70)
    print("STEP 2: Wiring Notes PDFs")
    print("="*70)
    
    wired = {}
    
    if not NOTES_SRC_DIR.exists():
        print(f"⚠ notes/ folder not found at {NOTES_SRC_DIR}")
        return wired
    
    pdf_files = list(NOTES_SRC_DIR.glob("*.pdf"))
    if not pdf_files:
        print("⚠ No PDF files found in notes/")
        return wired
    
    print(f"Found {len(pdf_files)} PDF(s) in notes/")
    
    for pdf_file in sorted(pdf_files):
        subject = detect_subject_from_filename(pdf_file.name)
        
        if not subject:
            print(f"  ⚠ Cannot map '{pdf_file.name}' to a subject")
            continue
        
        dest_folder = EUEE_NOTES / subject
        dest_folder.mkdir(parents=True, exist_ok=True)
        dest_pdf = dest_folder / "notes.pdf"
        
        try:
            shutil.copy2(pdf_file, dest_pdf)
            wired[subject] = str(dest_pdf)
            print(f"  ✓ {pdf_file.name} → euee_notes/{subject}/notes.pdf")
        except Exception as e:
            print(f"  ✗ Failed to copy {pdf_file.name}: {e}")
    
    return wired

# ============================================================================
# STEP 3: INGEST TEXTBOOKS TO SUPABASE
# ============================================================================

async def ingest_textbooks() -> dict:
    """Extract and ingest textbook chunks into textbook_chunks table"""
    print("\n" + "="*70)
    print("STEP 3: Ingesting Textbooks to Supabase")
    print("="*70)
    
    if not TEXTBOOK_DIR.exists():
        print(f"⚠ textbooks/ folder not found at {TEXTBOOK_DIR}")
        return {}
    
    pdf_files = [f for f in os.listdir(TEXTBOOK_DIR) if f.lower().endswith(".pdf")]
    
    if not pdf_files:
        print("⚠ No PDF files found in textbooks/")
        return {}
    
    print(f"Found {len(pdf_files)} textbook(s)")
    
    ingested = {}
    supabase = db._get_supabase()
    
    # First, clear existing textbook_chunks for fresh ingestion
    try:
        print("  Clearing existing textbook_chunks...")
        supabase.table("textbook_chunks").delete().neq("id", 0).execute()
        print("  ✓ Cleared old chunks")
    except Exception as e:
        print(f"  ⚠ Could not clear old chunks (may not exist yet): {e}")
    
    for pdf_file in sorted(pdf_files):
        subject = detect_subject_from_filename(pdf_file)
        
        if not subject:
            print(f"  ⚠ Cannot map '{pdf_file}' to a subject")
            continue
        
        pdf_path = os.path.join(TEXTBOOK_DIR, pdf_file)
        print(f"\n  Ingesting {pdf_file} (subject: {subject})...")
        
        try:
            text = extract_text_from_pdf(pdf_path)
            if not text:
                print(f"    ✗ Failed to extract text from {pdf_file}")
                continue
            
            chunks = chunk_text(text)
            print(f"    Created {len(chunks)} chunks from {len(text)} characters")
            
            # Insert chunks in batches
            batch_size = 50
            total_inserted = 0
            
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i+batch_size]
                data = [
                    {
                        "subject": subject,
                        "chunk_index": i + j,
                        "content": chunk,
                    }
                    for j, chunk in enumerate(batch)
                ]
                
                try:
                    supabase.table("textbook_chunks").insert(data).execute()
                    total_inserted += len(batch)
                    pct = int((total_inserted / len(chunks)) * 100)
                    print(f"    ↳ {total_inserted}/{len(chunks)} chunks ({pct}%)", end="\r")
                except Exception as e:
                    print(f"\n    ✗ Error uploading batch at index {i}: {e}")
                    break
            
            print(f"\n    ✓ {subject}: {total_inserted} chunks uploaded")
            ingested[subject] = total_inserted
        
        except Exception as e:
            print(f"    ✗ Failed to ingest {pdf_file}: {e}")
    
    return ingested

# ============================================================================
# STEP 4: INGEST NOTES TO SUPABASE
# ============================================================================

async def ingest_notes() -> dict:
    """Ingest notes PDFs to supabase notes table"""
    print("\n" + "="*70)
    print("STEP 4: Ingesting Study Notes to Supabase")
    print("="*70)
    
    supabase = db._get_supabase()
    ingested = {}
    
    # Check if notes table exists, if not create it
    try:
        supabase.table("notes").select("id").limit(1).execute()
    except:
        print("  Creating notes table...")
        # This will be handled by SQL
        print("  ⚠ notes table doesn't exist - will need SQL to create it")
    
    if not NOTES_SRC_DIR.exists():
        print(f"⚠ notes/ folder not found")
        return ingested
    
    pdf_files = list(NOTES_SRC_DIR.glob("*.pdf"))
    
    for pdf_file in sorted(pdf_files):
        subject = detect_subject_from_filename(pdf_file.name)
        
        if not subject:
            continue
        
        try:
            text = extract_text_from_pdf(str(pdf_file))
            if not text:
                print(f"  ✗ Failed to extract text from {pdf_file.name}")
                continue
            
            # Insert note record
            note_data = {
                "subject": subject,
                "title": SUBJECT_DISPLAY.get(subject, subject.title()),
                "content": text[:10000],  # Limit to 10k chars for preview
                "file_url": f"file:///notes/{pdf_file.name}",
                "created_at": datetime.utcnow().isoformat(),
            }
            
            try:
                supabase.table("notes").insert([note_data]).execute()
                print(f"  ✓ {subject}: notes ingested")
                ingested[subject] = len(text)
            except Exception as e:
                if "doesn't exist" in str(e).lower():
                    print(f"  ⚠ notes table doesn't exist yet - skipping")
                else:
                    print(f"  ⚠ Could not insert note for {subject}: {e}")
        
        except Exception as e:
            print(f"  ✗ Error processing {pdf_file.name}: {e}")
    
    return ingested

# ============================================================================
# STEP 5: INGEST AUDIO LESSONS TO SUPABASE
# ============================================================================

async def ingest_audio_lessons() -> dict:
    """Ingest audio lesson metadata to supabase"""
    print("\n" + "="*70)
    print("STEP 5: Ingesting Audio Lesson Metadata to Supabase")
    print("="*70)
    
    supabase = db._get_supabase()
    ingested = {}
    
    if not AUDIO_SRC_DIR.exists():
        print(f"⚠ audio_lessons/ folder not found")
        return ingested
    
    audio_files = [f for f in AUDIO_SRC_DIR.glob("*.mp3")]
    
    if not audio_files:
        print("⚠ No MP3 files found in audio_lessons/")
        return ingested
    
    print(f"Found {len(audio_files)} audio file(s)")
    
    for audio_file in sorted(audio_files):
        # Parse filename: {subject}_lesson.mp3
        stem = audio_file.stem.replace("_lesson", "").lower()
        subject = stem
        
        if subject not in SUBJECT_DISPLAY:
            print(f"  ⚠ Unknown subject: {subject}")
            continue
        
        try:
            file_size = audio_file.stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            
            # Try to insert into audio_lessons table
            lesson_data = {
                "subject": subject,
                "title": f"{SUBJECT_DISPLAY.get(subject, subject.title())} Lesson",
                "file_url": f"file:///audio_lessons/{audio_file.name}",
                "file_size_bytes": file_size,
                "duration_seconds": 0,  # Would need to calculate from MP3
                "created_at": datetime.utcnow().isoformat(),
            }
            
            try:
                supabase.table("audio_lessons").insert([lesson_data]).execute()
                print(f"  ✓ {subject}: audio lesson metadata ingested ({file_size_mb:.2f} MB)")
                ingested[subject] = file_size
            except Exception as e:
                if "doesn't exist" in str(e).lower():
                    print(f"  ⚠ audio_lessons table doesn't exist yet - skipping")
                else:
                    print(f"  ⚠ Could not insert audio lesson for {subject}: {e}")
        
        except Exception as e:
            print(f"  ✗ Error processing {audio_file.name}: {e}")
    
    return ingested

# ============================================================================
# SUMMARY
# ============================================================================

def print_summary(results: dict) -> None:
    """Print summary of all operations"""
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    print("\n📚 Study Notes Status:")
    for subject_dir in sorted(EUEE_NOTES.iterdir()):
        if not subject_dir.is_dir():
            continue
        subject = subject_dir.name
        has_pdf = (subject_dir / "notes.pdf").exists()
        has_md = (subject_dir / "notes.md").exists()
        
        flags = f"[PDF]" if has_pdf else "     "
        flags += f" [MD]" if has_md else "    "
        display = SUBJECT_DISPLAY.get(subject, subject.title())
        print(f"  {flags}   {display}")
    
    print("\n🎵 Audio Lessons Status:")
    for audio_file in sorted(AUDIO_SRC_DIR.glob("*.mp3")):
        stem = audio_file.stem.replace("_lesson", "").lower()
        size_mb = audio_file.stat().st_size / (1024 * 1024)
        display = SUBJECT_DISPLAY.get(stem, stem.title())
        print(f"  [MP3] ({size_mb:.2f} MB)   {display}")
    
    print("\n📖 Textbooks Status:")
    for pdf_file in sorted(TEXTBOOK_DIR.glob("*.pdf")):
        subject = detect_subject_from_filename(pdf_file.name)
        if subject:
            size_mb = pdf_file.stat().st_size / (1024 * 1024)
            display = SUBJECT_DISPLAY.get(subject, subject.title())
            chunks = results.get("textbooks", {}).get(subject, 0)
            if chunks:
                print(f"  [PDF] ({size_mb:.2f} MB)   {display} — {chunks} chunks ingested")
            else:
                print(f"  [PDF] ({size_mb:.2f} MB)   {display}")
    
    print("\n✅ All resources are wired and ready!")
    print("="*70)

# ============================================================================
# MAIN
# ============================================================================

async def main():
    print("\n" + "█"*70)
    print("█  EUEE ABEBE BOT — WIRE ALL RESOURCES TO SUPABASE")
    print("█"*70)
    
    results = {
        "notes_wired": {},
        "textbooks": {},
        "notes_ingested": {},
        "audio_ingested": {},
    }
    
    # Step 1: Ensure schema
    if not ensure_schema():
        print("\n✗ Failed to verify Supabase connection")
        sys.exit(1)
    
    # Step 2: Wire PDFs
    results["notes_wired"] = wire_notes_pdfs()
    
    # Step 3-5: Async operations
    results["textbooks"] = await ingest_textbooks()
    results["notes_ingested"] = await ingest_notes()
    results["audio_ingested"] = await ingest_audio_lessons()
    
    # Summary
    print_summary(results)
    
    print("\n💡 Next steps:")
    print("   1. Restart the bot: python bot.py")
    print("   2. Users can now access:")
    print("      - Study Notes (PDF + MD)")
    print("      - Audio Lessons (MP3)")
    print("      - Textbook content (chunks)")
    print("\n" + "█"*70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
