"""
RAG Engine – Retrieval-Augmented Generation pipeline.

Uses ChromaDB as the vector store and NVIDIA (or other) embeddings.
Handles: document ingestion, similarity search, and context-augmented prompting.
"""

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Optional
import httpx
import chromadb
from chromadb.config import Settings as ChromaSettings
from config import settings
from core.document_processor import DocumentChunk

logger = logging.getLogger(__name__)


class EmbeddingProvider:
    """Generates embeddings using the configured provider (NVIDIA NIM default)."""

    def __init__(self):
        self.provider = settings.embedding_provider
        self.api_key = settings.nvidia_api_key
        self.model = settings.nvidia_embed_model
        self.base_url = settings.nvidia_base_url

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        if self.provider == "openai":
            return await self._embed_openai(texts)
        return await self._embed_nvidia(texts)

    async def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings via OpenAI API."""
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        all_embeddings: list[list[float]] = []
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch = [t[:8000] for t in texts[i:i + batch_size]]
            resp = await client.embeddings.create(
                input=batch,
                model=settings.openai_embed_model,
            )
            all_embeddings.extend([item.embedding for item in resp.data])
        return all_embeddings

    async def _embed_nvidia(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings via NVIDIA NIM API with retry on transient failures."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        all_embeddings = []
        # Process in batches of 50 to avoid payload limits
        batch_size = 50
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            # Truncate texts that are too long for the embedding model
            batch = [t[:8000] if len(t) > 8000 else t for t in batch]

            payload = {
                "input": batch,
                "model": self.model,
                "input_type": "passage",
                "encoding_format": "float",
                "truncate": "END",
            }

            last_exc: Exception | None = None
            for attempt in range(3):
                if attempt > 0:
                    await asyncio.sleep(2 ** attempt)  # 2 s, 4 s back-off
                try:
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        resp = await client.post(
                            f"{self.base_url}/embeddings",
                            headers=headers,
                            json=payload,
                        )
                        if resp.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                            last_exc = httpx.HTTPStatusError(
                                f"HTTP {resp.status_code}", request=resp.request, response=resp
                            )
                            logger.warning(f"Embedding API {resp.status_code}, retrying (attempt {attempt+1}/3)…")
                            continue
                        resp.raise_for_status()
                        ct = resp.headers.get("content-type", "")
                        if "application/json" not in ct and "text/json" not in ct:
                            raise ValueError(
                                f"Embedding API returned non-JSON ({ct}). "
                                "Check NVIDIA_BASE_URL is https://integrate.api.nvidia.com/v1"
                            )
                        data = resp.json()
                    batch_embeddings = [item["embedding"] for item in data["data"]]
                    all_embeddings.extend(batch_embeddings)
                    last_exc = None
                    break
                except (httpx.TimeoutException, httpx.ConnectError) as exc:
                    last_exc = exc
                    logger.warning(f"Embedding API network error (attempt {attempt+1}/3): {exc}")
            if last_exc is not None:
                raise last_exc

        return all_embeddings

    async def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a single query with retry on transient failures."""
        if self.provider == "openai":
            results = await self._embed_openai([query])
            return results[0]
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "input": [query[:8000]],
            "model": self.model,
            "input_type": "query",
            "encoding_format": "float",
            "truncate": "END",
        }

        last_exc: Exception | None = None
        for attempt in range(3):
            if attempt > 0:
                await asyncio.sleep(2 ** attempt)
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        f"{self.base_url}/embeddings",
                        headers=headers,
                        json=payload,
                    )
                    if resp.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                        last_exc = httpx.HTTPStatusError(
                            f"HTTP {resp.status_code}", request=resp.request, response=resp
                        )
                        logger.warning(f"Embedding API {resp.status_code}, retrying (attempt {attempt+1}/3)…")
                        continue
                    resp.raise_for_status()
                    ct = resp.headers.get("content-type", "")
                    if "application/json" not in ct and "text/json" not in ct:
                        raise ValueError(
                            f"Embedding API returned non-JSON ({ct}). "
                            "Check NVIDIA_BASE_URL is https://integrate.api.nvidia.com/v1"
                        )
                    data = resp.json()
                return data["data"][0]["embedding"]
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exc = exc
                logger.warning(f"Embedding API network error (attempt {attempt+1}/3): {exc}")
        raise last_exc  # type: ignore[misc]


class RAGEngine:
    """
    Retrieval-Augmented Generation engine.

    Workflow:
    1. Ingest documents → chunk → embed → store in ChromaDB
    2. On query → embed query → retrieve top-k similar chunks
    3. Build augmented prompt with retrieved context
    """

    SYSTEM_PROMPT = """You are an expert AI assistant specializing in accounting, 
finance, tax law, and legal compliance — particularly for UAE regulations 
(IFRS, VAT, Corporate Tax, and related laws).

When answering questions:
- Reference the provided context documents when available
- Cite specific sources (document name, page number) when possible  
- If the context doesn't contain the answer, search your knowledge and answer directly
- Be precise with numbers, dates, and regulatory references
- When your response exceeds 150 words, structure it: one-sentence direct answer first, then numbered sections with bold headings, then a brief summary
- Use markdown tables for comparisons or multi-column data
- Cite web sources as [Source Name] inline when using web search results

Context from indexed documents:
{context}
"""

    def __init__(self):
        self.embedding_provider = EmbeddingProvider()

        # Initialize ChromaDB persistent client
        try:
            self.chroma_client = chromadb.PersistentClient(
                path=settings.vector_store_dir,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                ),
            )
            self.collection = self.chroma_client.get_or_create_collection(
                name="documents",
                metadata={"hnsw:space": "cosine"},
            )
            doc_count = self.collection.count()
        except Exception as e:
            logger.error(f"ChromaDB store corrupted or inaccessible — backing up and creating fresh: {e}")
            backup = Path(settings.vector_store_dir + "_backup_corrupted")
            try:
                if Path(settings.vector_store_dir).exists():
                    shutil.move(settings.vector_store_dir, str(backup))
                    logger.info(f"Corrupted store moved to: {backup}")
            except Exception as backup_err:
                logger.warning(f"Could not back up corrupted store: {backup_err}")
            Path(settings.vector_store_dir).mkdir(parents=True, exist_ok=True)
            self.chroma_client = chromadb.PersistentClient(
                path=settings.vector_store_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self.collection = self.chroma_client.get_or_create_collection(
                name="documents",
                metadata={"hnsw:space": "cosine"},
            )
            doc_count = 0

        logger.info(
            f"RAG engine initialized. Vector store: {settings.vector_store_dir}, "
            f"Documents in store: {doc_count}"
        )

    async def ingest_chunks(self, chunks: list[DocumentChunk], doc_id: str, original_name: str | None = None, category: str = "general") -> int:
        """
        Ingest document chunks into the vector store.

        Args:
            chunks: List of DocumentChunk from the document processor.
            doc_id: Document ID for metadata filtering.
            original_name: Original document filename.
            category: Document category for filtering (e.g., "law", "finance", "general").

        Returns:
            Number of chunks ingested.
        """
        if not chunks:
            return 0

        texts = [c.text for c in chunks]
        ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        metas = []
        for i, c in enumerate(chunks):
            meta = dict(c.metadata)
            meta["doc_id"] = doc_id
            if original_name:
                meta["original_name"] = original_name
            meta["category"] = category
            metas.append(meta)
        metadatas = metas

        # Generate embeddings
        logger.info(f"Generating embeddings for {len(texts)} chunks...")
        embeddings = await self.embedding_provider.embed_texts(texts)

        # Upsert into ChromaDB
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        logger.info(f"Ingested {len(chunks)} chunks for document {doc_id}")
        return len(chunks)

    def resolve_doc_names(self, source_ids: list[str]) -> dict[str, str]:
        """Map chunk source IDs to human-readable original filenames."""
        if not source_ids:
            return {}
        try:
            results = self.collection.get(ids=source_ids, include=["metadatas"])
            mapping: dict[str, str] = {}
            for sid, meta in zip(results["ids"], results["metadatas"]):
                mapping[sid] = meta.get("original_name", sid)
            return mapping
        except Exception:
            return {s: s for s in source_ids}

    def hybrid_search(self, query: str, doc_ids: list[str] | None = None,
                      top_k: int = 8) -> list[dict]:
        """Hybrid vector + graph search. Falls back to vector-only if graph has no entities."""
        from backend.core.rag.hybrid_retriever import HybridRetriever
        from backend.core.rag.graph_rag import GraphRAG
        import pathlib
        graph = GraphRAG(db_path=pathlib.Path(__file__).parent.parent / "chatbot.db")
        retriever = HybridRetriever(rag_engine=self, graph_rag=graph)
        return retriever.retrieve(query=query, doc_ids=doc_ids, top_k=top_k)

    async def search(
        self,
        query: str,
        top_k: int = 5,
        doc_id: Optional[str] = None,
        filter: Optional[dict] = None,
        min_score: Optional[float] = None,
    ) -> list[dict]:
        """
        Search the vector store for relevant chunks.

        Args:
            query: The search query.
            top_k: Number of results to return.
            doc_id: Optional filter to search within a specific document.
            filter: Optional metadata filter dict (e.g. {"category": "finance"}).
            min_score: Optional minimum cosine similarity score (0.0-1.0). Chunks below threshold are filtered out.

        Returns:
            List of results with text, metadata, and similarity score, sorted by score descending, capped at 8 results.
        """
        if self.collection.count() == 0:
            return []

        # Generate query embedding
        query_embedding = await self.embedding_provider.embed_query(query)

        # Build where filter
        where_filter = None
        if doc_id:
            where_filter = {"doc_id": doc_id}
        elif filter:
            where_filter = filter

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self.collection.count()),
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        # Format results
        search_results = []
        if results and results["documents"]:
            for i, doc_text in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 1.0
                score = 1 - distance  # Convert cosine distance to similarity score
                
                # Apply score threshold if specified
                if min_score is not None and score < min_score:
                    continue
                
                search_results.append({
                    "text": doc_text,
                    "metadata": meta,
                    "score": score,
                    # Structured source fields for Document Peeker
                    "source": meta.get("original_name") or meta.get("source", meta.get("filename", "Unknown")),
                    "page": meta.get("page", meta.get("page_number", 1)),
                    "excerpt": doc_text[:200],
                })
        
        # Sort by score descending
        search_results.sort(key=lambda x: x["score"], reverse=True)
        
        # Cap at 8 results maximum
        return search_results[:8]

    def build_augmented_prompt(
        self,
        query: str,
        search_results: list[dict],
        system_prompt: Optional[str] = None,
    ) -> list[dict]:
        """
        Build the augmented prompt with retrieved context.

        Args:
            query: User query.
            search_results: RAG results.
            system_prompt: Optional override; falls back to SYSTEM_PROMPT template.

        Returns messages in OpenAI-compatible format.
        """
        # Build context string from search results
        if search_results:
            context_parts = []
            for i, result in enumerate(search_results, 1):
                source = result["metadata"].get("original_name") or result["metadata"].get("source", "Unknown")
                page = result["metadata"].get("page", "?")
                score = result.get("score", 0)
                context_parts.append(
                    f"[Source {i}: {source}, Page {page}, Relevance: {score:.2f}]\n"
                    f"{result['text']}"
                )
            context = "\n\n---\n\n".join(context_parts)
        else:
            context = "No relevant documents found in the knowledge base."

        if system_prompt:
            system_message = (
                system_prompt
                + "\n\nContext from indexed documents:\n"
                + context
            )
        else:
            system_message = self.SYSTEM_PROMPT.format(context=context)

        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": query},
        ]

    async def delete_document(self, doc_id: str) -> int:
        """Remove all chunks for a document from the vector store."""
        # Get IDs for this document
        results = self.collection.get(
            where={"doc_id": doc_id},
            include=[],
        )
        if results and results["ids"]:
            self.collection.delete(ids=results["ids"])
            logger.info(f"Deleted {len(results['ids'])} chunks for document {doc_id}")
            return len(results["ids"])
        return 0

    def get_stats(self) -> dict:
        """Return statistics about the vector store."""
        return {
            "total_chunks": self.collection.count(),
            "vector_store_path": settings.vector_store_dir,
        }


# Module-level singleton
rag_engine = RAGEngine()
