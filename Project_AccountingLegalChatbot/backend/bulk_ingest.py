"""
Bulk document ingestion script — seeds the RAG vector store from local directories.

Usage (run from the backend/ directory):
    python bulk_ingest.py

Safe to re-run: files already indexed are detected by original_name and skipped.
Unsupported file types (.png, .jpeg, .doc, etc.) are skipped automatically.
"""

import asyncio
import io
import sys
import uuid
from pathlib import Path

# Force UTF-8 stdout so Arabic/non-Latin filenames don't crash print()
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Ensure backend/ is on sys.path so project imports resolve
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from config import settings
from db.database import Base
from db.models import Document
from core.document_processor import document_processor
from core.rag_engine import rag_engine

# ── Private engine with a generous lock-wait timeout ─────────────
# The running backend server holds the DB connection; using a separate
# engine with timeout=60 lets SQLite retry for up to 60 s before failing.
_db_url = settings.database_url
if _db_url.startswith("sqlite:///"):
    _db_url = _db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

_engine = create_async_engine(
    _db_url,
    echo=False,
    future=True,
    connect_args={"timeout": 60},
)
_session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

# ── Source directories ────────────────────────────────────────────
DIRS = {
    "finance": Path(
        r"C:\Users\Armaan\OneDrive - The Era Corporations\Study\Armaan"
        r"\AI Class\Data Science Class\35. 11-Apr-2026\data_source_finance"
    ),
    "law": Path(
        r"C:\Users\Armaan\OneDrive - The Era Corporations\Study\Armaan"
        r"\AI Class\Data Science Class\35. 11-Apr-2026\data_source_law"
    ),
}


async def main() -> None:
    # Ensure all DB tables exist (idempotent)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    totals = {"indexed": 0, "skipped": 0, "error": 0, "unsupported": 0}

    async with _session_factory() as db:
        for category, source_dir in DIRS.items():
            if not source_dir.exists():
                print(f"\n[{category.upper()}] Directory not found: {source_dir}")
                continue

            files = sorted(f for f in source_dir.rglob("*") if f.is_file())
            print(f"\n[{category.upper()}] {len(files)} files found in {source_dir.name}")

            for file_path in files:
                name = file_path.name

                # Skip unsupported types (.png, .jpeg, .doc, etc.)
                if not document_processor.is_supported(str(file_path)):
                    print(f"  SKIP (unsupported) {name}")
                    totals["unsupported"] += 1
                    continue

                # Skip files already indexed; retry those that errored previously
                result = await db.execute(
                    select(Document).where(Document.original_name == name)
                )
                existing = result.scalar_one_or_none()
                if existing:
                    if existing.status == "indexed":
                        print(f"  SKIP (exists)      {name}")
                        totals["skipped"] += 1
                        continue
                    # status == "error" or "processing" — retry by deleting the stale record
                    print(f"  RETRY ({existing.status:>10})  {name}")
                    await db.delete(existing)
                    await db.flush()

                doc_id = str(uuid.uuid4())
                doc = Document(
                    id=doc_id,
                    filename=name,
                    original_name=name,
                    file_type=file_path.suffix.lower(),
                    file_size=file_path.stat().st_size,
                    status="processing",
                    metadata_json={"category": category, "source_dir": str(source_dir)},
                )
                db.add(doc)
                await db.flush()

                try:
                    chunks = await document_processor.process(str(file_path), doc_id)
                    if not chunks:
                        doc.status = "error"
                        doc.error_message = "No text extracted from file"
                        await db.commit()
                        print(f"  ERR (no text)     {name}")
                        totals["error"] += 1
                        continue
                    count = await rag_engine.ingest_chunks(
    chunks,
    doc_id,
    original_name=name,
    category=category,
)
                    if count == 0:
                        doc.status = "error"
                        doc.error_message = "Embedding/indexing produced zero chunks"
                        await db.commit()
                        print(f"  ERR (0 indexed)   {name}")
                        totals["error"] += 1
                    else:
                        doc.status = "indexed"
                        doc.chunk_count = count
                        await db.commit()
                        print(f"  OK  ({count:>4} chunks)  {name}")
                        totals["indexed"] += 1
                except Exception as exc:
                    doc.status = "error"
                    err_msg = str(exc).strip()
                    doc.error_message = err_msg if err_msg else f"{type(exc).__name__} (empty error message)"
                    await db.commit()
                    print(f"  ERR               {name}: {doc.error_message}")
                    totals["error"] += 1

    print(
        f"\nDone.\n"
        f"  indexed     : {totals['indexed']}\n"
        f"  skipped     : {totals['skipped']}\n"
        f"  errors      : {totals['error']}\n"
        f"  unsupported : {totals['unsupported']}\n"
    )


if __name__ == "__main__":
    asyncio.run(main())
