import sqlite3
DB='backend/data/chatbot.db'
conn=sqlite3.connect(DB)
cur=conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables=[r[0] for r in cur.fetchall()]
print('TABLES FOUND:', tables)
for t in tables:
    try:
        cur.execute(f"PRAGMA table_info({t})")
        cols=[r[1] for r in cur.fetchall()]
        print('\n', t, '->', cols[:40])
    except Exception as e:
        print('ERR', t, e)
conn.close()
