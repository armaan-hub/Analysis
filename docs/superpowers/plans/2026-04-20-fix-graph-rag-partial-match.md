# Fix Graph RAG Partial Match Search

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix `search_by_entities` in `GraphRAG` to support partial substring matching so that `test_search_by_entities_partial_match` passes.

**Architecture:** Update the SQLite query in `search_by_entities` to use `LIKE` with wildcards instead of `IN`. Use a `JOIN` with a `VALUES` list of query terms to accurately count how many query terms matched each chunk.

**Tech Stack:** Python, SQLite.

---

### Task 1: Research and Verify

- [x] **Step 1: Read existing code and tests**
- [x] **Step 2: Verify test failure**
- [x] **Step 3: Check SQLite version for feature compatibility**

### Task 2: Implement Fix

**Files:**
- Modify: `Main Branch/Project_AccountingLegalChatbot/backend/core/rag/graph_rag.py`

- [ ] **Step 1: Update `search_by_entities` implementation**

Replace the `IN` clause query with a `JOIN` on `VALUES` and `LIKE` matching.

```python
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

        terms_placeholders = ",".join(["(?)"] * len(normalised))
        conn = self._connect()
        # Use a JOIN with query terms and LIKE for partial matching.
        # This counts how many of the query terms found a match in the chunk.
        rows = conn.execute(
            f\"\"\"
            SELECT e.doc_id, e.chunk_index, COUNT(DISTINCT q.term) AS match_count
            FROM entities e
            JOIN (VALUES {terms_placeholders}) AS q(term)
              ON LOWER(e.name) LIKE '%' || q.term || '%'
            GROUP BY e.doc_id, e.chunk_index
            ORDER BY match_count DESC
            LIMIT ?
            \"\"\",
            normalised + [top_k],
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
```

### Task 3: Verification

- [ ] **Step 1: Run the failing test**

Run: `python3 -m pytest tests/test_graph_rag.py::test_search_by_entities_partial_match` inside `Main Branch/Project_AccountingLegalChatbot/backend`.
Expected: PASS

- [ ] **Step 2: Run all tests in `test_graph_rag.py` to ensure no regressions**

Run: `python3 -m pytest tests/test_graph_rag.py`
Expected: ALL PASS
