"""
Standalone async batch ingest script.

Processes ALL documents in source_law_dir and source_finance_dir through the
existing ingest pipeline, embedding them into ChromaDB + SQLite.

Usage (from project root):
    python3 backend/scripts/batch_ingest.py
"""

import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend/ is on sys.path when run from project root
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from config import settings  # noqa: E402
from db.database import AsyncSessionLocal  # noqa: E402
from db.models import Document  # noqa: E402

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx"}
LOG_PATH = Path(__file__).parent / "ingest_log.json"


def collect_source_files() -> list[tuple[Path, str]]:
    """Return all supported files from law and finance source dirs.

    Each entry is (file_path, source_dir_label) where source_dir_label is
    "law" or "finance".
    """
    results: list[tuple[Path, str]] = []
    for label, dir_str in (("law", settings.source_law_dir), ("finance", settings.source_finance_dir)):
        directory = Path(dir_str)
        if not directory.exists():
            print(f"[WARN] Source directory does not exist: {directory}")
            continue
        for file_path in sorted(directory.rglob("*")):
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                results.append((file_path, label))
    return results


def compute_sha256(file_path: Path) -> str:
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


async def is_already_indexed(file_path: Path, db) -> bool:
    """Return True if a Document with matching content_hash and indexed_at exists."""
    from sqlalchemy import select

    content_hash = compute_sha256(file_path)
    result = await db.execute(
        select(Document).where(
            Document.content_hash == content_hash,
            Document.indexed_at.is_not(None),
        )
    )
    return result.scalar_one_or_none() is not None


def save_progress_log(
    total: int,
    processed: int,
    skipped: int,
    errors: int,
    error_details: list[dict],
) -> None:
    """Write a JSON progress log to scripts/ingest_log.json."""
    log = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
        "error_details": error_details,
    }
    LOG_PATH.write_text(json.dumps(log, indent=2, ensure_ascii=False))


async def run_batch_ingest() -> None:
    from core.document_processor import DocumentProcessor

    document_processor = DocumentProcessor()

    files = collect_source_files()
    total = len(files)

    processed = 0
    skipped = 0
    errors = 0
    error_details: list[dict] = []

    print(f"Found {total} source files. Starting ingest...\n")

    for idx, (file_path, source_dir) in enumerate(files, start=1):
        label = f"[{idx}/{total}]"
        filename = file_path.name

        async with AsyncSessionLocal() as db:
            try:
                if await is_already_indexed(file_path, db):
                    print(f"[SKIP] {filename}")
                    skipped += 1
                    continue

                print(f"{label} Processing: {filename} ...", flush=True)
                await document_processor.ingest_source_file(str(file_path), source_dir, db)
                print(f"[OK] {filename}")
                processed += 1

            except Exception as exc:
                err_msg = str(exc)
                print(f"[ERROR] {filename}: {err_msg}")
                error_details.append({"file": str(file_path), "error": err_msg})
                errors += 1

        # Rate-limit to avoid overwhelming the NVIDIA API
        await asyncio.sleep(0.5)

    save_progress_log(total, processed, skipped, errors, error_details)

    print("\n=== Ingest Complete ===")
    print(f"Total files found:     {total}")
    print(f"Already indexed:       {skipped}")
    print(f"Successfully ingested: {processed}")
    print(f"Errors:                {errors}")
    print("Log saved to: scripts/ingest_log.json")


if __name__ == "__main__":
    asyncio.run(run_batch_ingest())
