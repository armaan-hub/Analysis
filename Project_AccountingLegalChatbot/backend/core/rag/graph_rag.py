"""
Graph RAG layer.

Stores named entities extracted from document chunks into SQLite, then uses
NetworkX to traverse the entity graph and return related chunk indices.
Entity extraction uses spaCy (optional) + UAE-specific regex + keyword heuristics.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Sequence

import networkx as nx

# ── Optional spaCy ───────────────────────────────────────────────────────────
try:
    import spacy as _spacy  # type: ignore[import]
    _nlp = _spacy.load("en_core_web_sm")
    _SPACY_AVAILABLE = True
except (ImportError, OSError):
    _nlp = None
    _SPACY_AVAILABLE = False

# ── Accounting / finance keyword terms ───────────────────────────────────────
_FINANCE_TERMS = frozenset([
    "revenue", "ebitda", "net profit", "gross margin", "cash flow",
    "balance sheet", "income statement", "vat", "tax", "audit", "ifrs", "gaap",
    "amortisation", "depreciation", "provision", "asset",
    "equity", "dividend", "working capital", "free cash flow",
    # E-invoicing domain terms
    "fta", "peppol", "e-invoicing", "electronic invoice", "invoice",
])

# ── UAE legal / inheritance keyword terms ────────────────────────────────────
_LEGAL_TERMS = frozenset([
    "inheritance", "estate", "wills", "last will", "will and testament",
    "testamentary", "probate", "beneficiary",
    "beneficiaries", "succession", "heir", "heirs", "testator", "testatrix",
    "executor", "guardian", "trust", "endowment", "waqf",
    "personal status", "family law", "divorce", "custody", "alimony",
    "contract", "obligation", "liability", "penalty", "compensation",
    "corporate governance", "shareholder", "board of directors",
    "commercial", "partnership", "company law",
])

_overlap = _FINANCE_TERMS & _LEGAL_TERMS
if _overlap:
    raise ValueError(f"Term overlap between FINANCE and LEGAL sets: {_overlap}")

_ALL_KEYWORD_TERMS = _FINANCE_TERMS | _LEGAL_TERMS

# ── UAE-specific regex patterns ───────────────────────────────────────────────
_UAE_LAW_RE = re.compile(
    r"(?:"
    r"Federal\s+(?:Decree-?Law|Law)\s+No\.?\s*\d+"
    r"|Cabinet\s+(?:Decision|Resolution)\s+No\.?\s*\d+"
    r"|Ministerial\s+(?:Decision|Resolution)\s+No\.?\s*\d+"
    r"|(?:UAE\s+)?(?:Civil|Commercial|Penal|Labour)\s+(?:Code|Law)"
    r")",
    re.IGNORECASE,
)

_ARTICLE_RE = re.compile(r"\bArticle\s+\d+(?:\s*[–-]\s*\d+)?\b", re.IGNORECASE)
# Matches 0–2 decimal places (AED amounts are conventionally 2 d.p.)
_AED_RE = re.compile(r"\bAED\s*[\d,]+(?:\.\d{1,2})?\b", re.IGNORECASE)
_ORG_RE = re.compile(
    r"\b([A-Z][a-zA-Z&,\.\s]{2,40}(?:Inc|Ltd|LLC|Corp|Co|Group|Holdings|FZE|PJSC)?)\b"
)


def _extract_entities(text: str) -> list[tuple[str, str]]:
    """Return list of (name, type) tuples.

    Type tags: METRIC, LEGAL, LAW, MONEY, ORG.
    Tries spaCy first (if available), then falls back to regex + keyword heuristics.
    """
    entities: list[tuple[str, str]] = []
    lower = text.lower()

    # Finance keyword terms
    for term in _FINANCE_TERMS:
        if term in lower:
            entities.append((term.title(), "METRIC"))

    # Legal keyword terms
    for term in _LEGAL_TERMS:
        if term in lower:
            entities.append((term.title(), "LEGAL"))

    # UAE law references
    for m in _UAE_LAW_RE.finditer(text):
        entities.append((m.group(0).strip(), "LAW"))

    # Article references
    for m in _ARTICLE_RE.finditer(text):
        entities.append((m.group(0).strip(), "LAW"))

    # AED monetary amounts
    for m in _AED_RE.finditer(text):
        entities.append((m.group(0).strip(), "MONEY"))

    # spaCy NER (ORG, PERSON, DATE, GPE) — optional
    if _SPACY_AVAILABLE and _nlp is not None:
        doc = _nlp(text[:1000])  # cap at 1000 chars to control latency
        for ent in doc.ents:
            if ent.label_ in {"ORG", "PERSON", "DATE", "GPE", "LAW", "MONEY"}:
                entities.append((ent.text.strip(), ent.label_))

    # Fallback ORG regex when spaCy unavailable
    if not _SPACY_AVAILABLE:
        for m in _ORG_RE.finditer(text):
            name = m.group(1).strip().rstrip(",.")
            if 3 <= len(name) <= 60 and name.lower() not in _ALL_KEYWORD_TERMS:
                entities.append((name, "ORG"))

    # Deduplicate (case-insensitive), preserve first occurrence, cap at 40 per chunk
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for n, t in entities:
        key = n.lower().strip()
        if key and key not in seen:
            seen.add(key)
            out.append((n, t))
    return out[:40]


class GraphRAG:
    """Manages entity storage and graph traversal using SQLite + NetworkX."""

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
                entity_type TEXT    NOT NULL DEFAULT 'GENERAL',
                UNIQUE(doc_id, chunk_index, name)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ent_doc ON entities(doc_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ent_name_lower ON entities(LOWER(name))")
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
            "INSERT OR REPLACE INTO entities (doc_id, chunk_index, name, entity_type) VALUES (?,?,?,?)",
            [(doc_id, chunk_index, name, etype) for name, etype in entities],
        )
        conn.commit()
        if self._conn is None:
            conn.close()

    def _batch_store_entities(self, rows: list[tuple]) -> None:
        """Insert all (doc_id, chunk_index, name, entity_type) rows in one connection."""
        if not rows:
            return
        conn = self._connect()
        conn.executemany(
            "INSERT OR REPLACE INTO entities (doc_id, chunk_index, name, entity_type) VALUES (?,?,?,?)",
            rows,
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

    def search_by_entities(self, query_entities: list[str], top_k: int = 10) -> list[dict]:
        """Find chunks across the whole corpus that contain query entities.

        Matching is substring-based (LIKE %term%): a stored entity of
        "INVOICING SERVICE PROVIDERS" will match query term "invoicing".

        Returns list of dicts with keys: chunk_id, doc_id, chunk_index, graph_score.
        graph_score = distinct_matched_query_terms / total_query_terms (0.0–1.0).
        Results sorted descending by graph_score, limited to top_k.
        """
        if not query_entities:
            return []

        normalised = [e.lower().strip() for e in query_entities if e.strip()]
        if not normalised:
            return []

        # Build a UNION query — one branch per term — so COUNT(DISTINCT matched_term)
        # correctly scores how many query terms each chunk covers.
        union_parts = []
        params: list = []
        for term in normalised:
            union_parts.append(
                "SELECT doc_id, chunk_index, ? AS matched_term "
                "FROM entities WHERE LOWER(name) LIKE ?"
            )
            params.extend([term, f"%{term}%"])

        union_sql = " UNION ".join(union_parts)
        conn = self._connect()
        rows = conn.execute(
            f"""
            SELECT doc_id, chunk_index, COUNT(DISTINCT matched_term) AS match_count
            FROM ({union_sql})
            GROUP BY doc_id, chunk_index
            ORDER BY match_count DESC
            LIMIT ?
            """,
            params + [top_k],
        ).fetchall()
        if self._conn is None:
            conn.close()

        total = len(normalised)
        results = []
        for doc_id, chunk_index, match_count in rows:
            results.append({
                "chunk_id": f"{doc_id}_chunk_{chunk_index}",
                "doc_id": doc_id,
                "chunk_index": chunk_index,
                "graph_score": round(match_count / total, 4),
            })
        return results

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
        """Traverse entity co-occurrence graph to find related chunk indices."""
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

        related_entities: set[str] = set(seed_entities)
        frontier = set(seed_entities)
        for _ in range(depth):
            next_frontier: set[str] = set()
            for ent in frontier:
                if ent in G:
                    next_frontier.update(G.neighbors(ent))
            frontier = next_frontier - related_entities
            related_entities.update(next_frontier)

        related_chunks: set[int] = set()
        for idx, names in chunk_to_entities.items():
            if idx not in seed_chunk_indices:
                for name in names:
                    if name in related_entities:
                        related_chunks.add(idx)
                        break
        return related_chunks
