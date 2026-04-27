import sqlite3
DB='backend/data/chatbot.db'
conn=sqlite3.connect(DB)
conn.row_factory=sqlite3.Row
cur=conn.cursor()
print('Searching documents table for VAT-related names...')
for r in cur.execute("SELECT id, filename, original_name, file_type, source FROM documents WHERE original_name LIKE ? OR filename LIKE ? LIMIT 50",('%VAT Payment%','%VAT Payment%')):
    print(r['id'], '|', r['filename'], '|', r['original_name'], '|', r['file_type'], '|', r['source'])

print('\nSearching source_documents table...')
for r in cur.execute("SELECT id, original_filename, file_path FROM source_documents WHERE original_filename LIKE ? OR file_path LIKE ? LIMIT 50",('%VAT Payment%','%VAT Payment%')):
    print(r['id'], '|', r['original_filename'], '|', r['file_path'])

conn.close()
