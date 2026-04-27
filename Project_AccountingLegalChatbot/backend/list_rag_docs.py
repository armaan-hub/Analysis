
import asyncio
from core.rag_engine import rag_engine

async def list_docs():
    try:
        # ChromaDB doesn't have a simple 'list documents' but we can get all metadatas
        results = rag_engine.collection.get(include=["metadatas"])
        metas = results["metadatas"]
        doc_names = set()
        for m in metas:
            doc_names.add(m.get("original_name") or m.get("source", "Unknown"))
        
        print(f"Total chunks: {len(metas)}")
        print(f"Unique documents ({len(doc_names)}):")
        for name in sorted(doc_names):
            print(f" - {name}")
    except Exception as e:
        print(f"Failed to list docs: {e}")

if __name__ == "__main__":
    asyncio.run(list_docs())
