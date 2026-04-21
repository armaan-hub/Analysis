import sqlite3


def run_migration(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(conversations)").fetchall()]
        if "mode" in cols:
            return
        conn.execute(
            "ALTER TABLE conversations ADD COLUMN mode VARCHAR(20) NOT NULL DEFAULT 'fast'"
        )
        conn.execute(
            "UPDATE conversations SET mode = 'fast' WHERE mode IS NULL OR mode = 'normal'"
        )
        conn.commit()
    finally:
        conn.close()
