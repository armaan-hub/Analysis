import sqlite3, pathlib

DB_PATH = pathlib.Path(__file__).parent.parent / "data" / "chatbot.db"


def test_content_hash_column_exists():
    """content_hash column must exist in documents table."""
    conn = sqlite3.connect(str(DB_PATH))
    cols = {r[1] for r in conn.execute("PRAGMA table_info(documents)").fetchall()}
    conn.close()
    assert 'content_hash' in cols, f"content_hash not found. Columns: {cols}"


def test_entities_tables_exist():
    """entities and entity_relations tables must exist."""
    conn = sqlite3.connect(str(DB_PATH))
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert 'entities' in tables, f"entities table not found. Tables: {tables}"
    assert 'entity_relations' in tables, f"entity_relations table not found. Tables: {tables}"
