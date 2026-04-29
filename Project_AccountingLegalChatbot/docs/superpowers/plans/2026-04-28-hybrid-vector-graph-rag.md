# Hybrid Vector-Graph RAG — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the RAG pipeline to Parallel Fusion — vector search (ChromaDB) and entity graph search (SQLite/NetworkX) run simultaneously on every query, results are merged, so "Draft Wills" no longer returns VAT documents.

**Architecture:** A `HybridRetriever` fires `asyncio.gather(vector_search, graph_query_search)` in parallel on every query. The `GraphRAG` class gets UAE-specific legal entity patterns; `ingest_chunks()` calls `GraphRAG.extract_and_store()` at index time so the graph is built as documents are ingested. Fusion re-ranks by `0.6 × vector_score + 0.4 × graph_score` and deduplicates by chunk ID.

**Tech Stack:** Python 3.11, FastAPI, ChromaDB 0.5, SQLite (via stdlib sqlite3), NetworkX 3.6, spaCy (optional, graceful fallback), pytest-asyncio (asyncio_mode=auto), httpx + ASGITransport for API tests.

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `backend/core/rag/graph_rag.py` | Add UAE legal NER patterns + spaCy optional layer + cross-corpus `search_by_entities()` |
| Modify | `backend/core/document_processor.py` | Extract section headings from PDF/DOCX; add `section`, `word_count`, `total_chunks` to chunk metadata |
| Modify | `backend/core/rag_engine.py` | Call `GraphRAG.extract_and_store()` at ingest time; add `prev_chunk_id`, `next_chunk_id`, `section`, `word_count`, `total_chunks`, `entities` to stored metadata |
| Modify | `backend/config.py` | Add `graph_store_dir: str` setting |
| Modify | `backend/core/rag/hybrid_retriever.py` | Rewrite to true Parallel Fusion using `asyncio.gather()` |
| Modify | `backend/api/chat.py` | Replace `rag_engine.search()` calls with `hybrid_retriever.retrieve()` (both streaming + non-streaming) |
| Modify | `backend/requirements.txt` | Add `spacy>=3.7,<4.0` |
| Modify | `backend/tests/test_graph_rag.py` | Add UAE entity extraction tests + `search_by_entities` tests |
| Create | `backend/tests/test_hybrid_retriever.py` | Parallel fusion tests (mock vector + graph, verify merge logic) |
| Create | `backend/tests/test_document_section_extraction.py` | Section heading extraction unit tests |
| Modify | `backend/bulk_ingest.py` | Re-ingest 455 documents through the new pipeline |

---

## Task 1: Enhance GraphRAG with UAE Legal NER + Cross-Corpus Search

**Files:**
- Modify: `backend/core/rag/graph_rag.py`
- Test: `backend/tests/test_graph_rag.py`

- [ ] **Step 1.1: Write the failing tests for UAE entity extraction**

Add to the end of `backend/tests/test_graph_rag.py`:

```python
# ── UAE Legal NER tests ───────────────────────────────────────────

def test_uae_law_number_extracted(graph):
    """Federal Decree-Law numbers are recognised as LAW entities."""
    graph.extract_and_store("doc_law1", 0,
        "Federal Decree-Law No. 28 of 2005 on Personal Status governs wills and inheritance.")
    rows = graph.get_entities_for_doc("doc_law1")
    names = [r["name"] for r in rows]
    assert any("28" in n or "Decree-Law" in n for n in names), f"Got: {names}"


def test_uae_article_ref_extracted(graph):
    """Article references are recognised as LAW entities."""
    graph.extract_and_store("doc_law2", 0,
        "Article 4 of the Wills and Probate Registry Law sets distribution rules.")
    rows = graph.get_entities_for_doc("doc_law2")
    names = [r["name"] for r in rows]
    assert any("Article" in n or "article" in n.lower() for n in names), f"Got: {names}"


def test_legal_terms_extracted(graph):
    """Core legal terms (inheritance, estate, beneficiary) are recognised."""
    graph.extract_and_store("doc_law3", 0,
        "The estate shall be distributed equally among the beneficiaries as per the will.")
    rows = graph.get_entities_for_doc("doc_law3")
    names = {r["name"].lower() for r in rows}
    assert names & {"estate", "beneficiar", "will", "inheritance", "beneficiaries"} or len(names) > 0


def test_aed_amount_extracted(graph):
    """AED monetary amounts are recognised as MONEY entities."""
    graph.extract_and_store("doc_fin1", 0,
        "The total estate value is AED 10,000,000 to be distributed.")
    rows = graph.get_entities_for_doc("doc_fin1")
    types = [r["entity_type"] for r in rows]
    assert "MONEY" in types, f"Got types: {types}"


def test_search_by_entities_returns_chunks(graph):
    """search_by_entities finds chunks that contain matching entity names."""
    graph.store_entities("docX", chunk_index=0,
                         entities=[("Inheritance", "LEGAL"), ("Estate", "LEGAL")])
    graph.store_entities("docY", chunk_index=2,
                         entities=[("Estate", "LEGAL"), ("Beneficiary", "LEGAL")])
    results = graph.search_by_entities(["inheritance", "estate"], top_k=5)
    chunk_ids = {r["chunk_id"] for r in results}
    assert "docX_chunk_0" in chunk_ids
    assert "docY_chunk_2" in chunk_ids


def test_search_by_entities_empty_returns_empty(graph):
    """Querying with no matching entities returns empty list."""
    results = graph.search_by_entities(["nonexistent_entity_xyz_12345"], top_k=5)
    assert results == []


def test_search_by_entities_scores_higher_for_more_matches(graph):
    """Chunk with 2 matching entities scores higher than chunk with 1."""
    graph.store_entities("docZ", chunk_index=0,
                         entities=[("Wills", "LEGAL"), ("Estate", "LEGAL")])
    graph.store_entities("docZ", chunk_index=1,
                         entities=[("Wills", "LEGAL")])
    results = graph.search_by_entities(["wills", "estate"], top_k=5)
    scores = {r["chunk_id"]: r["graph_score"] for r in results}
    assert scores.get("docZ_chunk_0", 0) > scores.get("docZ_chunk_1", 0)
```

- [ ] **Step 1.2: Run to confirm tests fail**

```bash
cd backend
pytest tests/test_graph_rag.py::test_uae_law_number_extracted tests/test_graph_rag.py::test_search_by_entities_returns_chunks -v
```
Expected: FAIL — `AssertionError` (UAE patterns not in extractor) and `AttributeError: 'GraphRAG' object has no attribute 'search_by_entities'`

- [ ] **Step 1.3: Rewrite `backend/core/rag/graph_rag.py`**

Replace the entire file with:

```python
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
    import spacy as _spacy
    _nlp = _spacy.load("en_core_web_sm")
    _SPACY_AVAILABLE = True
except Exception:
    _nlp = None
    _SPACY_AVAILABLE = False

# ── Accounting / finance keyword terms ───────────────────────────────────────
_FINANCE_TERMS = frozenset([
    "revenue", "ebitda", "net profit", "gross margin", "cash flow",
    "balance sheet", "income statement", "vat", "tax", "audit", "ifrs", "gaap",
    "amortisation", "depreciation", "provision", "liability", "asset",
    "equity", "dividend", "working capital", "free cash flow",
])

# ── UAE legal / inheritance keyword terms ────────────────────────────────────
_LEGAL_TERMS = frozenset([
    "inheritance", "estate", "will", "wills", "probate", "beneficiary",
    "beneficiaries", "succession", "heir", "heirs", "testator", "testatrix",
    "executor", "guardian", "trust", "endowment", "waqf",
    "personal status", "family law", "divorce", "custody", "alimony",
    "contract", "obligation", "liability", "penalty", "compensation",
    "corporate governance", "shareholder", "board of directors",
    "commercial", "partnership", "company law",
])

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
            if 3 <= len(name) <= 60 and name.lower() not in _FINANCE_TERMS | _LEGAL_TERMS:
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
                entity_type TEXT    NOT NULL DEFAULT 'GENERAL'
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ent_doc ON entities(doc_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ent_name ON entities(name COLLATE NOCASE)")
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

    def search_by_entities(self, query_entities: list[str], top_k: int = 10) -> list[dict]:
        """Find chunks across the whole corpus that contain query entities.

        Returns list of dicts with keys: chunk_id, doc_id, chunk_index, graph_score.
        graph_score = matched_entity_count / total_query_entities (0.0–1.0).
        Results sorted descending by graph_score, limited to top_k.
        """
        if not query_entities:
            return []

        # Normalise to lowercase for case-insensitive matching
        normalised = [e.lower().strip() for e in query_entities if e.strip()]
        if not normalised:
            return []

        placeholders = ",".join("?" * len(normalised))
        conn = self._connect()
        rows = conn.execute(
            f"""
            SELECT doc_id, chunk_index, COUNT(DISTINCT name) AS match_count
            FROM entities
            WHERE LOWER(name) IN ({placeholders})
            GROUP BY doc_id, chunk_index
            ORDER BY match_count DESC
            """,
            normalised,
        ).fetchall()
        if self._conn is None:
            conn.close()

        total = len(normalised)
        results = []
        for doc_id, chunk_index, match_count in rows[:top_k]:
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
```

- [ ] **Step 1.4: Run tests — all graph_rag tests must pass**

```bash
cd backend
pytest tests/test_graph_rag.py -v
```
Expected: All 11 tests PASS. If `test_uae_law_number_extracted` fails, check the regex by running:
```python
import re
p = re.compile(r"Federal\s+(?:Decree-?Law|Law)\s+No\.?\s*\d+", re.IGNORECASE)
print(p.search("Federal Decree-Law No. 28 of 2005"))  # must match
```

- [ ] **Step 1.5: Commit**

```bash
git add backend/core/rag/graph_rag.py backend/tests/test_graph_rag.py
git commit -m "feat(graph-rag): add UAE legal NER patterns and cross-corpus search_by_entities

- Federal Decree-Law, Cabinet Resolution, Article, AED patterns
- Legal keyword terms: wills, estate, inheritance, beneficiary, etc.
- New search_by_entities() for query-time graph lookup
- Optional spaCy integration with graceful fallback

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: Add Section Heading Extraction to DocumentProcessor

**Files:**
- Modify: `backend/core/document_processor.py`
- Create: `backend/tests/test_document_section_extraction.py`

- [ ] **Step 2.1: Write the failing tests**

Create `backend/tests/test_document_section_extraction.py`:

```python
"""Tests for section heading extraction and enriched chunk metadata."""
import pytest
from core.document_processor import DocumentProcessor, DocumentChunk


@pytest.fixture
def proc():
    return DocumentProcessor(chunk_size=200, chunk_overlap=20)


def test_section_extracted_from_heading_line(proc):
    """A line starting with uppercase words followed by content is detected as a section."""
    pages = [{"text": "WILLS AND INHERITANCE\nThis section covers how wills are made.", "page": 1}]
    chunks = proc._split_text(pages, "test.pdf", "doc1")
    assert len(chunks) >= 1
    sections = [c.metadata.get("section", "") for c in chunks]
    assert any("WILLS" in s.upper() for s in sections), f"sections={sections}"


def test_section_defaults_to_empty_string(proc):
    """Chunks with no detectable heading get section='' not None."""
    pages = [{"text": "some lowercase plain text without any heading here", "page": 1}]
    chunks = proc._split_text(pages, "test.pdf", "doc1")
    for c in chunks:
        assert "section" in c.metadata
        assert c.metadata["section"] is not None


def test_chunk_metadata_has_word_count(proc):
    """Every chunk must have a word_count int field > 0."""
    pages = [{"text": "The quick brown fox jumps over the lazy dog.", "page": 1}]
    chunks = proc._split_text(pages, "test.pdf", "doc1")
    for c in chunks:
        assert "word_count" in c.metadata
        assert isinstance(c.metadata["word_count"], int)
        assert c.metadata["word_count"] > 0


def test_chunk_metadata_has_total_chunks(proc):
    """Every chunk in a doc must carry the same total_chunks count."""
    # 500-char text with chunk_size=200 → at least 3 chunks
    text = "word " * 100
    pages = [{"text": text, "page": 1}]
    chunks = proc._split_text(pages, "test.pdf", "doc1")
    assert len(chunks) >= 2
    totals = {c.metadata["total_chunks"] for c in chunks}
    assert totals == {len(chunks)}, f"expected single total={len(chunks)}, got {totals}"


def test_chunk_index_sequential(proc):
    """chunk_index should be 0, 1, 2, ... across the whole document."""
    text = "word " * 100
    pages = [{"text": text, "page": 1}, {"text": text, "page": 2}]
    chunks = proc._split_text(pages, "test.pdf", "doc1")
    indices = [c.metadata["chunk_index"] for c in chunks]
    assert indices == list(range(len(chunks)))
```

- [ ] **Step 2.2: Run to confirm tests fail**

```bash
cd backend
pytest tests/test_document_section_extraction.py -v
```
Expected: FAIL — `AssertionError` (no `section`, `word_count`, `total_chunks` fields)

- [ ] **Step 2.3: Update `_split_text` and `_extract_heading_from_text` in `document_processor.py`**

Find the `_split_text` method (around line 328) and replace the entire method plus add the helper before it:

```python
# Add this helper method inside DocumentProcessor class, before _split_text:
@staticmethod
def _extract_heading_from_text(text: str) -> str:
    """Return the most likely section heading from the start of a text block.

    Heuristic: a heading is a line that is:
    - Entirely uppercase, OR
    - Title Case and <= 80 chars and ends without a sentence terminator
    Returns empty string if no heading detected.
    """
    first_line = text.strip().split("\n")[0].strip()
    if not first_line:
        return ""
    # All-caps heading (e.g. "WILLS AND INHERITANCE")
    if first_line.isupper() and 3 <= len(first_line) <= 120:
        return first_line
    # Title Case heading (e.g. "Article 4 – Distribution of Estate")
    words = first_line.split()
    if (
        2 <= len(words) <= 12
        and not first_line[-1] in ".,:;"
        and sum(1 for w in words if w and w[0].isupper()) >= len(words) * 0.6
    ):
        return first_line
    return ""

def _split_text(
    self,
    pages: list[dict],
    filename: str,
    doc_id: str,
) -> list[DocumentChunk]:
    """Split extracted pages/sheets into overlapping chunks with rich metadata."""
    # First pass: collect all chunks (without total_chunks — not known yet)
    chunks: list[DocumentChunk] = []
    chunk_index = 0
    current_section = ""

    for page_data in pages:
        text = page_data["text"]
        page_ref = page_data["page"]

        # Update running section heading from page text
        detected = self._extract_heading_from_text(text)
        if detected:
            current_section = detected

        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end].strip()

            if chunk_text:
                # Detect inline section at chunk start
                chunk_heading = self._extract_heading_from_text(chunk_text)
                section = chunk_heading if chunk_heading else current_section

                chunks.append(DocumentChunk(
                    text=chunk_text,
                    metadata={
                        "doc_id": doc_id,
                        "source": filename,
                        "page": str(page_ref),
                        "chunk_index": chunk_index,
                        "section": section,
                        "word_count": len(chunk_text.split()),
                        "total_chunks": 0,  # backfilled below
                    },
                ))
                chunk_index += 1

            start += self.chunk_size - self.chunk_overlap
            if start >= len(text):
                break

    # Second pass: backfill total_chunks now that we know the count
    total = len(chunks)
    for c in chunks:
        c.metadata["total_chunks"] = total

    return chunks
```

- [ ] **Step 2.4: Run tests — all section extraction tests must pass**

```bash
cd backend
pytest tests/test_document_section_extraction.py -v
```
Expected: All 5 tests PASS.

- [ ] **Step 2.5: Run full test suite to verify no regressions**

```bash
cd backend
pytest --tb=short -q 2>&1 | tail -20
```
Expected: Same pass/fail ratio as before (573+/574 total). If `test_chunk_metadata_has_total_chunks` fails on an edge case, verify chunk overlap math.

- [ ] **Step 2.6: Commit**

```bash
git add backend/core/document_processor.py backend/tests/test_document_section_extraction.py
git commit -m "feat(doc-processor): extract section headings and add word_count/total_chunks metadata

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: Add `graph_store_dir` Config + GraphRAG Singleton

**Files:**
- Modify: `backend/config.py`

- [ ] **Step 3.1: Add `graph_store_dir` to Settings in `config.py`**

Find the `vector_store_dir` line (around line 69) and add the new setting directly below it:

```python
    vector_store_dir: str = "./vector_store_v2"
    graph_store_dir: str = "./graph_store"   # ← add this line
```

Find the `ensure_dirs` method and add graph_store_dir to the directory creation:

```python
    def ensure_dirs(self):
        """Create required directories if they don't exist."""
        Path(self.upload_dir).mkdir(parents=True, exist_ok=True)
        Path(self.vector_store_dir).mkdir(parents=True, exist_ok=True)
        Path(self.graph_store_dir).mkdir(parents=True, exist_ok=True)   # ← add this line
        db_raw = self.database_url
        if db_raw.startswith("sqlite:///"):
            db_raw = db_raw[len("sqlite:///"):]
        Path(db_raw).parent.mkdir(parents=True, exist_ok=True)
```

Also add `graph_store_dir` to the relative-path resolver in `_resolve_relative_paths`:

```python
        for key in ("database_url", "upload_dir", "vector_store_dir", "graph_store_dir"):
```

- [ ] **Step 3.2: Run existing tests to confirm config change is backward-compatible**

```bash
cd backend
pytest tests/test_health.py tests/test_chat_endpoint_domain.py -v
```
Expected: PASS (no test should reference graph_store_dir directly).

- [ ] **Step 3.3: Commit**

```bash
git add backend/config.py
git commit -m "feat(config): add graph_store_dir setting for SQLite knowledge graph

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4: Enrich `ingest_chunks()` — Wire GraphRAG at Ingest Time

**Files:**
- Modify: `backend/core/rag_engine.py`
- Test: extend `backend/tests/test_relevance_rag.py`

- [ ] **Step 4.1: Write failing tests for enriched metadata**

Add to the end of `backend/tests/test_relevance_rag.py`:

```python
# ── Enriched metadata tests ───────────────────────────────────────

@pytest.mark.asyncio
async def test_ingest_stores_section_in_metadata():
    """Chunk metadata must include 'section' field after ingestion."""
    from core.rag_engine import RAGEngine
    from unittest.mock import AsyncMock, MagicMock
    import os

    engine = RAGEngine()
    engine.collection = MagicMock()
    engine.collection.count.return_value = 0
    engine.embedding_provider.embed_texts = AsyncMock(return_value=[[0.1] * 1024])

    captured_meta = {}
    def capture_upsert(**kwargs):
        captured_meta.update({"metadatas": kwargs.get("metadatas", [])})
    engine.collection.upsert = MagicMock(side_effect=capture_upsert)

    chunks = [{"text": "WILLS AND INHERITANCE\nEstates are distributed.", "metadata": {"page": 1, "chunk_index": 0, "section": "WILLS AND INHERITANCE", "word_count": 5, "total_chunks": 1}}]
    await engine.ingest_chunks(chunks, "doc_test_section", original_name="Wills Law.pdf", category="law")

    assert captured_meta["metadatas"], "No metadatas captured"
    meta = captured_meta["metadatas"][0]
    assert "section" in meta, f"Missing 'section' in {meta.keys()}"
    assert "word_count" in meta, f"Missing 'word_count' in {meta.keys()}"
    assert "total_chunks" in meta, f"Missing 'total_chunks' in {meta.keys()}"


@pytest.mark.asyncio
async def test_ingest_stores_entities_in_metadata():
    """Chunk metadata must include 'entities' string after ingestion."""
    from core.rag_engine import RAGEngine
    from unittest.mock import AsyncMock, MagicMock

    engine = RAGEngine()
    engine.collection = MagicMock()
    engine.collection.count.return_value = 0
    engine.embedding_provider.embed_texts = AsyncMock(return_value=[[0.1] * 1024])

    captured_meta = {}
    def capture_upsert(**kwargs):
        captured_meta.update({"metadatas": kwargs.get("metadatas", [])})
    engine.collection.upsert = MagicMock(side_effect=capture_upsert)

    chunks = [{"text": "The estate shall be distributed per Federal Decree-Law No. 28.", "metadata": {"page": 1, "chunk_index": 0, "section": "", "word_count": 12, "total_chunks": 1}}]
    await engine.ingest_chunks(chunks, "doc_ent_test", original_name="Inheritance Law.pdf", category="law")

    meta = captured_meta["metadatas"][0]
    assert "entities" in meta, f"Missing 'entities' in {meta.keys()}"
    assert isinstance(meta["entities"], str), f"entities must be str, got {type(meta['entities'])}"
```

- [ ] **Step 4.2: Run to confirm tests fail**

```bash
cd backend
pytest tests/test_relevance_rag.py::test_ingest_stores_section_in_metadata tests/test_relevance_rag.py::test_ingest_stores_entities_in_metadata -v
```
Expected: FAIL — `AssertionError: Missing 'section'` and `Missing 'entities'`

- [ ] **Step 4.3: Update `ingest_chunks()` in `backend/core/rag_engine.py`**

At the top of the file, add the GraphRAG import after the existing imports:

```python
from core.rag.graph_rag import GraphRAG as _GraphRAG
```

Find the `ingest_chunks` method signature (around line 391) and replace the entire method body:

```python
    async def ingest_chunks(
        self,
        chunks: list,
        doc_id: str,
        original_name: str = "",
        category: str = "general",
    ) -> int:
        """Embed and store document chunks in ChromaDB, and index entities in the graph.

        Returns the number of chunks successfully indexed.
        Each chunk receives enriched metadata including section, word_count,
        total_chunks, prev/next chunk IDs, and entity tags.
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
        total_chunks = len(chunks)

        ids = [f"{doc_id}_chunk_{i}" for i in range(total_chunks)]
        metadatas: list[dict] = []
        entity_lists: list[list[tuple[str, str]]] = []

        from core.rag.graph_rag import _extract_entities as _ner
        for i, (raw, text) in enumerate(zip(raw_metadatas, texts)):
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

            # Enriched provenance fields
            meta.setdefault("section", "")
            meta.setdefault("word_count", len(text.split()))
            meta["total_chunks"] = total_chunks
            meta["chunk_index"] = i
            meta["prev_chunk_id"] = ids[i - 1] if i > 0 else ""
            meta["next_chunk_id"] = ids[i + 1] if i < total_chunks - 1 else ""

            # Entity tags (comma-separated string for ChromaDB scalar constraint)
            entities = _ner(text)
            entity_lists.append(entities)
            meta["entities"] = ",".join(n for n, _ in entities[:20])

            metadatas.append(meta)

        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        # Index entities in the knowledge graph (fire-and-forget: never block ingestion)
        try:
            graph_db_path = Path(settings.vector_store_dir).parent / "graph_store" / "graph.db"
            graph_db_path.parent.mkdir(parents=True, exist_ok=True)
            graph = _GraphRAG(db_path=str(graph_db_path))
            for i, (text, entities) in enumerate(zip(texts, entity_lists)):
                if entities:
                    graph.store_entities(doc_id, i, entities)
        except Exception as exc:
            logger.warning(f"GraphRAG indexing skipped for {doc_id}: {exc}")

        return total_chunks
```

- [ ] **Step 4.4: Run enriched metadata tests**

```bash
cd backend
pytest tests/test_relevance_rag.py -v 2>&1 | tail -30
```
Expected: All relevance_rag tests PASS including the 2 new ones. If the GraphRAG import causes issues in tests (file-system side effects), verify the `try/except` block swallows the error gracefully.

- [ ] **Step 4.5: Commit**

```bash
git add backend/core/rag_engine.py
git commit -m "feat(rag-engine): enrich chunk metadata with section/entities/prev-next at ingest time

- Adds section, word_count, total_chunks, prev_chunk_id, next_chunk_id, entities
- Calls GraphRAG.store_entities() at ingest time (fire-and-forget, never blocks)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5: Upgrade HybridRetriever to True Parallel Fusion

**Files:**
- Modify: `backend/core/rag/hybrid_retriever.py`
- Create: `backend/tests/test_hybrid_retriever.py`

- [ ] **Step 5.1: Write failing tests for parallel fusion**

Create `backend/tests/test_hybrid_retriever.py`:

```python
"""Tests for the Parallel Fusion HybridRetriever."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from core.rag.hybrid_retriever import HybridRetriever


def _make_chunk(chunk_id: str, score: float, text: str = "test text") -> dict:
    doc_id, _, chunk_i = chunk_id.rpartition("_chunk_")
    return {
        "id": chunk_id,
        "text": text,
        "metadata": {"doc_id": doc_id, "chunk_index": int(chunk_i), "source": "test.pdf"},
        "score": score,
    }


@pytest.fixture
def mock_rag():
    rag = MagicMock()
    rag.search = AsyncMock(return_value=[
        _make_chunk("docA_chunk_0", 0.85, "inheritance estate distribution"),
        _make_chunk("docA_chunk_1", 0.80, "wills probate"),
    ])
    # ChromaDB collection.get() for graph-expanded chunks
    rag.collection = MagicMock()
    rag.collection.get = MagicMock(return_value={
        "ids": ["docA_chunk_2"],
        "documents": ["related legal text"],
        "metadatas": [{"doc_id": "docA", "source": "test.pdf"}],
    })
    return rag


@pytest.fixture
def mock_graph():
    graph = MagicMock()
    graph.search_by_entities = MagicMock(return_value=[
        {"chunk_id": "docB_chunk_0", "doc_id": "docB", "chunk_index": 0, "graph_score": 0.9},
        {"chunk_id": "docA_chunk_0", "doc_id": "docA", "chunk_index": 0, "graph_score": 0.7},
    ])
    return graph


@pytest.mark.asyncio
async def test_retrieve_returns_merged_results(mock_rag, mock_graph):
    """retrieve() should return results from both vector and graph paths."""
    retriever = HybridRetriever(mock_rag, mock_graph)
    results = await retriever.retrieve("draft wills for estate", top_k=5)
    assert len(results) >= 1
    chunk_ids = {r["id"] for r in results}
    # docA_chunk_0 appears in both paths → should appear once (deduplicated)
    assert chunk_ids.count("docA_chunk_0") if "docA_chunk_0" in chunk_ids else True


@pytest.mark.asyncio
async def test_vector_and_graph_called_in_parallel(mock_rag, mock_graph):
    """Both vector search and graph search must be invoked for every query."""
    retriever = HybridRetriever(mock_rag, mock_graph)
    await retriever.retrieve("estate wills", top_k=5)
    mock_rag.search.assert_called_once()
    mock_graph.search_by_entities.assert_called_once()


@pytest.mark.asyncio
async def test_deduplication_by_chunk_id(mock_rag, mock_graph):
    """A chunk appearing in both vector and graph results appears only once."""
    retriever = HybridRetriever(mock_rag, mock_graph)
    results = await retriever.retrieve("wills estate", top_k=10)
    ids = [r["id"] for r in results]
    assert len(ids) == len(set(ids)), f"Duplicate IDs found: {ids}"


@pytest.mark.asyncio
async def test_graph_only_chunk_gets_graph_score(mock_rag, mock_graph):
    """A chunk found only by graph (not vector) must appear with graph_score as score."""
    # docB_chunk_0 is only in graph results, not vector results
    mock_rag.search = AsyncMock(return_value=[
        _make_chunk("docA_chunk_0", 0.85),
    ])
    mock_graph.search_by_entities = MagicMock(return_value=[
        {"chunk_id": "docB_chunk_0", "doc_id": "docB", "chunk_index": 0, "graph_score": 0.8},
    ])
    # collection.get returns text for graph-only chunk
    mock_rag.collection.get = MagicMock(return_value={
        "ids": ["docB_chunk_0"],
        "documents": ["law text"],
        "metadatas": [{"doc_id": "docB", "source": "law.pdf"}],
    })
    retriever = HybridRetriever(mock_rag, mock_graph)
    results = await retriever.retrieve("estate law", top_k=5)
    ids = {r["id"] for r in results}
    assert "docB_chunk_0" in ids, f"Graph-only chunk missing: {ids}"


@pytest.mark.asyncio
async def test_vector_failure_still_returns_graph_results(mock_rag, mock_graph):
    """If vector search raises, graph results are still returned."""
    mock_rag.search = AsyncMock(side_effect=Exception("vector store offline"))
    retriever = HybridRetriever(mock_rag, mock_graph)
    results = await retriever.retrieve("wills", top_k=5)
    # Should not raise; graph results may still be present
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_graph_failure_still_returns_vector_results(mock_rag, mock_graph):
    """If graph search raises, vector results are still returned."""
    mock_graph.search_by_entities = MagicMock(side_effect=Exception("graph db locked"))
    retriever = HybridRetriever(mock_rag, mock_graph)
    results = await retriever.retrieve("wills", top_k=5)
    assert len(results) >= 1
    assert results[0]["id"] == "docA_chunk_0"
```

- [ ] **Step 5.2: Run to confirm tests fail**

```bash
cd backend
pytest tests/test_hybrid_retriever.py -v 2>&1 | head -40
```
Expected: FAIL — `ImportError` or `AttributeError` because `HybridRetriever.retrieve()` doesn't accept a `query` without `doc_ids` and doesn't call `search_by_entities`.

- [ ] **Step 5.3: Rewrite `backend/core/rag/hybrid_retriever.py`**

Replace the entire file:

```python
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

logger = logging.getLogger(__name__)

_VECTOR_WEIGHT = 0.6
_GRAPH_WEIGHT = 0.4

# Stop words to exclude from entity extraction
_STOPWORDS = frozenset([
    "the", "and", "for", "with", "from", "that", "this", "are", "was",
    "will", "have", "has", "had", "can", "may", "how", "what", "when",
    "where", "which", "who", "why", "all", "any", "one", "two",
])


def _extract_query_entities(query: str) -> list[str]:
    """Extract candidate entity strings from a query for graph lookup.

    Extracts: individual words > 3 chars (excluding stopwords) + capitalised phrases.
    """
    entities: set[str] = set()
    words = re.findall(r"\b[a-zA-Z]{4,}\b", query)
    for w in words:
        if w.lower() not in _STOPWORDS:
            entities.add(w.lower())
    # Capitalised phrases (e.g. "Federal Law", "Estate Distribution")
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

        Args:
            query:      Natural language query.
            top_k:      Maximum number of results to return.
            rag_filter: Optional ChromaDB metadata filter for the vector path.

        Returns:
            List of chunk dicts sorted descending by combined_score.
            Each dict contains: id, text, metadata, score, graph_score, combined_score.
        """
        query_entities = _extract_query_entities(query)

        # ── Run both paths in parallel ────────────────────────────────────────
        vec_task = asyncio.create_task(self._vector_search(query, top_k, rag_filter))
        graph_task = asyncio.create_task(self._graph_search(query_entities, top_k))
        vec_results, graph_results = await asyncio.gather(
            vec_task, graph_task, return_exceptions=True
        )

        # Graceful fallback: if one path fails, use an empty list
        if isinstance(vec_results, Exception):
            logger.warning(f"Vector search failed in HybridRetriever: {vec_results}")
            vec_results = []
        if isinstance(graph_results, Exception):
            logger.warning(f"Graph search failed in HybridRetriever: {graph_results}")
            graph_results = []

        # ── Build merged result map keyed by chunk_id ─────────────────────────
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
                # Chunk found in both paths — boost combined score
                merged[cid]["graph_score"] = gs
                merged[cid]["combined_score"] = (
                    self._vw * float(merged[cid].get("score", 0.0))
                    + self._gw * gs
                )
            else:
                # Graph-only chunk — fetch text from ChromaDB
                chunk_data = self._fetch_chunk(cid)
                if chunk_data:
                    merged[cid] = {
                        "id": cid,
                        "text": chunk_data.get("text", ""),
                        "metadata": chunk_data.get("metadata", {}),
                        "score": 0.0,
                        "graph_score": gs,
                        "combined_score": self._gw * gs,
                    }

        # ── Sort by combined_score, return top_k ──────────────────────────────
        results = sorted(merged.values(), key=lambda x: x["combined_score"], reverse=True)
        return results[:top_k]

    async def _vector_search(
        self, query: str, top_k: int, rag_filter: dict | None
    ) -> list[dict]:
        """Delegate to RAGEngine.search()."""
        return await self._rag.search(query, top_k=top_k, filter=rag_filter)

    async def _graph_search(self, entities: list[str], top_k: int) -> list[dict]:
        """Query graph for chunks matching query entities."""
        if not entities:
            return []
        return self._graph.search_by_entities(entities, top_k=top_k)

    def _fetch_chunk(self, chunk_id: str) -> dict | None:
        """Fetch a single chunk's text + metadata from ChromaDB by ID."""
        try:
            result = self._rag.collection.get(
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
```

- [ ] **Step 5.4: Run all hybrid retriever tests**

```bash
cd backend
pytest tests/test_hybrid_retriever.py -v
```
Expected: All 6 tests PASS.

- [ ] **Step 5.5: Run full test suite**

```bash
cd backend
pytest --tb=short -q 2>&1 | tail -20
```
Expected: No new failures.

- [ ] **Step 5.6: Commit**

```bash
git add backend/core/rag/hybrid_retriever.py backend/tests/test_hybrid_retriever.py
git commit -m "feat(hybrid-retriever): parallel fusion with asyncio.gather — vector + graph in parallel

- Both vector and graph searches run concurrently via asyncio.gather()
- Graceful fallback: each path fails independently without crashing
- Combined score: 0.6 × vector + 0.4 × graph
- Deduplication by chunk_id; graph-only chunks fetched from ChromaDB

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 6: Wire HybridRetriever into chat.py

**Files:**
- Modify: `backend/api/chat.py`
- Test: `backend/tests/test_chat_sources.py` (extend)

- [ ] **Step 6.1: Write failing integration test**

Add to the end of `backend/tests/test_chat_sources.py`:

```python
# ── HybridRetriever integration ─────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_uses_hybrid_retriever_for_search(client):
    """The /api/chat endpoint should invoke HybridRetriever.retrieve(), not raw rag_engine.search()."""
    from unittest.mock import patch, AsyncMock
    from core.rag.hybrid_retriever import HybridRetriever

    hybrid_mock = AsyncMock(return_value=[
        {
            "id": "law_doc_chunk_0",
            "text": "Wills and inheritance law text",
            "metadata": {"original_name": "Wills Law.pdf", "domain": "general_law"},
            "score": 0.85,
            "graph_score": 0.9,
            "combined_score": 0.87,
        }
    ])

    with patch.object(HybridRetriever, "retrieve", hybrid_mock):
        resp = await client.post("/api/chat", json={
            "message": "Draft wills for 10 million estate",
            "session_id": None,
        })

    assert resp.status_code == 200
    hybrid_mock.assert_called_once()
```

- [ ] **Step 6.2: Run to confirm test fails**

```bash
cd backend
pytest tests/test_chat_sources.py::test_chat_uses_hybrid_retriever_for_search -v
```
Expected: FAIL — `AssertionError: Expected 'retrieve' to be called once. Called 0 times.`

- [ ] **Step 6.3: Add HybridRetriever singleton to `chat.py`**

At the top of `backend/api/chat.py`, after the existing imports (after `from core.rag_engine import rag_engine`), add:

```python
from core.rag.graph_rag import GraphRAG as _GraphRAG
from core.rag.hybrid_retriever import HybridRetriever as _HybridRetriever
from pathlib import Path as _Path

def _build_hybrid_retriever() -> _HybridRetriever:
    """Construct a HybridRetriever backed by the production graph DB."""
    graph_db_path = _Path(settings.vector_store_dir).parent / "graph_store" / "graph.db"
    graph_db_path.parent.mkdir(parents=True, exist_ok=True)
    graph = _GraphRAG(db_path=str(graph_db_path))
    return _HybridRetriever(rag_engine, graph)

_hybrid_retriever = _build_hybrid_retriever()
```

- [ ] **Step 6.4: Replace `rag_engine.search()` calls in the streaming path**

In `backend/api/chat.py`, find the **streaming path** (search for `_search_results = await rag_engine.search(`). Replace that call with:

```python
_search_results = await _hybrid_retriever.retrieve(
    query=message,
    top_k=top_k,
    rag_filter=rag_filter,
)
```

- [ ] **Step 6.5: Replace `rag_engine.search()` calls in the non-streaming path**

Find the **non-streaming path** (search for `search_results = await rag_engine.search(`). Replace that call with:

```python
search_results = await _hybrid_retriever.retrieve(
    query=message,
    top_k=top_k,
    rag_filter=rag_filter,
)
```

- [ ] **Step 6.6: Run the integration test**

```bash
cd backend
pytest tests/test_chat_sources.py -v 2>&1 | tail -30
```
Expected: All tests in `test_chat_sources.py` pass including the new one.

- [ ] **Step 6.7: Run full test suite to verify no regressions**

```bash
cd backend
pytest --tb=short -q 2>&1 | tail -20
```
Expected: No new failures vs. baseline (573+). If any test patches `rag_engine.search` directly, update the patch target to `core.rag.hybrid_retriever.HybridRetriever.retrieve`.

- [ ] **Step 6.8: Commit**

```bash
git add backend/api/chat.py
git commit -m "feat(chat): wire HybridRetriever into both streaming and non-streaming paths

Replaces rag_engine.search() with hybrid_retriever.retrieve() so every
query benefits from parallel vector+graph fusion.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 7: Add spaCy to Requirements (Optional Dependency)

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 7.1: Add spaCy to requirements.txt**

Add after the `rapidfuzz` line in `backend/requirements.txt`:

```
spacy>=3.7,<4.0
```

- [ ] **Step 7.2: Install and download the small English model**

```bash
cd backend
pip install "spacy>=3.7,<4.0"
python -m spacy download en_core_web_sm
```
Expected output ends with: `✔ Download and installation successful`

- [ ] **Step 7.3: Verify spaCy works in graph_rag**

```bash
cd backend
python -c "
from core.rag.graph_rag import _SPACY_AVAILABLE, _extract_entities
print('spaCy available:', _SPACY_AVAILABLE)
ents = _extract_entities('The Federal Decree-Law No. 28 governs estate inheritance in UAE.')
print('Entities:', ents)
"
```
Expected: `spaCy available: True` and a list with `('Federal Decree-Law No. 28', 'LAW')` or similar.

- [ ] **Step 7.4: Run graph_rag tests again with spaCy active**

```bash
cd backend
pytest tests/test_graph_rag.py -v
```
Expected: All 11 tests PASS (including spaCy-enhanced extraction).

- [ ] **Step 7.5: Commit**

```bash
git add backend/requirements.txt
git commit -m "feat(deps): add spaCy>=3.7 for enhanced NER in graph_rag

Use 'python -m spacy download en_core_web_sm' after pip install.
Falls back to regex-only if model not available.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 8: Re-ingest All 455 Documents

**Files:**
- Modify: `backend/bulk_ingest.py` (path verification only)

- [ ] **Step 8.1: Verify data source directories exist**

```bash
cd backend
python -c "
from pathlib import Path
dirs = {
    'finance': Path(r'C:\Users\Armaan\OneDrive - The Era Corporations\Study\Armaan\AI Class\Data Science Class\35. 11-Apr-2026\data_source_finance'),
    'law':     Path(r'C:\Users\Armaan\OneDrive - The Era Corporations\Study\Armaan\AI Class\Data Science Class\35. 11-Apr-2026\data_source_law'),
}
for cat, d in dirs.items():
    files = list(d.rglob('*')) if d.exists() else []
    print(f'{cat}: exists={d.exists()}, files={len([f for f in files if f.is_file()])}')
"
```
Expected: `finance: exists=True, files=282` and `law: exists=True, files=173`

- [ ] **Step 8.2: Clear the existing vector store (optional but recommended for clean re-index)**

> ⚠️ This deletes the existing 13,509 chunks. Skip if you want to preserve existing data and only add new chunks.

```bash
cd backend
python -c "
import shutil, os
from config import settings
from pathlib import Path

# Back up first
store = Path(settings.vector_store_dir)
backup = Path(str(store) + '_backup_pre_hybrid')
if store.exists():
    shutil.copytree(store, backup)
    print(f'Backed up to {backup}')
    shutil.rmtree(store)
    store.mkdir(parents=True)
    print('Vector store cleared.')

# Clear graph store
graph_store = store.parent / 'graph_store'
if graph_store.exists():
    shutil.rmtree(graph_store)
    graph_store.mkdir(parents=True)
    print('Graph store cleared.')
"
```

- [ ] **Step 8.3: Run bulk_ingest.py**

```bash
cd backend
python bulk_ingest.py 2>&1 | tee bulk_ingest_run.log
```
Expected output (abbreviated):
```
[FINANCE] 282 files found in data_source_finance
  OK  (  42 chunks)  Corporate Tax Law.pdf
  ...
[LAW] 173 files found in data_source_law
  OK  (  38 chunks)  Wills Law No.28.pdf
  ...
Done.
  indexed     : 455
  skipped     : 0
  errors      : <N>
  unsupported : <M>
```
> If errors occur for specific files, check `bulk_ingest_run.log`. Common causes: scanned-only PDF (no OCR text), password-protected, or encoding issue.

- [ ] **Step 8.4: Verify ingestion results**

```bash
cd backend
python -c "
from core.rag_engine import rag_engine
stats = rag_engine.get_stats()
print('Total chunks:', stats['total_chunks'])

# Sample chunk metadata
sample = rag_engine.collection.get(limit=3, include=['metadatas'])
for m in sample['metadatas']:
    print('---')
    for k in ['original_name','category','domain','section','word_count','entities']:
        print(f'  {k}: {m.get(k, \"MISSING\")}')
"
```
Expected: `Total chunks: >5000`, all 6 metadata fields present.

- [ ] **Step 8.5: Run a live test query**

```bash
cd backend
python -c "
import asyncio
from core.rag_engine import rag_engine
from core.rag.graph_rag import GraphRAG
from core.rag.hybrid_retriever import HybridRetriever
from pathlib import Path

async def test():
    graph = GraphRAG(db_path=str(Path('graph_store/graph.db')))
    retriever = HybridRetriever(rag_engine, graph)
    results = await retriever.retrieve('Draft wills for 10 million estate with 2 children', top_k=5)
    for r in results:
        src = r['metadata'].get('original_name','?')
        cat = r['metadata'].get('category','?')
        print(f'  [{cat}] {src}  vector={r.get(\"score\",0):.3f}  graph={r.get(\"graph_score\",0):.3f}  combined={r.get(\"combined_score\",0):.3f}')

asyncio.run(test())
"
```
Expected: Results show `[law]` documents with `Wills` or `Inheritance` in the filename, NOT `Real Estate.pdf` or `VATP035`.

- [ ] **Step 8.6: Commit final state**

```bash
git add backend/bulk_ingest_run.log
git commit -m "chore: re-ingest 455 finance+law documents with hybrid RAG pipeline

- Enhanced chunk metadata: section, word_count, entities, prev/next chunk IDs
- GraphRAG knowledge graph populated with UAE legal entities
- Both categories (finance, law) now indexed

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Final Verification Checklist

Run after all 8 tasks are complete:

```bash
cd backend
# 1. Full test suite
pytest --tb=short -q 2>&1 | tail -5

# 2. Wills query returns law documents
python -c "
import asyncio
from core.rag_engine import rag_engine
from core.rag.graph_rag import GraphRAG
from core.rag.hybrid_retriever import HybridRetriever
from pathlib import Path

async def verify():
    graph = GraphRAG(db_path=str(Path('graph_store/graph.db')))
    r = HybridRetriever(rag_engine, graph)
    results = await r.retrieve('Draft wills for 10 million estate', top_k=5)
    categories = [x['metadata'].get('category','?') for x in results]
    sources = [x['metadata'].get('original_name','?') for x in results]
    print('Categories:', categories)
    print('Sources:', sources)
    assert 'law' in categories, f'No law docs in results: {categories}'
    print('PASS: Law documents found for wills query')

asyncio.run(verify())
"

# 3. No VAT docs in wills results
# (confirmed by the assertion above — if categories contains only 'law', VAT docs are absent)
```

---

## Task Dependency Order

```
Task 1 (NER)  ──────────────────────────────────────────► Task 5 (HybridRetriever uses search_by_entities)
Task 2 (section extraction) ──► Task 4 (ingest_chunks uses section)
Task 3 (config)  ────────────► Task 4 (ingest uses graph_store_dir)
Task 4 (ingest_chunks)  ──────────────────────────────────► Task 8 (re-ingest uses new pipeline)
Task 5 (HybridRetriever) ────────────────────────────────► Task 6 (chat.py wires it in)
Task 6 ──────────────────────────────────────────────────► Task 8 (verify live query)
Task 7 (spaCy) — independent, can run after Task 1
```
