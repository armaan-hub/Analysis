import sqlite3
import json
from pathlib import Path

db_path = Path("vector_store_v2/chroma.sqlite3")
conn = sqlite3.connect(db_path)

# Get tables
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print("=" * 80)
print("CHROMADB SCHEMA")
print("=" * 80)

for table in tables:
    table_name = table[0]
    cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    print(f"\n{table_name}: {count} rows")
    for col in cols:
        col_name, col_type = col[1], col[2]
        print(f"  - {col_name}: {col_type}")

# Show sample data from each table
print("\n" + "=" * 80)
print("SAMPLE DATA")
print("=" * 80)

for table in tables:
    table_name = table[0]
    count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    if count == 0:
        print(f"\n{table_name}: (empty)")
        continue
    
    print(f"\n{table_name}: (showing up to 3 rows)")
    rows = conn.execute(f"SELECT * FROM {table_name} LIMIT 3").fetchall()
    for row in rows:
        print(f"  {row}")

conn.close()
print("\n" + "=" * 80)
