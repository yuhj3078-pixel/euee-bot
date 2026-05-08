#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ingest_textbooks_simple.py
==========================
Simple script to ingest textbooks to existing textbook_chunks table.

Run: python ingest_textbooks_simple.py
"""

import os
import sys
import asyncio
import pdfplumber
from pathlib import Path
from dotenv import load_dotenv

# Load env
load_dotenv()

# Add current dir to path
sys.path.append(os.getcwd())

import db_supabase as db

# Config
BOT_ROOT = Path(__file__).resolve().parent
TEXTBOOK_DIR = BOT_ROOT / "textbooks"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100

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

# Helper functions

def detect_subject(filename: str) -> str | None:
    fname_upper = filename.upper()
    for keyword, code in PDF_SUBJECT_MAP.items():
        if keyword.upper() in fname_upper:
            return code
    return None

def extract_text_from_pdf(pdf_path: str) -> str:
    print(f"    Reading: {pdf_path}")
    all_text = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text.append(text.strip())
    except Exception as e:
        print(f"    ✗ Error reading PDF: {e}")
        return ""
    return "\n\n".join(all_text)

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        start = end - overlap
    return chunks

# Main

async def main():
    print("\n" + "="*70)
    print("TEXTBOOK INGESTION TO SUPABASE")
    print("="*70)
    
    if not TEXTBOOK_DIR.exists():
        print(f"✗ textbooks/ not found at {TEXTBOOK_DIR}")
        return False
    
    pdf_files = [f for f in os.listdir(TEXTBOOK_DIR) if f.lower().endswith(".pdf")]
    
    if not pdf_files:
        print("✗ No PDF files found in textbooks/")
        return False
    
    print(f"\n✓ Found {len(pdf_files)} textbook(s)")
    
    supabase = db._get_supabase()
    
    # Clear existing chunks
    print("\nClearing existing textbook chunks...")
    try:
        supabase.table("textbook_chunks").delete().neq("id", 0).execute()
        print("✓ Cleared old chunks")
    except Exception as e:
        print(f"✗ Error clearing chunks: {e}")
        return False
    
    # Ingest each textbook
    total_chunks = 0
    for pdf_file in sorted(pdf_files):
        subject = detect_subject(pdf_file)
        
        if not subject:
            print(f"\n⚠ Cannot map '{pdf_file}' to a subject - skipping")
            continue
        
        pdf_path = TEXTBOOK_DIR / pdf_file
        print(f"\n  📖 {subject.upper()}")
        print(f"     File: {pdf_file}")
        
        try:
            text = extract_text_from_pdf(str(pdf_path))
            if not text:
                print(f"     ✗ Failed to extract text")
                continue
            
            chunks = chunk_text(text)
            print(f"     ✓ Created {len(chunks)} chunks ({len(text)} chars)")
            
            # Insert in batches
            batch_size = 50
            inserted = 0
            
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
                    inserted += len(batch)
                    pct = int((inserted / len(chunks)) * 100)
                    print(f"     ↳ {inserted}/{len(chunks)} ({pct}%)", end="\r")
                except Exception as e:
                    print(f"\n     ✗ Error uploading batch: {e}")
                    break
            
            print(f"\n     ✅ {subject}: {inserted} chunks uploaded")
            total_chunks += inserted
        
        except Exception as e:
            print(f"     ✗ Error: {e}")
    
    print(f"\n" + "="*70)
    print(f"✅ COMPLETE: {total_chunks} total chunks ingested")
    print("="*70)
    
    return True

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        sys.exit(1)
