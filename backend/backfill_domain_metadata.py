"""
One-time migration: backfill `domain` metadata on all existing ChromaDB chunks.

Run from the backend/ directory:
    python backfill_domain_metadata.py

This script reads every chunk in the active vector store, infers a `domain`
value from the chunk's `original_name` metadata, and writes it back.
Chunks that already have a `domain` field are skipped unless --force is passed.
"""

import argparse
import sys
from pathlib import Path

# Make sure backend modules are importable
sys.path.insert(0, str(Path(__file__).parent))

import chromadb
from chromadb.config import Settings as ChromaSettings

from config import settings
from core.rag_engine import _infer_domain_from_name


BATCH_SIZE = 500  # update this many chunks at once


def backfill(force: bool = False) -> None:
    print(f"Vector store: {settings.vector_store_dir}")
    client = chromadb.PersistentClient(
        path=settings.vector_store_dir,
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    col = client.get_or_create_collection("documents")
    total = col.count()
    print(f"Total chunks: {total}")

    processed = 0
    updated = 0
    skipped = 0
    offset = 0

    while offset < total:
        batch = col.get(
            limit=BATCH_SIZE,
            offset=offset,
            include=["metadatas"],
        )
        ids = batch["ids"]
        metadatas = batch["metadatas"]

        update_ids: list[str] = []
        update_metas: list[dict] = []

        for chunk_id, meta in zip(ids, metadatas):
            if not force and meta.get("domain"):
                skipped += 1
                continue

            original_name = meta.get("original_name") or meta.get("source") or ""
            domain = _infer_domain_from_name(original_name)
            new_meta = {**meta, "domain": domain}
            update_ids.append(chunk_id)
            update_metas.append(new_meta)

        if update_ids:
            col.update(ids=update_ids, metadatas=update_metas)
            updated += len(update_ids)

        processed += len(ids)
        offset += BATCH_SIZE
        print(f"  {processed}/{total} processed, {updated} updated, {skipped} skipped …", end="\r")

    print(f"\nDone. {updated} chunks updated, {skipped} already had domain (skipped).")

    # Quick verification: show domain distribution
    print("\nDomain distribution after backfill:")
    sample = col.get(limit=10000, include=["metadatas"])
    from collections import Counter
    domains = Counter(m.get("domain", "MISSING") for m in sample["metadatas"])
    for domain, count in sorted(domains.items(), key=lambda x: -x[1]):
        print(f"  {domain}: {count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill domain metadata on ChromaDB chunks")
    parser.add_argument("--force", action="store_true",
                        help="Re-infer domain even for chunks that already have one")
    args = parser.parse_args()
    backfill(force=args.force)
