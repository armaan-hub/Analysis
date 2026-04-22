"""
Migration: add entities and entity_relations tables for graph RAG.
"""
import sqlite3, pathlib

DB_PATH = pathlib.Path(__file__).parent.parent.parent / "data" / "chatbot.db"


def run():
    conn = sqlite3.connect(str(DB_PATH))
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}

    if "entities" not in tables:
        conn.execute("""
            CREATE TABLE entities (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id      TEXT    NOT NULL,
                chunk_index INTEGER NOT NULL,
                name        TEXT    NOT NULL,
                entity_type TEXT    NOT NULL DEFAULT 'GENERAL',
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_doc_id ON entities(doc_id)")
        print("[migration] created entities table")
    else:
        print("[migration] entities table already exists — skipped")

    if "entity_relations" not in tables:
        conn.execute("""
            CREATE TABLE entity_relations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id      TEXT NOT NULL,
                source_name TEXT NOT NULL,
                target_name TEXT NOT NULL,
                relation    TEXT NOT NULL DEFAULT 'RELATED_TO',
                weight      REAL NOT NULL DEFAULT 1.0
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_er_doc_id ON entity_relations(doc_id)")
        print("[migration] created entity_relations table")
    else:
        print("[migration] entity_relations table already exists — skipped")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    run()
