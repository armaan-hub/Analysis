
import asyncio
import traceback
from core.rag_engine import rag_engine

async def check_dim():
    try:
        # Get one embedding to check its length
        results = rag_engine.collection.get(include=["embeddings"], limit=1)
        if results["embeddings"]:
            dim = len(results["embeddings"][0])
            print(f"Embedding dimensionality: {dim}")
        else:
            print("No embeddings found in store.")
    except Exception:
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_dim())
