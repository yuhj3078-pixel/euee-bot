
import os
import sys
import pdfplumber
import asyncio
from dotenv import load_dotenv
from pathlib import Path

# Load env from .env
load_dotenv(Path('.env'))

# Add current dir to path
sys.path.append(os.getcwd())

import db_supabase as db
from config import SUBJECTS

# Map PDF filenames to subject codes
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

TEXTBOOK_DIR = "textbooks"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100

def detect_subject(filename: str) -> str | None:
    fname_upper = filename.upper()
    for keyword, code in PDF_SUBJECT_MAP.items():
        if keyword.upper() in fname_upper:
            return code
    return None

def extract_text_from_pdf(pdf_path: str) -> str:
    print(f"Reading PDF: {pdf_path}")
    all_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_text.append(text.strip())
    return "\n\n".join(all_text)

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        start = end - overlap
    return chunks

async def ingest_file(pdf_name: str, subject: str):
    pdf_path = os.path.join(TEXTBOOK_DIR, pdf_name)
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found.")
        return

    print(f"Ingesting {pdf_name} for subject {subject}...")
    text = extract_text_from_pdf(pdf_path)
    chunks = chunk_text(text)
    
    supabase = db._get_supabase()
    batch_size = 50
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
            print(f"  Uploaded {i + len(batch)} / {len(chunks)} chunks", end="\r")
        except Exception as e:
            print(f"\n  Error uploading batch at index {i}: {e}")
            break
    print(f"\nDone with {subject}!")

async def main():
    if not os.path.exists(TEXTBOOK_DIR):
        print(f"Error: {TEXTBOOK_DIR} folder not found.")
        return

    files = [f for f in os.listdir(TEXTBOOK_DIR) if f.lower().endswith(".pdf")]
    print(f"Found {len(files)} textbooks.")
    
    for f in files:
        subject = detect_subject(f)
        if subject:
            await ingest_file(f, subject)
        else:
            print(f"Skipping {f} (could not detect subject)")

if __name__ == "__main__":
    asyncio.run(main())
