import sqlite3
import pytest
from db.migrations.add_conversation_mode import run_migration


def _make_legacy_db(tmp_path):
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE conversations ("
        "id TEXT PRIMARY KEY, title TEXT, created_at TEXT)"
    )
    conn.execute("INSERT INTO conversations (id, title, created_at) VALUES "
                 "('c1', 'Old', '2026-04-01')")
    conn.commit()
    conn.close()
    return str(db)


def test_migration_adds_mode_column_and_backfills(tmp_path):
    db_path = _make_legacy_db(tmp_path)
    run_migration(db_path)
    conn = sqlite3.connect(db_path)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(conversations)").fetchall()]
    assert "mode" in cols
    rows = conn.execute("SELECT mode FROM conversations").fetchall()
    assert rows == [("fast",)]
    conn.close()


def test_migration_is_idempotent(tmp_path):
    db_path = _make_legacy_db(tmp_path)
    run_migration(db_path)
    run_migration(db_path)  # must not raise
    conn = sqlite3.connect(db_path)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(conversations)").fetchall()]
    assert cols.count("mode") == 1
    conn.close()
