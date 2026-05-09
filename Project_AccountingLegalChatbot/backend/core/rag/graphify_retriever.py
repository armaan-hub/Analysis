from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from config import settings


class GraphifyRetriever:
    """Lightweight graph retriever backed by graph_store/graph.json."""

    def __init__(self, graph_json_path: str | Path | None = None):
        self.graph_json_path = Path(graph_json_path or Path(settings.graph_store_dir) / "graph.json")
        self._graph: dict[str, Any] = {}
        self._mtime_ns: int | None = None

    def _reload_if_changed(self) -> None:
        if not self.graph_json_path.exists():
            self._graph = {}
            self._mtime_ns = None
            return

        current_mtime = self.graph_json_path.stat().st_mtime_ns
        if self._mtime_ns == current_mtime:
            return

        try:
            self._graph = json.loads(self.graph_json_path.read_text(encoding="utf-8"))
            self._mtime_ns = current_mtime
        except Exception:
            self._graph = {}
            self._mtime_ns = None

    def is_available(self) -> bool:
        self._reload_if_changed()
        return bool(self._nodes())

    def _nodes(self) -> list[dict[str, Any]]:
        nodes = self._graph.get("nodes", [])
        return nodes if isinstance(nodes, list) else []

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {t for t in re.findall(r"[a-zA-Z0-9_]+", text.lower()) if len(t) > 1}

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        self._reload_if_changed()
        if not query.strip():
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scored: list[tuple[float, dict[str, Any]]] = []
        for node in self._nodes():
            if not isinstance(node, dict):
                continue
            label = str(node.get("label") or node.get("name") or node.get("id") or "").strip()
            if not label:
                continue
            haystack = " ".join(
                str(node.get(k, ""))
                for k in ("label", "name", "id", "description", "summary", "type")
            )
            tokens = self._tokenize(haystack)
            if not tokens:
                continue
            overlap = len(query_tokens & tokens)
            if overlap == 0:
                continue
            score = overlap / max(len(query_tokens), 1)
            scored.append((score, {**node, "label": label, "score": round(score, 4)}))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:top_k]]

    def get_related_source_files(self, query: str, top_k: int = 5) -> list[str]:
        results = self.search(query, top_k=top_k)
        files: list[str] = []
        seen: set[str] = set()
        for result in results:
            for key in ("source_file", "source", "file", "doc", "document"):
                value = result.get(key)
                if isinstance(value, str) and value.strip() and value not in seen:
                    seen.add(value)
                    files.append(value)
                    break
        return files


graphify_retriever = GraphifyRetriever()

