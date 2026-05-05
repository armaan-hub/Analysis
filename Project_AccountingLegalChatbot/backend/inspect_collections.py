import chromadb
from pathlib import Path

# Check backend's own vector_store_v2
backend_path = Path("vector_store_v2").absolute()
client = chromadb.PersistentClient(path=str(backend_path))

cols = client.list_collections()
print(f"Collections found: {len(cols)}")
for col in cols:
    print(f"\n{col.name}: {col.count()} chunks")
    
    # Get sample metadata
    r = col.get(limit=1, include=['metadatas'])
    if r and r['metadatas']:
        print(f"  Sample metadata keys: {list(r['metadatas'][0].keys())}")
        print(f"  Sample: {r['metadatas'][0]}")

print("\n" + "="*80)
print("COLLECTION STATISTICS")
print("="*80)

for col in cols:
    r = col.get(limit=5000, include=['metadatas'])
    
    # Analyze metadata
    domains = {}
    cats = {}
    srcs = set()
    
    for m in (r['metadatas'] or []):
        d = m.get('domain', '?')
        c = m.get('category', '?')
        s = m.get('source', '?')
        domains[d] = domains.get(d, 0) + 1
        cats[c] = cats.get(c, 0) + 1
        srcs.add(s)
    
    print(f"\n{col.name}:")
    print(f"  Total chunks: {col.count()}")
    print(f"  Domains: {domains}")
    print(f"  Categories: {cats}")
    print(f"  Unique sources: {len(srcs)}")
