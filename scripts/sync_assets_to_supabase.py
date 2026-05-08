"""Sync local notes/ and audio_lessons/ assets into Supabase Storage and tables.

Usage:
    python scripts/sync_assets_to_supabase.py --all
    python scripts/sync_assets_to_supabase.py --notes
    python scripts/sync_assets_to_supabase.py --audio

The script scans the local `notes/` and `audio_lessons/` folders, uploads each
file into a public Supabase Storage bucket, and upserts a matching row into the
`notes` or `audio_lessons` table.
"""
from __future__ import annotations

import argparse
import mimetypes
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from supabase import create_client

from config import SUBJECTS, SUPABASE_KEY, SUPABASE_URL


ROOT = Path(__file__).resolve().parents[1]
NOTES_DIR = ROOT / "notes"
AUDIO_DIR = ROOT / "audio_lessons"
NOTES_BUCKET = "notes"
AUDIO_BUCKET = "audio_lessons"

SUBJECT_KEYWORDS = {
    "math": ["math", "mathematics", "maths"],
    "physics": ["physics"],
    "chemistry": ["chemistry"],
    "biology": ["biology"],
    "english": ["english"],
    "civics": ["civics", "ethics"],
    "history": ["history"],
    "geography": ["geography"],
    "economics": ["economics", "economy"],
    "agriculture": ["agriculture", "agri"],
    "it": ["it", "ict", "information technology", "information_technology", "computer"],
}


@dataclass(frozen=True)
class AssetRecord:
    subject: str
    title: str
    local_path: Path
    bucket: str
    table: str
    content_type: str


def _slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "asset"


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _subject_title(subject: str) -> str:
    return SUBJECTS.get(subject, subject.replace("_", " ").title())


def _infer_subject(path: Path) -> str:
    haystack = _normalize(" ".join([path.stem, path.parent.name, path.as_posix()]))
    for subject, keywords in SUBJECT_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return subject
    return _slugify(path.stem)


def _guess_content_type(path: Path) -> str:
    content_type, _ = mimetypes.guess_type(path.name)
    if content_type:
        return content_type
    if path.suffix.lower() == ".pdf":
        return "application/pdf"
    if path.suffix.lower() in {".mp3"}:
        return "audio/mpeg"
    if path.suffix.lower() in {".m4a"}:
        return "audio/mp4"
    if path.suffix.lower() in {".wav"}:
        return "audio/wav"
    return "application/octet-stream"


def _ensure_env() -> None:
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_KEY:
        missing.append("SUPABASE_KEY")
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")


def _make_client():
    _ensure_env()
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def _ensure_bucket_exists(client, bucket: str) -> None:
    try:
        client.storage.get_bucket(bucket)
        return
    except Exception:
        pass

    try:
        client.storage.create_bucket(bucket, {"public": True})
        print(f"Created storage bucket: {bucket}")
    except Exception as exc:
        print(f"Bucket check warning for {bucket}: {exc}")


def _upload_file(client, bucket: str, local_path: Path, object_path: str, content_type: str) -> str:
    with local_path.open("rb") as handle:
        client.storage.from_(bucket).upload(
            object_path,
            handle,
            file_options={
                "content-type": content_type,
                "upsert": "true",
            },
        )

    return f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{object_path}"


def _collect_notes() -> list[AssetRecord]:
    if not NOTES_DIR.exists():
        return []

    records: list[AssetRecord] = []
    for path in sorted(NOTES_DIR.rglob("*.pdf")):
        subject = _infer_subject(path)
        title = path.stem.replace("_", " ").replace("-", " ").strip().title()
        records.append(
            AssetRecord(
                subject=subject,
                title=title,
                local_path=path,
                bucket=NOTES_BUCKET,
                table="notes",
                content_type="application/pdf",
            )
        )
    return records


def _collect_audio() -> list[AssetRecord]:
    if not AUDIO_DIR.exists():
        return []

    records: list[AssetRecord] = []
    for path in sorted(AUDIO_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".mp3", ".m4a", ".wav"}:
            continue
        subject = _infer_subject(path)
        title = path.stem.replace("_", " ").replace("-", " ").strip().title()
        records.append(
            AssetRecord(
                subject=subject,
                title=title,
                local_path=path,
                bucket=AUDIO_BUCKET,
                table="audio_lessons",
                content_type=_guess_content_type(path),
            )
        )
    return records


def _upsert_record(client, record: AssetRecord, object_path: str, file_url: str) -> None:
    payload: dict[str, object] = {
        "subject": record.subject,
        "title": record.title,
        "file_url": file_url,
    }
    if record.table == "audio_lessons":
        payload["file_size_bytes"] = record.local_path.stat().st_size

    client.table(record.table).upsert(payload, on_conflict="subject").execute()


def _sync_records(client, records: Iterable[AssetRecord], dry_run: bool = False) -> int:
    count = 0
    for record in records:
        object_name = f"{record.subject}/{_slugify(record.local_path.stem)}{record.local_path.suffix.lower()}"
        file_url = f"{SUPABASE_URL}/storage/v1/object/public/{record.bucket}/{object_name}"
        print(f"[{record.table}] {record.local_path} -> {object_name}")

        if dry_run:
            count += 1
            continue

        _ensure_bucket_exists(client, record.bucket)
        file_url = _upload_file(client, record.bucket, record.local_path, object_name, record.content_type)
        _upsert_record(client, record, object_name, file_url)
        count += 1
        print(f"  synced subject={record.subject} url={file_url}")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync local notes/audio assets to Supabase Storage and DB tables.")
    parser.add_argument("--notes", action="store_true", help="Sync note PDFs from notes/")
    parser.add_argument("--audio", action="store_true", help="Sync audio files from audio_lessons/")
    parser.add_argument("--all", action="store_true", help="Sync both notes and audio")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without uploading")
    args = parser.parse_args()

    if not any([args.notes, args.audio, args.all]):
        args.all = True

    client = _make_client()

    total = 0
    if args.all or args.notes:
        total += _sync_records(client, _collect_notes(), dry_run=args.dry_run)
    if args.all or args.audio:
        total += _sync_records(client, _collect_audio(), dry_run=args.dry_run)

    print(f"Done. Processed {total} asset(s).")


if __name__ == "__main__":
    main()