"""
Hybrid retriever: combines ChromaDB vector results with graph-expanded chunks.

Workflow:
1. Vector search via RAGEngine for top_k results.
2. Extract chunk indices from vector results.
3. Use GraphRAG to find related chunks via entity co-occurrence.
4. Fetch graph-expanded chunks from ChromaDB by ID.
5. Merge, deduplicate by chunk ID, sort by score descending.
"""
from __future__ import annotations

from typing import Any


class HybridRetriever:
    def __init__(self, rag_engine, graph_rag,
                 graph_expansion_depth: int = 1,
                 graph_weight: float = 0.6):
        self._rag = rag_engine
        self._graph = graph_rag
        self._depth = graph_expansion_depth
        self._graph_weight = graph_weight

    def retrieve(self, query: str, doc_ids: list[str] | None = None,
                 top_k: int = 8) -> list[dict[str, Any]]:
        """
        Return deduplicated, re-ranked list of chunk result dicts.
        Each result: {id, document, metadata, score}
        """
        # 1. Vector search
        vec_filter = {"doc_id": {"$in": doc_ids}} if doc_ids else None
        raw_results = self._rag.search(query, top_k=top_k, filter=vec_filter)

        seen_ids: set[str] = set()
        merged: list[dict[str, Any]] = []

        for r in raw_results:
            rid = r.get("id") or r.get("metadata", {}).get("source", "")
            score = 1.0 - float(r.get("distance", 0.5))
            merged.append({**r, "id": rid, "score": score})
            seen_ids.add(rid)

        # 2. Graph expansion
        if doc_ids:
            for doc_id in doc_ids:
                seed_indices = [
                    int(r["id"].split("_chunk_")[-1])
                    for r in merged
                    if r.get("metadata", {}).get("doc_id") == doc_id
                    and "_chunk_" in r.get("id", "")
                ]
                if not seed_indices:
                    continue
                related_indices = self._graph.find_related_chunks(
                    doc_id, seed_indices, depth=self._depth
                )
                extra_ids = [f"{doc_id}_chunk_{i}" for i in related_indices
                             if f"{doc_id}_chunk_{i}" not in seen_ids]
                if not extra_ids:
                    continue
                try:
                    fetched = self._rag.collection.get(
                        ids=extra_ids, include=["documents", "metadatas"]
                    )
                    for cid, text, meta in zip(
                        fetched["ids"], fetched["documents"], fetched["metadatas"]
                    ):
                        if cid not in seen_ids:
                            merged.append({
                                "id": cid,
                                "document": text,
                                "metadata": meta,
                                "score": self._graph_weight,
                            })
                            seen_ids.add(cid)
                except Exception:
                    pass

        # 3. Sort by score descending
        merged.sort(key=lambda r: r["score"], reverse=True)
        return merged[:top_k]
