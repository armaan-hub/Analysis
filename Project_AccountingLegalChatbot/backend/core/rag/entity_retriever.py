"""Third retrieval path: entity graph-based retrieval."""
from __future__ import annotations
import logging
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.entity_graph import EntityGraph

logger = logging.getLogger(__name__)


class EntityRetriever:
    def __init__(self, graph: "EntityGraph") -> None:
        self._graph = graph

    async def get_relevant_doc_ids(self, query: str, limit: int = 5) -> list[str]:
        try:
            results = await self._graph.search_entities(query, limit=limit * 3)
            seen: list[str] = []
            for r in results:
                doc_id = r["doc_id"]
                if doc_id not in seen:
                    seen.append(doc_id)
                if len(seen) >= limit:
                    break
            return seen
        except Exception as exc:
            logger.warning("EntityRetriever.get_relevant_doc_ids failed: %s", exc)
            return []
