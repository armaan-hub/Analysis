
import asyncio
import json
from core.rag_engine import rag_engine
from config import settings

async def test_rag():
    query = "I have a client who sold Hotel Apartment and now got notice from FTA to pay VAT, need a on pager on this as well documents required to make payment on portal"
    print(f"Testing RAG for query: {query}")
    
    # We need to mock embeddings if we don't have a working key, 
    # but let's see if the embedding key works.
    try:
        results = await rag_engine.search(query, top_k=5)
        print(f"Found {len(results)} results.")
        for i, r in enumerate(results):
            print(f"\nResult {i+1} (Score: {r['score']}):")
            print(f"Source: {r['metadata'].get('source')}")
            print(f"Excerpt: {r['text'][:300]}...")
    except Exception as e:
        print(f"RAG Search failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_rag())
