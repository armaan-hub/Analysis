---
name: project-isolated-testing
description: Use when writing or updating tests for the Accounting & Legal Chatbot to ensure they are isolated, fast, and do not hit external APIs or corrupt local storage.
---

# Project Isolated Testing Skill

## Overview
This project relies on external LLM and Embedding APIs (NVIDIA, OpenAI, etc.) and uses a persistent vector store (ChromaDB). To ensure reliable and fast testing, all tests MUST be isolated from these dependencies.

## Core Pattern

### 1. Mocking External APIs
Use `respx` to block and mock all network calls to external providers. This is globally configured in `backend/tests/conftest.py`.

**Before (Unstable):**
```python
# Hits the real API and requires valid keys
resp = await client.post("/api/documents/upload", files=...)
```

**After (Isolated):**
```python
# In conftest.py
with respx.mock(assert_all_called=False) as respx_mock:
    respx_mock.post("https://integrate.api.nvidia.com/v1/embeddings").mock(
        side_effect=mock_embedding_side_effect
    )
```

### 2. In-Memory Database
Always use the `db_session` fixture which uses an in-memory SQLite database (`sqlite+aiosqlite:///:memory:`).

### 3. Isolated Vector Store
When testing RAG logic, prefer mocking `rag_engine` methods or ensure the `VECTOR_STORE_DIR` is set to a temporary directory in the test environment.

## When to Use
- Adding a new API endpoint that calls an LLM.
- Adding a new document processing pipeline.
- Fixing bugs in RAG retrieval.

## Common Mistakes
- **Leaking API Keys:** Never commit real API keys to tests.
- **Deselected Tests:** If a test skips because of "missing API key", it's a sign that it's not properly mocked.
- **Shared State:** Ensure the database is rolled back or cleared between tests (handled by `db_session` fixture).

## Verification
Run all tests using the project venv to avoid version mismatches:
```powershell
.\venv\Scripts\python.exe -m pytest
```
All 410+ tests should pass with 0 errors and minimal skips.
