import sqlite3

DB = 'backend/data/chatbot.db'

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

rows = cur.execute("SELECT id,title,mode,created_at FROM conversations WHERE title LIKE '%Hotel Apartment%' ORDER BY created_at DESC LIMIT 200").fetchall()
for r in rows:
    print(r['id'], '|', r['title'], '|', r['mode'], '|', r['created_at'])

conn.close()
