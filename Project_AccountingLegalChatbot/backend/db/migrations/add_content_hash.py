"""
Migration: add content_hash VARCHAR(64) NULL to documents table.
Safe to run multiple times (checks PRAGMA first).
"""
import sqlite3, pathlib

DB_PATH = pathlib.Path(__file__).parent.parent.parent / "data" / "chatbot.db"


def run():
    conn = sqlite3.connect(str(DB_PATH))
    cols = {r[1] for r in conn.execute("PRAGMA table_info(documents)").fetchall()}
    if "content_hash" not in cols:
        conn.execute("ALTER TABLE documents ADD COLUMN content_hash VARCHAR(64) NULL")
        conn.commit()
        print("[migration] added content_hash to documents")
    else:
        print("[migration] content_hash already present — skipped")
    conn.close()


if __name__ == "__main__":
    run()
