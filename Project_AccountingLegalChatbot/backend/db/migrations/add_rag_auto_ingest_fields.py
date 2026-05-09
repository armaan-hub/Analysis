"""Migration: add RAG auto-ingest fields to documents table.

Idempotent — safe to run multiple times.
"""
import sqlite3
import logging

logger = logging.getLogger(__name__)

_NEW_COLUMNS = [
    ("source_dir",     "TEXT"),
    ("domain",         "TEXT"),
    ("jurisdiction",   "TEXT"),
    ("law_number",     "TEXT"),
    ("subjects",       "TEXT"),   # JSON stored as TEXT in SQLite
    ("effective_date", "TEXT"),
    ("is_arabic",      "INTEGER DEFAULT 0 NOT NULL"),
    ("was_translated", "INTEGER DEFAULT 0 NOT NULL"),
    ("indexed_at",     "TEXT"),
]


def run_migration(db_path: str) -> None:
    """ALTER TABLE documents to add new columns if not already present."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute("PRAGMA table_info(documents)")
        existing = {row[1] for row in cur.fetchall()}
        for col_name, col_type in _NEW_COLUMNS:
            if col_name not in existing:
                conn.execute(f"ALTER TABLE documents ADD COLUMN {col_name} {col_type}")
                logger.info(f"[migration] Added documents.{col_name}")
        conn.commit()
    finally:
        conn.close()
