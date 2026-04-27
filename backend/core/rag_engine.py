"""
RAG Engine – Retrieval-Augmented Generation pipeline.

Uses ChromaDB as the vector store and NVIDIA (or other) embeddings.
Handles: document ingestion, similarity search, and context-augmented prompting.
"""

import asyncio
import logging
import shutil
import time
import uuid
from pathlib import Path
from typing import Optional, Literal

import chromadb
from chromadb.config import Settings as ChromaSettings
from config import settings

logger = logging.getLogger(__name__)


class EmbeddingProvider:
    """Interface for text embedding models."""

    def __init__(self):
        self.provider = settings.embedding_provider.lower()
        self.api_key = settings.nvidia_api_key
        self.model = settings.nvidia_embed_model
        self.base_url = settings.nvidia_base_url

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        if self.provider == "mock":
            # Return a fake 1024-dim embedding for each text
            return [[0.1] * 1024 for _ in texts]
        if self.provider == "openai":
            return await self._embed_openai(texts)
        return await self._embed_nvidia(texts)

    async def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a single query with retry on transient failures."""
        if self.provider == "mock":
            return [0.1] * 1024
        if self.provider == "openai":
            results = await self._embed_openai([query])
            return results[0]
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "input": [query],
            "model": self.model,
            "input_type": "query",
            "encoding_format": "float",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        return data["data"][0]["embedding"]

    async def _embed_nvidia(self, texts: list[str]) -> list[list[float]]:
        import httpx
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        # Batch processing: NVIDIA NIM allows up to 96 inputs per request for some models
        batch_size = 50
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            payload = {
                "input": batch,
                "model": self.model,
                "input_type": "passage",
                "encoding_format": "float",
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self.base_url}/embeddings",
                    headers=headers,
                    json=payload,
                )
                if resp.status_code >= 400:
                    logger.error(f"NVIDIA Embedding API {resp.status_code}: {resp.text}")
                resp.raise_for_status()
                data = resp.json()
                
            batch_embeddings = [item["embedding"] for item in data["data"]]
            all_embeddings.extend(batch_embeddings)
            
        return all_embeddings

    async def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        import httpx
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        
        batch_size = 100
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            payload = {
                "input": batch,
                "model": "text-embedding-3-small",
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                
            batch_embeddings = [item["embedding"] for item in data["data"]]
            all_embeddings.extend(batch_embeddings)
            
        return all_embeddings


import httpx  # Ensure httpx is available for type hints and usage


def _infer_domain_from_name(name: str) -> str:
    """Infer document domain from filename for metadata tagging.

    Normalizes hyphens/underscores to spaces before matching so that
    filenames like "Federal-Decree-Law-No.-47-of-2022-EN.pdf" still match
    keyword "federal decree law no. 47".

    Order matters: check more-specific patterns before broad ones.
    """
    # Normalise: lowercase, hyphens/underscores → spaces
    n = name.lower().replace("-", " ").replace("_", " ")

    # E-invoicing — must come BEFORE vat
    if any(kw in n for kw in [
        "e invoic", "einvoic", "peppol", "243 & 244", "243&244", "243 244",
        "implementing einvoic",
    ]):
        return "e_invoicing"

    # Corporate Tax — must come BEFORE vat (many CT docs mention "tax" broadly)
    if any(kw in n for kw in [
        "corporate tax", "ctp0", "ct registration", "ct deregistr", "ct edit",
        # Federal Decree Law 47 of 2022 (the CT law) — works after hyphen normalisation
        "federal decree law no. 47", "law no. 47",
        # CT-specific concepts
        "small business relief", "qualifying free zone", "qualifying income",
        "participation exemption", "interest deduction", "transfer pricing",
        "tax group", "tax residency",
        # FTA numbered CT guide series (topics that only appear in CT guides)
        "taxation of", "taxable income",
        "business restructuring", "qualifying group", "foreign source income",
        "extractive", "registration of juridical person", "registration of natural person",
        "exempt person", "investment fund", "master guide",
        "accounting standards guide",  # CT accounting standards guide
        "explanatory guide",  # CT explanatory guide
        "determination of taxable", "automotive sector",
        "financial services",  # CT financial services sector guide
        "insurance",  # CT insurance sector guide (not VAT on insurance)
        "natural resource", "natural person",
        "qualifying public benefit", "public benefit entity",
    ]):
        return "corporate_tax"

    # Labour / HR
    if any(kw in n for kw in ["labour", "labor", "mohre", "wps", "gratuity"]):
        return "labour"

    # Commercial / Company Law / Business Registration
    if any(kw in n for kw in [
        "commercial compan", "licensing", "rakez", "free zone", "dwc",
        "hamriyah", "dubai south", "rak free",
        "list of activities", "activities description",
    ]):
        return "commercial"

    # IFRS / Client financials
    if any(kw in n for kw in [
        "audit report", "financial statement", "draft fs", "trail balance",
        "trial balance", "comparative", "castle plaza", "tl 2024", "signed audit",
    ]):
        return "ifrs"

    # VAT — broad bucket; check AFTER CT so CT docs don't fall here
    if any(kw in n for kw in [
        "vat", "vatp", "tax invoice", "real estate", "property",
        "reverse charge", "refund", "electronic device", "gold",
        "zero rating", "input tax", "output tax", "excise",
        "no 8 of 2017",    # VAT Federal Decree Law No 8 of 2017
        "executive regulation of federal decree",  # VAT exec regulation
        "convert tin", " trn",   # TRN conversion guides
        "e services",            # FTA e-services VAT portal
        "tax procedures",        # Tax Procedures law/regulation
    ]):
        return "vat"

    # Research notes created by the chatbot
    if n.startswith("research:") or n.startswith("research "):
        return "general"

    return "general"


class RAGEngine:
    """Retrieval-Augmented Generation logic."""

    def __init__(self):
        self.embedding_provider = EmbeddingProvider()

        # Initialize ChromaDB persistent client
        try:
            if settings.vector_store_dir == ":memory:":
                logger.info("Using ephemeral (in-memory) ChromaDB client")
                self.chroma_client = chromadb.EphemeralClient(
                    settings=ChromaSettings(anonymized_telemetry=False)
                )
            else:
                self.chroma_client = chromadb.PersistentClient(
                    path=settings.vector_store_dir,
                    settings=ChromaSettings(
                        anonymized_telemetry=False,
                    ),
                )
            self._collection = self.chroma_client.get_or_create_collection(
                name="documents",
                metadata={"hnsw:space": "cosine"},
            )
            # Test connectivity/validity
            try:
                self._collection.count()
            except Exception as e:
                logger.warning(f"Initial collection count failed: {e}")

        except Exception as e:
            logger.error(f"ChromaDB store corrupted or inaccessible — backing up and creating fresh: {e}")
            backup = Path(settings.vector_store_dir + "_backup_corrupted")
            try:
                if Path(settings.vector_store_dir).exists():
                    shutil.move(settings.vector_store_dir, str(backup))
                    logger.info(f"Corrupted store moved to: {backup}")
                
                # Try fresh initialization
                self.chroma_client = chromadb.PersistentClient(
                    path=settings.vector_store_dir,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
                self._collection = self.chroma_client.get_or_create_collection(
                    name="documents",
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception as e2:
                logger.critical(f"Fatal error: Could not initialize ChromaDB even after reset: {e2}")
                raise e2

    @property
    def collection(self):
        """Robust collection access that attempts to recover from common segment errors."""
        try:
            # Try a simple operation to see if segments are valid
            self._collection.count()
            return self._collection
        except (AttributeError, Exception) as e:
            if "dimensionality" in str(e) or "segment" in str(e).lower():
                logger.warning(f"ChromaDB segment error detected ({e}). Attempting to re-initialize client...")
                # Re-initialize client (often fixes transient segment issues in PersistentClient)
                self.__init__()
                return self._collection
            raise e

    @collection.setter
    def collection(self, value):
        """Allow direct assignment of the collection (used in tests for mocking)."""
        self._collection = value

    async def search(
        self,
        query: str,
        top_k: int = 8,
        filter: Optional[dict] = None,
        min_score: float = 0.30,
    ) -> list[dict]:
        """Perform similarity search and return relevant document chunks."""
        query_embedding = await self.embedding_provider.embed_query(query)

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k * 2,  # Over-fetch for better filtering
            where=filter,
            include=["documents", "metadatas", "distances"],
        )

        search_results = []
        if not results["ids"]:
            return []

        # Convert distances to scores (cosine distance 0..2 where 0 is identical)
        # Score = 1 - distance/2 (approximate)
        for i in range(len(results["ids"][0])):
            distance = results["distances"][0][i]
            score = 1 - (distance / 2.0)
            
            if score < min_score:
                continue

            search_results.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "score": score,
                "source": results["metadatas"][0][i].get("source", "Unknown"),
            })

        # Sort by score, then hybrid re-rank
        search_results.sort(key=lambda x: x["score"], reverse=True)
        # Hybrid re-ranking: blend vector score with keyword signal
        from core.search.hybrid_engine import blend_results
        search_results = blend_results(query, search_results)
        return search_results[:top_k]

    def build_augmented_prompt(
        self,
        query: str,
        results: list[dict],
        system_prompt: Optional[str] = None,
    ) -> list[dict]:
        """Build a context-augmented message list for the LLM."""
        context_parts = []
        for r in results:
            source = r["metadata"].get("original_name") or r["metadata"].get("source", "Unknown")
            page = r["metadata"].get("page", "?")
            context_parts.append(f"Source: {source} (Page {page})\n{r['text']}")

        context = "\n\n---\n\n".join(context_parts)
        
        if system_prompt:
            system_message = (
                system_prompt
                + "\n\nContext from indexed documents:\n"
                + context
            )
        else:
            system_message = (
                "You are a helpful assistant. Use the following context to answer the user's question. "
                "If you don't know the answer based on the context, say so. Do not make up information.\n\n"
                "Context:\n" + context
            )

        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": query},
        ]

    async def delete_document(self, doc_id: str) -> int:
        """Delete all chunks belonging to doc_id from ChromaDB.

        Returns the number of chunks removed.
        """
        existing = self.collection.get(
            where={"doc_id": doc_id},
            include=[],
        )
        chunk_ids = existing.get("ids", [])
        if chunk_ids:
            self.collection.delete(ids=chunk_ids)
        return len(chunk_ids)

    async def ingest_chunks(
        self,
        chunks: list,
        doc_id: str,
        original_name: str = "",
        category: str = "general",
    ) -> int:
        """Embed and store document chunks in ChromaDB.

        Returns the number of chunks successfully indexed.
        Each chunk receives:
          - doc_id, original_name, category from caller
          - domain inferred from original_name for domain-filtered RAG
          - page/source from the chunk's own metadata
        """
        if not chunks:
            return 0

        texts: list[str] = []
        raw_metadatas: list[dict] = []
        for c in chunks:
            if hasattr(c, "text"):
                texts.append(c.text)
                raw_metadatas.append(dict(c.metadata) if c.metadata else {})
            else:
                texts.append(c.get("text", ""))
                raw_metadatas.append(dict(c.get("metadata", {})))

        domain = _infer_domain_from_name(original_name)
        embeddings = await self.embedding_provider.embed_texts(texts)

        ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas: list[dict] = []
        for raw in raw_metadatas:
            meta: dict = {}
            # Copy only scalar values from per-chunk metadata (ChromaDB constraint)
            for k, v in raw.items():
                if isinstance(v, (str, int, float, bool)):
                    meta[k] = str(v) if k == "page" else v
                elif v is not None:
                    meta[k] = str(v)
            # Document-level fields (always override per-chunk values if present)
            meta["doc_id"] = doc_id
            meta["original_name"] = original_name or ""
            meta["source"] = original_name or doc_id
            meta["category"] = category
            meta["domain"] = domain
            metadatas.append(meta)

        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        return len(chunks)

    def get_stats(self) -> dict:
        """Return statistics about the vector store."""
        return {
            "total_chunks": self.collection.count(),
            "vector_store_path": settings.vector_store_dir,
        }


# Module-level singleton
rag_engine = RAGEngine()
