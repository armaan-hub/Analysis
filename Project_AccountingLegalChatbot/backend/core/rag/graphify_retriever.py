"""Graphify knowledge-graph retriever — augments vector search with concept-based BFS."""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_STOP_WORDS = {
    "a", "an", "the", "and", "or", "of", "in", "to", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "for", "on", "at", "by", "from", "with", "as", "it", "its",
    "this", "that", "what", "which", "who", "how", "when", "where",
}


@dataclass
class GraphResult:
    node_id: str
    label: str
    source_file: str
    relation_path: list[str]   # edge relations traversed to reach this node
    relevance_score: float
    confidence: str            # EXTRACTED | INFERRED | AMBIGUOUS


class GraphifyRetriever:
    """
    Loads graphify graph.json and provides BFS-based concept retrieval.

    The graphify graph connects legal/financial concepts extracted from
    the UAE source documents. Used to augment ChromaDB vector search.
    """

    def __init__(self, graph_path: str | Path) -> None:
        self._graph_path = Path(graph_path)
        self._graph: Any = None
        self._available = False
        self._load()

    # ── Loading ───────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._graph_path.exists():
            logger.info("[GraphifyRetriever] Graph file not found: %s", self._graph_path)
            return
        try:
            import json
            import networkx as nx
            from networkx.readwrite import json_graph

            with open(self._graph_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)

            if not data.get("nodes"):
                logger.info("[GraphifyRetriever] Graph file is empty")
                return

            self._graph = json_graph.node_link_graph(data, edges="links")
            self._available = True
            logger.info(
                "[GraphifyRetriever] Loaded graph: %d nodes, %d edges",
                self._graph.number_of_nodes(),
                self._graph.number_of_edges(),
            )
        except Exception as exc:
            logger.warning("[GraphifyRetriever] Failed to load graph: %s", exc)

    # ── Public API ────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Returns True if graph loaded successfully."""
        if not self._available and Path(self._graph_path).exists():
            self._load()
        return self._available

    def reload(self) -> bool:
        """Reload graph from disk. Call after graphify pipeline completes."""
        self._load()
        return self._available

    def search(self, query: str, top_k: int = 10) -> list[GraphResult]:
        """BFS-based concept search starting from keyword-matched nodes."""
        if not self._available or self._graph is None:
            return []

        keywords = self._tokenize(query)
        if not keywords:
            return []

        # Score every node by keyword overlap with label
        scored: list[tuple[float, Any]] = []
        for node_id, attrs in self._graph.nodes(data=True):
            label = str(attrs.get("label", "")).lower()
            score = sum(1 for kw in keywords if kw in label)
            if score > 0:
                scored.append((score, node_id))

        # Take top-3 seed nodes
        scored.sort(key=lambda x: x[0], reverse=True)
        seed_nodes = [nid for _, nid in scored[:3]]

        # BFS from each seed, collecting results
        seen_ids: set[str] = set()
        results: list[GraphResult] = []

        for seed in seed_nodes:
            bfs_results = self._bfs(seed, max_depth=3, keywords=keywords)
            for r in bfs_results:
                if r.node_id not in seen_ids:
                    seen_ids.add(r.node_id)
                    results.append(r)

        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results[:top_k]

    def get_related_source_files(self, query: str, top_k: int = 10) -> list[str]:
        """Return unique source_file paths from graph search results."""
        results = self.search(query, top_k=top_k)
        seen: list[str] = []
        for r in results:
            if r.source_file and r.source_file not in seen:
                seen.append(r.source_file)
        return seen

    def get_concept_path(self, concept_a: str, concept_b: str) -> list[str]:
        """Find shortest label path between two concepts. Returns [] if no path."""
        if not self._available or self._graph is None:
            return []
        try:
            import networkx as nx
            node_a = self._find_node_by_label(concept_a)
            node_b = self._find_node_by_label(concept_b)
            if node_a is None or node_b is None:
                return []
            path = nx.shortest_path(self._graph, source=node_a, target=node_b)
            return [str(self._graph.nodes[n].get("label", n)) for n in path]
        except Exception:
            return []

    # ── Internals ─────────────────────────────────────────────────────

    def _tokenize(self, text: str) -> list[str]:
        tokens = [t.lower().strip(".,;:") for t in text.split()]
        return [t for t in tokens if t and t not in _STOP_WORDS and len(t) > 1]

    def _bfs(self, start_node: Any, max_depth: int, keywords: list[str]) -> list[GraphResult]:
        """BFS up to max_depth, returning GraphResult for each visited node."""
        results: list[GraphResult] = []
        visited: set[Any] = set()
        # queue entries: (node_id, depth, relation_path)
        queue: deque[tuple[Any, int, list[str]]] = deque()
        queue.append((start_node, 0, []))
        visited.add(start_node)

        while queue:
            node_id, depth, rel_path = queue.popleft()
            attrs = self._graph.nodes[node_id]
            label = str(attrs.get("label", ""))
            source_file = str(attrs.get("source_file", ""))
            confidence = str(attrs.get("confidence", "EXTRACTED"))

            # Score: keyword matches in label + proximity bonus (closer = higher)
            score = sum(1.0 for kw in keywords if kw in label.lower())
            score += max(0.0, (max_depth - depth) * 0.1)  # proximity bonus

            results.append(GraphResult(
                node_id=str(node_id),
                label=label,
                source_file=source_file,
                relation_path=list(rel_path),
                relevance_score=round(score, 3),
                confidence=confidence,
            ))

            if depth < max_depth:
                for neighbor in self._graph.neighbors(node_id):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        edge_data = self._graph.get_edge_data(node_id, neighbor) or {}
                        relation = str(edge_data.get("relation", "related_to"))
                        queue.append((neighbor, depth + 1, rel_path + [relation]))

        return results

    def _find_node_by_label(self, label: str) -> Any | None:
        label_lower = label.lower()
        for node_id, attrs in self._graph.nodes(data=True):
            if str(attrs.get("label", "")).lower() == label_lower:
                return node_id
        return None


# ── Singleton ─────────────────────────────────────────────────────────

_graph_path = str(Path(__file__).parent.parent.parent / "graph_store" / "graphify_graph.json")
graphify_retriever = GraphifyRetriever(_graph_path)
