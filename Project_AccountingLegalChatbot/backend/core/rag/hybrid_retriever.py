"""
Hybrid Retriever — Parallel Fusion.

Fires vector search (ChromaDB) and entity graph search (GraphRAG) simultaneously
using asyncio.gather(). Results are merged, deduplicated by chunk ID, and
re-ranked by a combined score before returning.

Score formula:  combined = 0.6 × vector_score + 0.4 × graph_score
Graph-only chunks receive:  combined = 0.4 × graph_score
Vector-only chunks receive: combined = 0.6 × vector_score (graph_score = 0)
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from core.search.hybrid_engine import blend_results

logger = logging.getLogger(__name__)

_VECTOR_WEIGHT = 0.6
_GRAPH_WEIGHT = 0.4

_STOPWORDS = frozenset([
    "the", "and", "for", "with", "from", "that", "this", "are", "was",
    "will", "have", "has", "had", "can", "may", "how", "what", "when",
    "where", "which", "who", "why", "all", "any", "one", "two",
    "its", "not", "but", "our", "you", "his", "her", "him", "she",
    "they", "did", "get", "got", "let", "set", "use", "via", "per",
])


def _extract_query_entities(query: str) -> list[str]:
    """Extract candidate entity strings from a query for graph lookup."""
    entities: set[str] = set()
    words = re.findall(r"\b[a-zA-Z]{3,}\b", query)
    for w in words:
        if w.lower() not in _STOPWORDS:
            entities.add(w.lower())
    for phrase in re.findall(r"\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\b", query):
        entities.add(phrase.lower())
    return list(entities)


class HybridRetriever:
    """Parallel Fusion retriever combining vector similarity and entity graph."""

    def __init__(
        self,
        rag_engine,
        graph_rag,
        graph_expansion_depth: int = 1,
        vector_weight: float = _VECTOR_WEIGHT,
        graph_weight: float = _GRAPH_WEIGHT,
    ):
        self._rag = rag_engine
        self._graph = graph_rag
        self._depth = graph_expansion_depth
        self._vw = vector_weight
        self._gw = graph_weight

    async def retrieve(
        self,
        query: str,
        top_k: int = 8,
        rag_filter: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Run vector + graph searches in parallel and return fused, de-duplicated results.

        Returns list of chunk dicts sorted descending by combined_score.
        Each dict contains: id, text, metadata, score, graph_score, combined_score.
        """
        query_entities = _extract_query_entities(query)

        vec_results, graph_results = await asyncio.gather(
            self._vector_search(query, top_k, rag_filter),
            self._graph_search(query_entities, top_k),
            return_exceptions=True,
        )

        if isinstance(vec_results, Exception):
            logger.warning(f"Vector search failed in HybridRetriever: {vec_results}")
            vec_results = []
        if isinstance(graph_results, Exception):
            logger.warning(f"Graph search failed in HybridRetriever: {graph_results}")
            graph_results = []

        merged: dict[str, dict[str, Any]] = {}

        for r in vec_results:
            cid = r.get("id", "")
            if not cid:
                continue
            merged[cid] = {
                **r,
                "graph_score": 0.0,
                "combined_score": self._vw * float(r.get("score", 0.0)),
            }

        for g in graph_results:
            cid = g["chunk_id"]
            gs = float(g["graph_score"])
            if cid in merged:
                merged[cid]["graph_score"] = gs
                merged[cid]["combined_score"] = (
                    self._vw * float(merged[cid].get("score", 0.0))
                    + self._gw * gs
                )
            else:
                chunk_data = await self._fetch_chunk(cid)
                if chunk_data:
                    merged[cid] = {
                        "id": cid,
                        "text": chunk_data.get("text", ""),
                        "metadata": chunk_data.get("metadata", {}),
                        "score": 0.0,
                        "graph_score": gs,
                        "combined_score": self._gw * gs,
                    }

        results = sorted(merged.values(), key=lambda x: x["combined_score"], reverse=True)
        # Keyword re-ranking: blend combined_score (vector+graph fusion) with keyword signal
        # Preserve original vector score before blending (blend_results overwrites "score")
        for r in results:
            r["vector_score"] = r.get("score", 0.0)
        blend_input = [{**r, "score": r["combined_score"]} for r in results]
        blended = blend_results(query, blend_input)
        # Restore original vector score so chat.py can compare raw scores against broad fallback
        for b in blended:
            b["score"] = b.get("vector_score", b.get("score", 0.0))
        return blended[:top_k]

    async def _vector_search(
        self, query: str, top_k: int, rag_filter: dict | None
    ) -> list[dict]:
        return await self._rag.search(query, top_k=top_k, filter=rag_filter)

    async def _graph_search(self, entities: list[str], top_k: int) -> list[dict]:
        if not entities:
            return []
        return await asyncio.to_thread(
            self._graph.search_by_entities, entities, top_k=top_k
        )

    async def _fetch_chunk(self, chunk_id: str) -> dict | None:
        try:
            result = await asyncio.to_thread(
                self._rag.collection.get,
                ids=[chunk_id],
                include=["documents", "metadatas"],
            )
            if result and result.get("ids"):
                return {
                    "text": result["documents"][0] if result.get("documents") else "",
                    "metadata": result["metadatas"][0] if result.get("metadatas") else {},
                }
        except Exception as exc:
            logger.debug(f"Could not fetch chunk {chunk_id} from ChromaDB: {exc}")
        return None
