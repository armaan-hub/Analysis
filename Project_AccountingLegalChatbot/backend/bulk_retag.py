"""
One-time migration: retag existing ChromaDB chunks with correct category metadata.

Reads every Document record's metadata_json.category from SQLite, then calls
ChromaDB collection.update() to stamp that category onto every chunk belonging
to that document.

Safe to re-run: documents already correctly tagged are skipped.

Usage (run from backend/ directory):
    python bulk_retag.py
"""

import asyncio
import io
import sys
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from config import settings
from db.database import Base
from db.models import Document
from core.rag_engine import rag_engine

_db_url = settings.database_url
if _db_url.startswith("sqlite:///"):
    _db_url = _db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

_engine = create_async_engine(_db_url, echo=False, future=True, connect_args={"timeout": 60})
_session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def main() -> None:
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    totals = {"retagged": 0, "skipped": 0, "no_chunks": 0, "error": 0}

    async with _session_factory() as db:
        result = await db.execute(select(Document).where(Document.status == "indexed"))
        docs = result.scalars().all()
        print(f"Found {len(docs)} indexed documents to check.\n")

        for doc in docs:
            meta = doc.metadata_json if isinstance(doc.metadata_json, dict) else {}
            category = meta.get("category", "general")

            if category == "general":
                print(f"  SKIP (no category)  {doc.original_name}")
                totals["skipped"] += 1
                continue

            # Get all chunk IDs for this document from ChromaDB
            # Query by original_name (not doc_id) because duplicate uploads create new doc_ids
            # but chunks from old uploads still exist with old doc_ids
            try:
                existing = rag_engine.collection.get(
                    where={"original_name": str(doc.original_name)},
                    include=["metadatas"],
                )
                # Fallback: old chunks ingested before the fix have no original_name metadata.
                # Try finding them by doc_id instead.
                if not existing or not existing["ids"]:
                    existing = rag_engine.collection.get(
                        where={"doc_id": str(doc.id)},
                        include=["metadatas"],
                    )
            except Exception as exc:
                print(f"  ERR  (query)        {doc.original_name}: {exc}")
                totals["error"] += 1
                continue

            if not existing or not existing["ids"]:
                print(f"  SKIP (no chunks)    {doc.original_name}")
                totals["no_chunks"] += 1
                continue

            chunk_ids = existing["ids"] or []
            current_metas = existing["metadatas"] or []

            # Check if already correctly tagged (both category AND original_name must match)
            # IMPORTANT: require at least one chunk AND all chunks must match
            already_tagged = (
                len(current_metas) > 0
                and all(
                    m.get("category") == category and m.get("original_name") == doc.original_name
                    for m in current_metas
                )
            )
            if already_tagged:
                print(f"  SKIP (already ok)   {doc.original_name}  [{category}]")
                totals["skipped"] += 1
                continue

            # Build updated metadata: preserve all existing fields, update category + original_name
            updated_metas = []
            for m in current_metas:
                updated = dict(m)
                updated["category"] = category
                updated["original_name"] = doc.original_name
                updated_metas.append(updated)

            try:
                rag_engine.collection.update(
                    ids=chunk_ids,
                    metadatas=updated_metas,
                )
                print(f"  OK   ({len(chunk_ids):>4} chunks)  {doc.original_name}  [{category}]")
                totals["retagged"] += 1
            except Exception as exc:
                print(f"  ERR  (update)       {doc.original_name}: {exc}")
                totals["error"] += 1

    print(
        f"\nDone.\n"
        f"  retagged  : {totals['retagged']}\n"
        f"  skipped   : {totals['skipped']}\n"
        f"  no chunks : {totals['no_chunks']}\n"
        f"  errors    : {totals['error']}\n"
    )


if __name__ == "__main__":
    asyncio.run(main())
