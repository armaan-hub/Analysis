import sqlite3, json, sys

if len(sys.argv) < 2:
    print('Usage: python print_conv_messages.py <conversation_id>')
    sys.exit(1)

conv_id = sys.argv[1]
DB = 'backend/data/chatbot.db'
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
rows = cur.execute("SELECT role, content, created_at, tokens_used, sources FROM messages WHERE conversation_id = ? ORDER BY created_at", (conv_id,)).fetchall()
for i, r in enumerate(rows, 1):
    print(f"--- MESSAGE {i} ---")
    print("ROLE:", r['role'], "AT", r['created_at'])
    print("TOKENS:", r['tokens_used'])
    print("CONTENT:\n", r['content'])
    print("SOURCES RAW:\n", r['sources'])
    print("\n" + "="*80 + "\n")
conn.close()
