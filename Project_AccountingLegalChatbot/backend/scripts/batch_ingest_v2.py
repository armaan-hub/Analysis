"""
batch_ingest_v2.py — Memory-safe batch ingest (NO LLM calls).

Processes all 451 UAE law/finance documents directly:
  extract_text → chunk → embed (NVIDIA) → ChromaDB upsert → SQLite record

Avoids entity-graph LLM calls (root cause of OOM kills in v1).
GraphRAG NER uses only spaCy (CPU, ~11 MB) — no network calls.

Usage:
    nohup ~/chatbot_venv/bin/python3 backend/scripts/batch_ingest_v2.py \
        > backend/scripts/batch_ingest_v2.log 2>&1 &
"""

from __future__ import annotations

import asyncio
import gc
import hashlib
import json
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ignore SIGHUP so terminal disconnect doesn't kill a long-running job
try:
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
except (AttributeError, OSError):
    pass

_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from config import settings  # noqa: E402

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx"}
CHUNK_SIZE_LAW = 800
CHUNK_OVERLAP_LAW = 150
CHUNK_SIZE_FINANCE = 1200
CHUNK_OVERLAP_FINANCE = 200
EMBED_BATCH_SIZE = 20        # chunks per embedding API call (keeps request size small)
EMBED_MAX_CHARS = 500        # hard truncation per chunk — Arabic text: ~300 tokens, English: ~120 tokens
FILE_TIMEOUT_S = 180.0       # hard per-file cap
LOG_PATH = Path(__file__).parent / "batch_ingest_v2_log.json"


# ── helpers ──────────────────────────────────────────────────────────────────

def collect_source_files() -> list[tuple[Path, str]]:
    results: list[tuple[Path, str]] = []
    for label, dir_str in (("law", settings.source_law_dir), ("finance", settings.source_finance_dir)):
        d = Path(dir_str)
        if not d.exists():
            print(f"[WARN] Source directory missing: {d}", flush=True)
            continue
        for fp in sorted(d.rglob("*")):
            if fp.is_file() and fp.suffix.lower() in SUPPORTED_EXTENSIONS:
                results.append((fp, label))
    return results


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def simple_chunk(text: str, size: int, overlap: int) -> list[str]:
    """Sliding-window character chunker. Skips very short fragments."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        piece = text[start: start + size].strip()
        if piece and len(piece.split()) >= 5:
            chunks.append(piece)
        start += size - overlap
    return chunks


def infer_domain(filename: str, source_dir: str) -> str:
    n = filename.lower()
    if any(x in n for x in ("vat", "value added tax")):
        return "vat"
    if any(x in n for x in ("corporate tax", "corp tax", "ct guide")):
        return "corporate_tax"
    if any(x in n for x in ("labour", "labor", "employment", "worker")):
        return "labour"
    if any(x in n for x in ("peppol", "e-invoice", "einvoice", "e_invoice")):
        return "e_invoicing"
    if any(x in n for x in ("ifrs", "financial statement", "accounting standard")):
        return "ifrs"
    if source_dir == "law":
        return "general_law"
    return "general"


async def embed_batch_with_retry(embed_fn, texts: list[str]) -> list:
    # Truncate each text to stay within the embedding model's 512-token limit
    safe_texts = [t[:EMBED_MAX_CHARS] for t in texts]
    for attempt in range(3):
        try:
            return await asyncio.wait_for(embed_fn(safe_texts), timeout=60.0)
        except Exception as e:
            if attempt == 2:
                raise
            print(f"    [RETRY embed attempt {attempt + 2}] {type(e).__name__}: {e}", flush=True)
            await asyncio.sleep(3)
    return []


# ── per-file ingest ───────────────────────────────────────────────────────────

async def process_file(
    file_path: Path,
    source_dir: str,
    collection,
    embed_fn,
    db,
    ner_fn,
    graphrag,
) -> str:
    """Ingest one file. Returns 'ok', 'skip', or 'error:<msg>'."""
    from core.pipeline.pdf_extractor import extract_text
    from db.models import Document, DocumentChunk as DBDocumentChunk
    from sqlalchemy import select, delete

    content_hash = sha256_file(file_path)
    doc_id = content_hash[:36]

    # Skip if already indexed
    res = await db.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.indexed_at.is_not(None),
        )
    )
    if res.scalar_one_or_none() is not None:
        return "skip"

    # Text extraction (pure local, no network)
    extraction = extract_text(str(file_path))
    if extraction.skipped or not extraction.text.strip():
        return "skip"

    raw_text = extraction.text
    chunk_size = CHUNK_SIZE_LAW if source_dir == "law" else CHUNK_SIZE_FINANCE
    chunk_overlap = CHUNK_OVERLAP_LAW if source_dir == "law" else CHUNK_OVERLAP_FINANCE
    chunks = simple_chunk(raw_text, chunk_size, chunk_overlap)
    if not chunks:
        return "skip"

    domain = infer_domain(file_path.name, source_dir)

    # Embed in small batches
    all_embeddings: list = []
    for i in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch = chunks[i: i + EMBED_BATCH_SIZE]
        embs = await embed_batch_with_retry(embed_fn, batch)
        if len(embs) != len(batch):
            return f"error:embed returned {len(embs)} for batch of {len(batch)}"
        all_embeddings.extend(embs)

    # ChromaDB upsert
    ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "doc_id": doc_id,
            "original_name": file_path.name,
            "source_dir": source_dir,
            "domain": domain,
            "category": domain,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "word_count": len(chunks[i].split()),
            "prev_chunk_id": f"{doc_id}_chunk_{i - 1}" if i > 0 else "",
            "next_chunk_id": f"{doc_id}_chunk_{i + 1}" if i < len(chunks) - 1 else "",
        }
        for i in range(len(chunks))
    ]
    collection.upsert(ids=ids, embeddings=all_embeddings, documents=chunks, metadatas=metadatas)

    # GraphRAG NER (spaCy only, no network) — best effort
    if ner_fn is not None and graphrag is not None:
        try:
            entity_rows = [
                (doc_id, idx, name, etype)
                for idx, chunk_text in enumerate(chunks)
                for name, etype in ner_fn(chunk_text)
            ]
            if entity_rows:
                await asyncio.to_thread(graphrag._batch_store_entities, entity_rows)
        except Exception as eg_exc:
            print(f"    [WARN] GraphRAG NER failed: {eg_exc}", flush=True)

    # SQLite document record
    existing_doc_res = await db.execute(select(Document).where(Document.id == doc_id))
    existing_doc = existing_doc_res.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing_doc is None:
        doc = Document(
            id=doc_id,
            filename=str(file_path.resolve()),
            original_name=file_path.name,
            file_type=file_path.suffix.lstrip(".").lower(),
            file_size=file_path.stat().st_size,
            content_hash=content_hash,
            source_dir=source_dir,
            domain=domain,
            status="indexed",
            source="auto_ingest_v2",
            indexed_at=now,
            chunk_count=len(chunks),
        )
        db.add(doc)
    else:
        existing_doc.status = "indexed"
        existing_doc.indexed_at = now
        existing_doc.chunk_count = len(chunks)
        existing_doc.domain = domain

    # SQLite chunk records
    await db.execute(delete(DBDocumentChunk).where(DBDocumentChunk.doc_id == doc_id))
    for i, chunk_text in enumerate(chunks):
        db.add(DBDocumentChunk(
            id=ids[i],
            doc_id=doc_id,
            chunk_index=i,
            text=chunk_text,
            metadata_json=metadatas[i],
        ))

    await db.commit()
    return "ok"


# ── main ─────────────────────────────────────────────────────────────────────

async def run_batch() -> None:
    import logging
    logging.basicConfig(
        level=logging.WARNING,   # suppress DEBUG noise; we use explicit print()
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
        force=True,
    )

    from db.database import AsyncSessionLocal
    from core.rag_engine import rag_engine

    collection = rag_engine.collection
    embed_fn = rag_engine.embedding_provider.embed_texts

    # Load GraphRAG NER (spaCy, no network)
    ner_fn = None
    graphrag = None
    try:
        from core.rag.graph_rag import GraphRAG, _extract_entities
        graph_db_path = str(Path(settings.graph_store_dir) / "graph.db")
        Path(graph_db_path).parent.mkdir(parents=True, exist_ok=True)
        graphrag = GraphRAG(db_path=graph_db_path)
        ner_fn = _extract_entities
        print("[INFO] GraphRAG NER loaded (spaCy en_core_web_sm)", flush=True)
    except Exception as e:
        print(f"[WARN] GraphRAG NER unavailable (will skip): {e}", flush=True)

    files = collect_source_files()
    total = len(files)
    print(f"\nFound {total} source files. Starting ingest...\n", flush=True)

    processed = 0
    skipped = 0
    errors = 0
    error_details: list[dict] = []

    for idx, (file_path, source_dir) in enumerate(files, start=1):
        label = f"[{idx}/{total}]"
        print(f"{label} {file_path.name} ...", end=" ", flush=True)

        async with AsyncSessionLocal() as db:
            try:
                result = await asyncio.wait_for(
                    process_file(file_path, source_dir, collection, embed_fn, db, ner_fn, graphrag),
                    timeout=FILE_TIMEOUT_S,
                )
                if result == "ok":
                    processed += 1
                    chroma_count = collection.count()
                    print(f"[OK] total_vectors={chroma_count}", flush=True)
                elif result == "skip":
                    skipped += 1
                    print("[SKIP]", flush=True)
                else:
                    errors += 1
                    error_details.append({"file": str(file_path), "error": result})
                    print(f"[ERROR] {result}", flush=True)

            except BaseException as exc:
                errors += 1
                err_msg = f"{type(exc).__name__}: {exc}"
                error_details.append({"file": str(file_path), "error": err_msg})
                print(f"[ERROR] {err_msg}", flush=True)
                import traceback
                traceback.print_exc()
                sys.stdout.flush()
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    break

        # Release memory between files
        gc.collect()
        await asyncio.sleep(0.2)

    # Save progress log
    LOG_PATH.write_text(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
        "error_details": error_details,
    }, indent=2, ensure_ascii=False))

    final_count = collection.count()
    print(f"\n=== Ingest Complete ===", flush=True)
    print(f"Total files:           {total}", flush=True)
    print(f"Successfully ingested: {processed}", flush=True)
    print(f"Skipped:               {skipped}", flush=True)
    print(f"Errors:                {errors}", flush=True)
    print(f"ChromaDB total vectors:{final_count}", flush=True)
    print(f"Log: {LOG_PATH}", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(run_batch())
    except BaseException as exc:
        import traceback
        print(f"\n[FATAL] {type(exc).__name__}: {exc}", flush=True)
        traceback.print_exc()
        sys.exit(1)
