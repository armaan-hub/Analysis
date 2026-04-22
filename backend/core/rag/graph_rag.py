"""
Graph RAG layer.

Stores named entities extracted from document chunks into SQLite, then uses
NetworkX to traverse the entity graph and return related chunk indices.
Entity extraction uses a regex + keyword heuristic to avoid extra LLM calls.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Sequence

import networkx as nx

# ── Simple keyword-based entity recogniser ───────────────────────────────────
_ACCOUNTING_TERMS = frozenset([
    "revenue", "ebitda", "net profit", "gross margin", "cash flow",
    "balance sheet", "income statement", "vat", "tax", "audit", "ifrs", "gaap",
    "amortisation", "depreciation", "provision", "liability", "asset",
    "equity", "dividend", "working capital", "free cash flow",
])

_ENT_RE = re.compile(
    r"\b([A-Z][a-zA-Z&,\.\s]{2,40}(?:Inc|Ltd|LLC|Corp|Co|Group|Holdings|FZE|PJSC)?)\b"
)


def _extract_entities(text: str) -> list[tuple[str, str]]:
    """Return list of (name, type) tuples from raw chunk text."""
    entities: list[tuple[str, str]] = []
    lower = text.lower()
    for term in _ACCOUNTING_TERMS:
        if term in lower:
            entities.append((term.title(), "METRIC"))
    for m in _ENT_RE.finditer(text):
        name = m.group(1).strip().rstrip(",.")
        if 3 <= len(name) <= 60 and name.lower() not in _ACCOUNTING_TERMS:
            entities.append((name, "ORG"))
    # deduplicate preserving order
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for n, t in entities:
        key = n.lower()
        if key not in seen:
            seen.add(key)
            out.append((n, t))
    return out[:30]  # cap per chunk


class GraphRAG:
    """Manages entity storage and graph traversal for a single SQLite database."""

    def __init__(self, db_path: str | Path = "chatbot.db"):
        self._db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None
        if self._db_path == ":memory:":
            self._conn = sqlite3.connect(":memory:")
        self._init_db()

    # ── DB init ──────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        conn = self._connect()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id      TEXT    NOT NULL,
                chunk_index INTEGER NOT NULL,
                name        TEXT    NOT NULL,
                entity_type TEXT    NOT NULL DEFAULT 'GENERAL'
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ent_doc ON entities(doc_id)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entity_relations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id      TEXT NOT NULL,
                source_name TEXT NOT NULL,
                target_name TEXT NOT NULL,
                relation    TEXT NOT NULL DEFAULT 'RELATED_TO',
                weight      REAL NOT NULL DEFAULT 1.0
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_er_doc ON entity_relations(doc_id)")
        conn.commit()
        if self._conn is None:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        return sqlite3.connect(self._db_path)

    # ── Public API ───────────────────────────────────────────────────────────

    def extract_and_store(self, doc_id: str, chunk_index: int, text: str) -> None:
        """Extract entities from text and persist to DB."""
        entities = _extract_entities(text)
        self.store_entities(doc_id, chunk_index, entities)

    def store_entities(self, doc_id: str, chunk_index: int,
                       entities: Sequence[tuple[str, str]]) -> None:
        """Persist pre-computed entities."""
        conn = self._connect()
        conn.executemany(
            "INSERT INTO entities (doc_id, chunk_index, name, entity_type) VALUES (?,?,?,?)",
            [(doc_id, chunk_index, name, etype) for name, etype in entities],
        )
        conn.commit()
        if self._conn is None:
            conn.close()

    def get_entities_for_doc(self, doc_id: str) -> list[dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT chunk_index, name, entity_type FROM entities WHERE doc_id=?",
            (doc_id,),
        ).fetchall()
        if self._conn is None:
            conn.close()
        return [{"chunk_index": r[0], "name": r[1], "entity_type": r[2]} for r in rows]

    def build_graph(self, doc_id: str) -> nx.Graph:
        """Build an in-memory co-occurrence graph for one document."""
        rows = self.get_entities_for_doc(doc_id)
        G: nx.Graph = nx.Graph()
        chunk_to_entities: dict[int, list[str]] = {}
        for row in rows:
            chunk_to_entities.setdefault(row["chunk_index"], []).append(row["name"])
        for chunk_idx, names in chunk_to_entities.items():
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    u, v = names[i], names[j]
                    if G.has_edge(u, v):
                        G[u][v]["weight"] += 1
                    else:
                        G.add_edge(u, v, weight=1)
                    G[u][v].setdefault("chunks", set()).add(chunk_idx)
        return G

    def find_related_chunks(self, doc_id: str, seed_chunk_indices: list[int],
                            depth: int = 1) -> set[int]:
        """
        Given seed chunk indices, traverse entity co-occurrence graph to find
        related chunk indices within `depth` hops.
        Returns a set of chunk indices (excluding the seeds themselves).
        """
        rows = self.get_entities_for_doc(doc_id)
        if not rows:
            return set()

        G = self.build_graph(doc_id)
        chunk_to_entities: dict[int, list[str]] = {}
        for row in rows:
            chunk_to_entities.setdefault(row["chunk_index"], []).append(row["name"])

        seed_entities: set[str] = set()
        for idx in seed_chunk_indices:
            seed_entities.update(chunk_to_entities.get(idx, []))

        # Start with seed entities themselves (depth 0)
        related_entities: set[str] = set(seed_entities)
        
        # Traverse graph for depth hops
        frontier = set(seed_entities)
        for _ in range(depth):
            next_frontier: set[str] = set()
            for ent in frontier:
                if ent in G:
                    next_frontier.update(G.neighbors(ent))
            frontier = next_frontier - related_entities
            related_entities.update(next_frontier)

        # Find all chunks containing any of the related entities
        related_chunks: set[int] = set()
        for idx, names in chunk_to_entities.items():
            if idx not in seed_chunk_indices:  # Exclude seed chunks
                for name in names:
                    if name in related_entities:
                        related_chunks.add(idx)
                        break
        return related_chunks
