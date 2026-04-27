import sqlite3,sys,json
if len(sys.argv)<2:
    print('Usage: python print_doc_row.py <doc_id>'); sys.exit(1)
doc_id=sys.argv[1]
DB='backend/data/chatbot.db'
conn=sqlite3.connect(DB)
conn.row_factory=sqlite3.Row
cur=conn.cursor()
row=cur.execute('SELECT * FROM documents WHERE id=?',(doc_id,)).fetchone()
if not row:
    print('Not found')
else:
    for k in row.keys():
        print(k,':',row[k])
conn.close()
