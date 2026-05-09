"""Graph API – concept-graph search via graphify knowledge graph."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Query

from core.rag.graphify_retriever import graphify_retriever

router = APIRouter(prefix="/api/documents", tags=["graph"])


@router.get("/concept-graph")
async def search_concept_graph(
    query: str = Query(..., description="Search query"),
    top_k: int = Query(10, ge=1, le=50),
) -> dict:
    """Search the graphify knowledge graph by concept."""
    if not graphify_retriever.is_available():
        return {"available": False, "results": [], "message": "Graphify graph not built yet"}
    results = graphify_retriever.search(query, top_k=top_k)
    return {
        "available": True,
        "query": query,
        "results": [asdict(r) for r in results],
        "source_files": graphify_retriever.get_related_source_files(query, top_k),
    }
