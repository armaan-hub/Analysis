"""
Targeted ingestion for the VAT/Peppol QA seed and the Peppol PDF.

Run from the backend/ directory:
    python ingest_vat_peppol.py

Sources ingested:
  1. data/qa_seeds/vat_peppol_qa.json  – Q&A pairs converted to text chunks
  2. brain/UAE E-Invoicing and Peppol... .pdf – Peppol/E-invoicing reference PDF
"""

import asyncio
import io
import json
import sys
import uuid
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from config import settings
from db.database import Base
from db.models import Document
from core.document_processor import DocumentChunk, document_processor
from core.rag_engine import rag_engine

_db_url = settings.database_url
if _db_url.startswith("sqlite:///"):
    _db_url = _db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

_engine = create_async_engine(_db_url, echo=False, future=True, connect_args={"timeout": 60})
_session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

BACKEND_DIR = Path(__file__).parent
PROJECT_ROOT = BACKEND_DIR.parent

QA_SEED_PATH = BACKEND_DIR / "data" / "qa_seeds" / "vat_peppol_qa.json"
PEPPOL_PDF_PATH = (
    PROJECT_ROOT / "brain"
    / "UAE E-Invoicing and Peppol for Third-Party Shipments - Google Gemini.pdf"
)


def qa_seed_to_chunks(json_path: Path, doc_id: str) -> list[DocumentChunk]:
    """Convert QA seed JSON pairs into DocumentChunk objects."""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    pairs = data.get("pairs", [])
    source_name = json_path.name
    chunks = []

    for i, pair in enumerate(pairs):
        question = pair.get("question", "").strip()
        answer = pair.get("answer", "").strip()
        tags = ", ".join(pair.get("tags", []))
        citation = pair.get("citation", "")
        pair_id = pair.get("id", f"pair_{i}")

        text = f"Q: {question}\n\nA: {answer}"
        if citation:
            text += f"\n\nSource: {citation}"

        chunks.append(DocumentChunk(
            text=text,
            metadata={
                "doc_id": doc_id,
                "source": source_name,
                "page": str(i + 1),
                "chunk_index": i,
                "pair_id": pair_id,
                "tags": tags,
                "topic": data.get("topic", ""),
            },
        ))

    return chunks


async def ingest_file(db: AsyncSession, file_path: Path, category: str, name_override: str | None = None) -> dict:
    """Ingest a single file (PDF or QA seed JSON) and return a result dict."""
    name = name_override or file_path.name
    result = {"name": name, "status": "?", "chunks": 0, "error": ""}

    # Check if already indexed
    row = (await db.execute(select(Document).where(Document.original_name == name))).scalar_one_or_none()
    if row:
        if row.status == "indexed":
            result["status"] = "skipped"
            result["chunks"] = row.chunk_count or 0
            return result
        # Retry errored/stale record
        print(f"  RETRY ({row.status})  {name}")
        await db.delete(row)
        await db.flush()

    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        filename=name,
        original_name=name,
        file_type=file_path.suffix.lower(),
        file_size=file_path.stat().st_size,
        status="processing",
        metadata_json={"category": category, "source": str(file_path)},
    )
    db.add(doc)
    await db.flush()

    try:
        if file_path.suffix.lower() == ".json":
            chunks = qa_seed_to_chunks(file_path, doc_id)
        else:
            chunks = await document_processor.process(str(file_path), doc_id)

        if not chunks:
            doc.status = "error"
            doc.error_message = "No text extracted"
            await db.commit()
            result["status"] = "error"
            result["error"] = "No text extracted"
            return result

        count = await rag_engine.ingest_chunks(chunks, doc_id)
        if count == 0:
            doc.status = "error"
            doc.error_message = "Zero chunks indexed"
            await db.commit()
            result["status"] = "error"
            result["error"] = "Zero chunks indexed"
        else:
            doc.status = "indexed"
            doc.chunk_count = count
            await db.commit()
            result["status"] = "ok"
            result["chunks"] = count

    except Exception as exc:
        doc.status = "error"
        doc.error_message = str(exc)[:500]
        await db.commit()
        result["status"] = "error"
        result["error"] = str(exc)[:200]

    return result


async def main() -> None:
    before = rag_engine.collection.count()
    print(f"ChromaDB before: {before:,} chunks")

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    sources = [
        (QA_SEED_PATH, "finance", "vat_peppol_qa.json"),
        (PEPPOL_PDF_PATH, "finance", None),
    ]

    results = []
    async with _session_factory() as db:
        for file_path, category, name_override in sources:
            label = name_override or file_path.name
            if not file_path.exists():
                print(f"  NOT FOUND: {file_path}")
                results.append({"name": label, "status": "not_found", "chunks": 0, "error": str(file_path)})
                continue
            print(f"\nIngesting: {label}")
            r = await ingest_file(db, file_path, category, name_override)
            results.append(r)
            status_str = f"  → {r['status'].upper()}"
            if r["chunks"]:
                status_str += f" ({r['chunks']} chunks)"
            if r["error"]:
                status_str += f"  ERR: {r['error']}"
            print(status_str)

    after = rag_engine.collection.count()
    added = after - before

    print(f"\n{'─'*50}")
    print(f"ChromaDB before : {before:,}")
    print(f"ChromaDB after  : {after:,}")
    print(f"Net chunks added: {added:,}")
    print("─" * 50)
    for r in results:
        print(f"  {r['name']}: {r['status']} | chunks={r['chunks']}")


if __name__ == "__main__":
    asyncio.run(main())
