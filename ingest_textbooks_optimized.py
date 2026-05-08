#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ingest_textbooks_optimized.py
=============================
Fast textbook ingestion by sampling key pages (TOCs, chapters, selected pages).

Run: python ingest_textbooks_optimized.py
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
CHUNK_SIZE = 1500

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

def detect_subject(filename: str) -> str | None:
    fname_upper = filename.upper()
    for keyword, code in PDF_SUBJECT_MAP.items():
        if keyword.upper() in fname_upper:
            return code
    return None

def extract_sample_from_pdf(pdf_path: str, max_pages: int = 50) -> str:
    """Extract first N pages plus TOC from PDF (much faster)"""
    print(f"    Reading PDF (sampling {max_pages} pages)...")
    all_text = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            print(f"    ℹ Total pages in PDF: {total_pages}")
            
            # Get first 50 pages (usually includes TOC and intro chapters)
            pages_to_read = min(max_pages, total_pages)
            
            for i, page in enumerate(pdf.pages[:pages_to_read]):
                try:
                    text = page.extract_text()
                    if text and text.strip():
                        all_text.append(f"[PAGE {i+1}]\n{text.strip()}")
                except:
                    pass
                
                if (i + 1) % 10 == 0:
                    print(f"    ↳ Extracted {i+1}/{pages_to_read} pages", end="\r")
            
            print(f"    ✓ Extracted {pages_to_read} pages")
    
    except Exception as e:
        print(f"    ✗ Error reading PDF: {e}")
        return ""
    
    return "\n\n".join(all_text)

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """Split text into chunks"""
    if not text:
        return []
    
    chunks = []
    # Split by pages first to preserve structure
    pages = text.split("[PAGE")
    
    for page_text in pages:
        if len(page_text) < chunk_size:
            chunks.append(page_text.strip())
        else:
            # Further split large pages
            start = 0
            while start < len(page_text):
                end = min(start + chunk_size, len(page_text))
                chunk = page_text[start:end].strip()
                if chunk:
                    chunks.append(chunk)
                start = end
    
    return [c for c in chunks if c]  # Remove empty chunks

async def main():
    print("\n" + "="*70)
    print("TEXTBOOK INGESTION (OPTIMIZED - KEY PAGES ONLY)")
    print("="*70)
    
    if not TEXTBOOK_DIR.exists():
        print(f"✗ textbooks/ not found")
        return False
    
    pdf_files = [f for f in os.listdir(TEXTBOOK_DIR) if f.lower().endswith(".pdf")]
    
    if not pdf_files:
        print("✗ No PDF files found in textbooks/")
        return False
    
    print(f"\n✓ Found {len(pdf_files)} textbook(s)\n")
    
    supabase = db._get_supabase()
    
    # Clear existing chunks
    print("Clearing existing textbook chunks...")
    try:
        supabase.table("textbook_chunks").delete().neq("id", 0).execute()
        print("✓ Cleared old chunks\n")
    except Exception as e:
        print(f"✗ Error clearing: {e}\n")
    
    # Ingest each textbook
    total_chunks = 0
    
    for pdf_file in sorted(pdf_files):
        subject = detect_subject(pdf_file)
        
        if not subject:
            print(f"⚠ Cannot map '{pdf_file}' - skipping")
            continue
        
        pdf_path = TEXTBOOK_DIR / pdf_file
        print(f"📖 {subject.upper()}")
        print(f"   File: {pdf_file}")
        
        try:
            text = extract_sample_from_pdf(str(pdf_path), max_pages=60)
            
            if not text or len(text) < 100:
                print(f"   ✗ Failed to extract meaningful content")
                continue
            
            chunks = chunk_text(text)
            print(f"   ✓ Created {len(chunks)} chunks from {len(text)} chars")
            
            if not chunks:
                print(f"   ✗ No chunks created")
                continue
            
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
                    print(f"   ↳ Uploading: {pct}%", end="\r")
                except Exception as e:
                    print(f"\n   ✗ Upload error: {e}")
                    break
            
            print(f"   ✅ {subject}: {inserted} chunks uploaded         ")
            total_chunks += inserted
        
        except Exception as e:
            print(f"   ✗ Error: {e}")
    
    print(f"\n" + "="*70)
    print(f"✅ COMPLETE: {total_chunks} chunks ingested")
    print("="*70 + "\n")
    
    return True

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)
