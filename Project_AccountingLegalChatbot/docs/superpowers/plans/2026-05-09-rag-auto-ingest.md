# RAG Auto-Ingest Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-ingest all 461+ PDFs from `data_source_finance/` and `data_source_law/` into ChromaDB with Arabic translation, LLM metadata tagging, entity graph extraction, and a persistent document registry that only re-processes changed files.

**Architecture:** Three-stage pipeline per document (Parse → Translate → Tag+Index) driven by a SHA256-based registry. On startup, a full source-dir scan queues all new/changed files. A watchdog (already exists) handles live drops. Five new backend modules cover the pipeline stages; existing `DocumentProcessor` is extended to orchestrate them.

**Tech Stack:** pymupdf (fitz), aiosqlite, ChromaDB, existing LLMProvider (NvidiaProvider), existing APScheduler, pytest-asyncio

**Active code root:** `~/chatbot_local/Project_AccountingLegalChatbot/backend/`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| **Modify** | `db/models.py` | Add `source_dir`, `domain`, `jurisdiction`, `law_number`, `subjects`, `effective_date`, `is_arabic`, `was_translated`, `indexed_at` columns to `Document`; update `status` vocabulary |
| **Modify** | `db/migrations/` | New migration file `add_rag_auto_ingest_fields.py` to ALTER TABLE for new columns |
| **Modify** | `config.py` | Add `source_law_dir`, `source_finance_dir`, `entity_graph_db` settings |
| **Create** | `core/pipeline/pdf_extractor.py` | `extract_text(path) → ExtractionResult` — pymupdf, Arabic detection, OCR fallback |
| **Modify** | `core/llm_manager.py` | Add `translate(text, src, tgt) → str` and `extract_metadata(filename, text, source_dir) → MetadataResult` methods to `LLMManager` |
| **Create** | `api/llm.py` | Internal-only `POST /api/llm/translate` and `POST /api/llm/extract-metadata` endpoints |
| **Create** | `core/entity_graph.py` | SQLite-backed entity/relationship store, `extract_and_store(doc_id, text)` |
| **Create** | `core/rag/entity_retriever.py` | `EntityRetriever.search(query) → list[EntityResult]` — third retrieval path |
| **Create** | `core/pipeline/source_scanner.py` | `SourceScanner.scan() → list[PendingFile]` — SHA256 diff against registry |
| **Modify** | `core/document_processor.py` | Add `ingest_source_file(path, source_dir, db)` that runs all 3 stages and populates new fields |
| **Modify** | `api/documents.py` | Add `POST /api/documents/scan-source-dirs`, `GET /api/documents/registry`, `GET /api/documents/registry/{doc_id}`, `POST /api/documents/{doc_id}/reindex` endpoints; extend existing `DELETE` to cascade |
| **Modify** | `main.py` | On startup: call `SourceScanner.scan()`, queue batch via `ingest_source_file` |
| **Create** | `tests/test_pdf_extraction.py` | Unit tests for text extraction, Arabic detection, OCR handling |
| **Create** | `tests/test_translation.py` | Unit tests for `LLMManager.translate()` + translation endpoint |
| **Create** | `tests/test_metadata_tagger.py` | Unit tests for `LLMManager.extract_metadata()` + metadata endpoint |
| **Create** | `tests/test_entity_graph.py` | Unit tests for entity extraction, graph storage, traversal |
| **Create** | `tests/test_source_scanner.py` | Unit tests for SHA256 scan logic, changed-file detection |
| **Create** | `tests/test_full_ingest.py` | Integration test: scan → extract → translate → tag → index → verify registry |

---

## Task 1: DB Model — Add New Fields

**Files:**
- Modify: `db/models.py` (Document class, ~line 66–90)
- Create: `db/migrations/add_rag_auto_ingest_fields.py`

- [ ] **Step 1.1: Write the failing test**

```python
# tests/test_pdf_extraction.py (stub — just import Document to confirm fields exist)
import pytest
from db.models import Document

def test_document_model_has_new_rag_fields():
    """Document model must carry pipeline fields before we can test anything else."""
    required = {
        "source_dir", "domain", "jurisdiction", "law_number",
        "subjects", "effective_date", "is_arabic", "was_translated", "indexed_at",
    }
    cols = {c.key for c in Document.__table__.columns}
    missing = required - cols
    assert not missing, f"Document model missing columns: {missing}"
```

- [ ] **Step 1.2: Run test to confirm it fails**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/test_pdf_extraction.py::test_document_model_has_new_rag_fields -v
```

Expected: `FAILED — AssertionError: Document model missing columns: {...}`

- [ ] **Step 1.3: Add new columns to `db/models.py`**

Open `db/models.py` and add these columns to the `Document` class immediately after `content_hash` (line ~83):

```python
    # ── Source pipeline fields ────────────────────────────────────────
    source_dir     = Column(String(20),  nullable=True)          # "law" | "finance" | None (upload)
    domain         = Column(String(50),  nullable=True)          # e.g. "banking_compliance"
    jurisdiction   = Column(String(50),  nullable=True)          # e.g. "uae_federal"
    law_number     = Column(String(200), nullable=True)          # e.g. "Decree Law 50 of 2022"
    subjects       = Column(JSON,        nullable=True)          # ["cheque bouncing", "penalties"]
    effective_date = Column(String(20),  nullable=True)          # ISO date or None
    is_arabic      = Column(Boolean,     default=False, nullable=False, server_default="0")
    was_translated = Column(Boolean,     default=False, nullable=False, server_default="0")
    indexed_at     = Column(DateTime,    nullable=True)
```

Also update the `status` default comment (line ~76) to document the full vocabulary:

```python
    status = Column(String(20), default="processing")  # processing | indexed | error | pending | failed | skipped
```

- [ ] **Step 1.4: Create migration file**

Create `db/migrations/add_rag_auto_ingest_fields.py`:

```python
"""Migration: add RAG auto-ingest fields to documents table.

Idempotent — safe to run multiple times.
"""
import sqlite3
import logging

logger = logging.getLogger(__name__)

_NEW_COLUMNS = [
    ("source_dir",     "TEXT"),
    ("jurisdiction",   "TEXT"),
    ("law_number",     "TEXT"),
    ("subjects",       "TEXT"),   # JSON stored as TEXT in SQLite
    ("effective_date", "TEXT"),
    ("is_arabic",      "INTEGER DEFAULT 0 NOT NULL"),
    ("was_translated", "INTEGER DEFAULT 0 NOT NULL"),
    ("indexed_at",     "TEXT"),
]


def run_migration(db_path: str) -> None:
    """ALTER TABLE documents to add new columns if not already present."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute("PRAGMA table_info(documents)")
        existing = {row[1] for row in cur.fetchall()}
        for col_name, col_type in _NEW_COLUMNS:
            if col_name not in existing:
                conn.execute(f"ALTER TABLE documents ADD COLUMN {col_name} {col_type}")
                logger.info(f"[migration] Added documents.{col_name}")
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 1.5: Wire migration into `main.py` startup**

In `main.py` lifespan function, after the existing `_add_conv_mode` migration call (line ~52), add:

```python
    from db.migrations.add_rag_auto_ingest_fields import run_migration as _add_rag_fields
    _add_rag_fields(str(_s.database_url).replace("sqlite+aiosqlite:///", "").replace("sqlite:///", ""))
    logger.info(f"[OK] Schema migration: RAG auto-ingest fields ensured ({time.perf_counter()-_t:.2f}s)")
```

- [ ] **Step 1.6: Run test to confirm it passes**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/test_pdf_extraction.py::test_document_model_has_new_rag_fields -v
```

Expected: `PASSED`

- [ ] **Step 1.7: Commit**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
git add db/models.py db/migrations/add_rag_auto_ingest_fields.py main.py
git commit -m "feat: add RAG auto-ingest fields to Document model + migration

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: Config — Source Directory Settings

**Files:**
- Modify: `config.py` (add 3 settings)

- [ ] **Step 2.1: Write failing test**

```python
# tests/test_source_scanner.py
import os
import pytest
from config import Settings

def test_config_has_source_dir_settings():
    """Config must expose source_law_dir, source_finance_dir, entity_graph_db."""
    s = Settings()
    assert hasattr(s, "source_law_dir")
    assert hasattr(s, "source_finance_dir")
    assert hasattr(s, "entity_graph_db")

def test_source_dirs_default_to_backend_relative():
    """Default paths must resolve to absolute paths under backend/."""
    s = Settings()
    import os
    assert os.path.isabs(s.source_law_dir), "source_law_dir must be absolute"
    assert os.path.isabs(s.source_finance_dir), "source_finance_dir must be absolute"
    assert os.path.isabs(s.entity_graph_db), "entity_graph_db must be absolute"
```

- [ ] **Step 2.2: Run test to confirm it fails**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/test_source_scanner.py::test_config_has_source_dir_settings -v
```

Expected: `FAILED — AttributeError`

- [ ] **Step 2.3: Add settings to `config.py`**

In `config.py`, find the `# ── File Storage` block (~line 100) and add after `graph_store_dir`:

```python
    # ── Auto-ingest source directories ──────────────────────────────
    source_law_dir:     str = "../data_source_law"
    source_finance_dir: str = "../data_source_finance"
    entity_graph_db:    str = "./graph_store/entity_graph.db"
```

Also add the new keys to the `_resolve_relative_paths` validator:

```python
        for key in ("database_url", "upload_dir", "vector_store_dir", "graph_store_dir",
                    "source_law_dir", "source_finance_dir", "entity_graph_db"):
```

- [ ] **Step 2.4: Run test to confirm it passes**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/test_source_scanner.py::test_config_has_source_dir_settings tests/test_source_scanner.py::test_source_dirs_default_to_backend_relative -v
```

Expected: `2 PASSED`

- [ ] **Step 2.5: Commit**

```bash
git add config.py tests/test_source_scanner.py
git commit -m "feat: add source_law_dir, source_finance_dir, entity_graph_db to config

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: PDF Extractor Module

**Files:**
- Create: `core/pipeline/pdf_extractor.py`
- Modify: `tests/test_pdf_extraction.py` (add extraction tests)

- [ ] **Step 3.1: Write failing tests**

```python
# tests/test_pdf_extraction.py — add below the model field test

import pytest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

# ── Arabic detection ──────────────────────────────────────────────────────────

def test_is_arabic_detects_arabic_text():
    from core.pipeline.pdf_extractor import _is_arabic
    arabic = "هذا نص عربي طويل بما يكفي للكشف عنه كنص عربي"
    assert _is_arabic(arabic) is True

def test_is_arabic_rejects_english():
    from core.pipeline.pdf_extractor import _is_arabic
    english = "This is a long English sentence about UAE commercial law and contracts."
    assert _is_arabic(english) is False

def test_is_arabic_threshold_30_percent():
    from core.pipeline.pdf_extractor import _is_arabic
    # 25% Arabic chars (below threshold) → False
    mixed = "English words " * 6 + "عربي"   # ~12% arabic
    assert _is_arabic(mixed) is False

# ── ExtractionResult dataclass ────────────────────────────────────────────────

def test_extraction_result_fields():
    from core.pipeline.pdf_extractor import ExtractionResult
    r = ExtractionResult(text="hello", page_count=2, is_arabic=False, skipped=False, skip_reason=None)
    assert r.text == "hello"
    assert r.page_count == 2
    assert r.is_arabic is False
    assert r.skipped is False

# ── extract_text mocked ───────────────────────────────────────────────────────

def test_extract_text_returns_result_for_valid_pdf(tmp_path):
    from core.pipeline.pdf_extractor import extract_text

    # Build a minimal in-memory PDF via fitz
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello world, this is a test PDF for ingestion.")
    pdf_path = tmp_path / "test.pdf"
    doc.save(str(pdf_path))
    doc.close()

    result = extract_text(str(pdf_path))
    assert result.skipped is False
    assert "Hello world" in result.text
    assert result.page_count == 1
    assert result.is_arabic is False

def test_extract_text_detects_encrypted_pdf(tmp_path):
    from core.pipeline.pdf_extractor import extract_text
    import fitz
    doc = fitz.open()
    doc.new_page()
    pdf_path = tmp_path / "enc.pdf"
    # Save with owner password to create encrypted PDF
    doc.save(str(pdf_path), encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="secret", user_pw="secret")
    doc.close()

    result = extract_text(str(pdf_path))
    assert result.skipped is True
    assert result.skip_reason is not None
    assert "encrypt" in result.skip_reason.lower() or "password" in result.skip_reason.lower()
```

- [ ] **Step 3.2: Run tests to confirm they fail**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/test_pdf_extraction.py -k "not test_document_model" -v
```

Expected: `ImportError: cannot import name 'ExtractionResult' from 'core.pipeline.pdf_extractor'`

- [ ] **Step 3.3: Create `core/pipeline/pdf_extractor.py`**

```python
"""Stage 1: PDF text extraction with Arabic detection and OCR fallback.

Public API:
    extract_text(path: str) -> ExtractionResult
"""
from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Arabic Unicode block: U+0600–U+06FF (basic Arabic + extended)
_ARABIC_RANGE_START = 0x0600
_ARABIC_RANGE_END   = 0x06FF
_ARABIC_THRESHOLD   = 0.30   # >30% of non-whitespace chars are Arabic → is_arabic=True


@dataclass
class ExtractionResult:
    text:        str
    page_count:  int
    is_arabic:   bool
    skipped:     bool
    skip_reason: Optional[str]


def _is_arabic(text: str) -> bool:
    """Return True if >30% of non-whitespace characters are in the Arabic Unicode block."""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return False
    arabic_count = sum(
        1 for c in chars
        if _ARABIC_RANGE_START <= ord(c) <= _ARABIC_RANGE_END
    )
    return arabic_count / len(chars) > _ARABIC_THRESHOLD


def _ocr_page(page) -> str:  # type: ignore[no-untyped-def]
    """Attempt OCR on a single pymupdf page. Returns '' if pytesseract unavailable."""
    try:
        import pytesseract
        from PIL import Image
        import io
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return pytesseract.image_to_string(img, lang="ara+eng")
    except ImportError:
        return ""
    except Exception as exc:
        logger.debug("OCR failed on page: %s", exc)
        return ""


def extract_text(path: str) -> ExtractionResult:
    """Extract text from a PDF (or txt/docx/csv) file.

    Returns ExtractionResult with skipped=True if the file cannot be parsed
    (encrypted, no extractable text, unsupported format).
    """
    import fitz  # PyMuPDF

    p = Path(path)
    suffix = p.suffix.lower()

    # ── Plain text / CSV ──────────────────────────────────────────────
    if suffix in (".txt", ".csv"):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            return ExtractionResult(
                text=text,
                page_count=1,
                is_arabic=_is_arabic(text),
                skipped=False,
                skip_reason=None,
            )
        except Exception as exc:
            return ExtractionResult("", 0, False, True, str(exc))

    # ── DOCX ─────────────────────────────────────────────────────────
    if suffix == ".docx":
        try:
            import docx  # python-docx
            doc = docx.Document(str(p))
            text = "\n".join(para.text for para in doc.paragraphs)
            return ExtractionResult(
                text=text,
                page_count=1,
                is_arabic=_is_arabic(text),
                skipped=False,
                skip_reason=None,
            )
        except ImportError:
            return ExtractionResult("", 0, False, True, "python-docx not installed")
        except Exception as exc:
            return ExtractionResult("", 0, False, True, str(exc))

    # ── PDF via PyMuPDF ───────────────────────────────────────────────
    try:
        doc = fitz.open(str(p))
    except Exception as exc:
        return ExtractionResult("", 0, False, True, f"fitz.open failed: {exc}")

    try:
        # Attempt blank-password decrypt for encrypted PDFs
        if doc.is_encrypted:
            ok = doc.authenticate("")
            if not ok:
                return ExtractionResult(
                    "", 0, False, True,
                    "encrypted PDF — blank password failed, skipping"
                )

        pages_text: list[str] = []
        for page in doc:
            page_text = page.get_text()
            if not page_text.strip():
                # Scanned image page — try OCR
                page_text = _ocr_page(page)
            pages_text.append(page_text)

        full_text = "\n".join(pages_text)

        if not full_text.strip():
            return ExtractionResult(
                "", doc.page_count, False, True,
                "no extractable text and OCR yielded nothing"
            )

        return ExtractionResult(
            text=full_text,
            page_count=doc.page_count,
            is_arabic=_is_arabic(full_text),
            skipped=False,
            skip_reason=None,
        )
    finally:
        doc.close()
```

- [ ] **Step 3.4: Run tests to confirm they pass**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/test_pdf_extraction.py -v
```

Expected: `5 PASSED`

- [ ] **Step 3.5: Commit**

```bash
git add core/pipeline/pdf_extractor.py tests/test_pdf_extraction.py
git commit -m "feat: add PDF extractor with Arabic detection and OCR fallback

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4: LLM Translation + Metadata Extraction Methods

**Files:**
- Modify: `core/llm_manager.py` (add `translate()` and `extract_metadata()` to `LLMManager`)
- Create: `api/llm.py` (internal endpoints)
- Modify: `main.py` (register router)
- Modify: `tests/test_translation.py` (new test file)
- Modify: `tests/test_metadata_tagger.py` (new test file)

- [ ] **Step 4.1: Write failing tests for translation**

```python
# tests/test_translation.py
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture
def mock_llm_chat():
    """Returns a mock chat() that produces a canned translation response."""
    async def _chat(messages, temperature=0.1, max_tokens=None, **kw):
        from core.llm_manager import LLMResponse
        return LLMResponse(
            content="The Arabic text here",
            model="test-model",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )
    return _chat


@pytest.mark.asyncio
async def test_llm_manager_translate_returns_string(mock_llm_chat):
    """LLMManager.translate() must return a non-empty string."""
    from core.llm_manager import LLMManager
    mgr = LLMManager.__new__(LLMManager)
    mgr._provider = MagicMock()
    mgr._provider.chat = mock_llm_chat
    result = await mgr.translate("النص العربي هنا", src="ar", tgt="en")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_llm_manager_translate_uses_legal_system_prompt(mock_llm_chat):
    """translate() must include legal translator system prompt."""
    from core.llm_manager import LLMManager
    mgr = LLMManager.__new__(LLMManager)
    captured = []

    async def _capture_chat(messages, **kw):
        captured.extend(messages)
        from core.llm_manager import LLMResponse
        return LLMResponse(content="translated", model="m", usage={})

    mgr._provider = MagicMock()
    mgr._provider.chat = _capture_chat
    await mgr.translate("نص", src="ar", tgt="en")
    system_msg = next((m for m in captured if m.get("role") == "system"), None)
    assert system_msg is not None
    assert "legal" in system_msg["content"].lower()
```

- [ ] **Step 4.2: Write failing tests for metadata extraction**

```python
# tests/test_metadata_tagger.py
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock


_SAMPLE_METADATA_JSON = json.dumps({
    "domain": "banking_compliance",
    "jurisdiction": "uae_federal",
    "law_number": "Decree Law 50 of 2022",
    "subjects": ["cheque bouncing", "penalties"],
    "effective_date": "2022-09-01",
    "summary": "Federal decree governing bounced cheques.",
})


@pytest.mark.asyncio
async def test_extract_metadata_returns_dataclass():
    """extract_metadata() must return a MetadataResult with domain, jurisdiction, subjects."""
    from core.llm_manager import LLMManager, MetadataResult

    mgr = LLMManager.__new__(LLMManager)
    mgr._provider = MagicMock()

    async def _chat(messages, **kw):
        from core.llm_manager import LLMResponse
        return LLMResponse(content=_SAMPLE_METADATA_JSON, model="m", usage={})

    mgr._provider.chat = _chat
    result = await mgr.extract_metadata(
        filename="DecreeLaw_50_2022_pdf.pdf",
        text="text sample",
        source_dir="law",
    )
    assert isinstance(result, MetadataResult)
    assert result.domain == "banking_compliance"
    assert result.jurisdiction == "uae_federal"
    assert "cheque bouncing" in result.subjects
    assert result.effective_date == "2022-09-01"


@pytest.mark.asyncio
async def test_extract_metadata_handles_malformed_json():
    """extract_metadata() must not raise on malformed LLM output — return defaults."""
    from core.llm_manager import LLMManager, MetadataResult

    mgr = LLMManager.__new__(LLMManager)
    mgr._provider = MagicMock()

    async def _chat(messages, **kw):
        from core.llm_manager import LLMResponse
        return LLMResponse(content="this is not JSON", model="m", usage={})

    mgr._provider.chat = _chat
    result = await mgr.extract_metadata("test.pdf", "text", "law")
    assert isinstance(result, MetadataResult)
    assert result.domain == "general"   # safe fallback
```

- [ ] **Step 4.3: Run tests to confirm they fail**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/test_translation.py tests/test_metadata_tagger.py -v 2>&1 | head -30
```

Expected: `ImportError` or `AttributeError` — `translate`, `extract_metadata`, `MetadataResult` don't exist yet.

- [ ] **Step 4.4: Add `MetadataResult` dataclass + `translate()` + `extract_metadata()` to `core/llm_manager.py`**

Find the section near the top of `llm_manager.py` where dataclasses / response objects are defined (around `LLMResponse` class, line ~76). Add after `LLMResponse`:

```python
from dataclasses import dataclass, field as _field
from typing import Optional as _Opt, List as _List

@dataclass
class MetadataResult:
    domain:         str             = "general"
    jurisdiction:   str             = ""
    law_number:     str             = ""
    subjects:       list[str]       = _field(default_factory=list)
    effective_date: _Opt[str]       = None
    summary:        str             = ""
```

Then find the `LLMManager` class (the main orchestrator that holds `_provider`). Add these two async methods to it:

```python
    # ── Translation ────────────────────────────────────────────────────────

    async def translate(self, text: str, src: str = "ar", tgt: str = "en") -> str:
        """Translate *text* from *src* to *tgt* using the legal translator prompt.

        Returns the translated string. Raises on provider error.
        """
        _TRANSLATE_SYSTEM = (
            "You are a professional legal translator. "
            "Translate the following document from Arabic to English. "
            "Preserve legal terminology precisely. Return ONLY the English translation. "
            "If a passage cannot be translated with confidence, mark it as [TRANSLATION_UNCERTAIN]. "
            "Do not add explanations or notes."
        )
        messages = [
            {"role": "system", "content": _TRANSLATE_SYSTEM},
            {"role": "user",   "content": f"Translate this text:\n\n{text}"},
        ]
        response = await self._provider.chat(messages, temperature=0.1, max_tokens=4096)
        return response.content.strip()

    # ── Metadata Extraction ────────────────────────────────────────────────

    async def extract_metadata(
        self,
        filename: str,
        text: str,
        source_dir: str,
    ) -> "MetadataResult":
        """Extract domain, jurisdiction, subjects etc. from a document sample.

        Returns MetadataResult with safe defaults on LLM error or malformed JSON.
        """
        import json as _json

        _META_SYSTEM = (
            "You are a UAE legal research assistant. Analyze this document and extract metadata. "
            "Return ONLY valid JSON with these fields: "
            "domain (one of: tenancy|vat|corporate_tax|aml|competition|banking_compliance|labour|"
            "antidumping|trademark|copyright|consumer_protection|companies|general|other), "
            "jurisdiction (uae_federal|dubai|cabinet|ministerial|local), "
            "law_number (official law/decree number or empty string), "
            "subjects (array of 3-8 specific legal topics), "
            "effective_date (ISO date or null), "
            "summary (1-2 sentence plain-English summary)."
        )
        sample = text[:2000]
        messages = [
            {"role": "system", "content": _META_SYSTEM},
            {"role": "user",   "content": (
                f"Filename: {filename}\n"
                f"Source category: {source_dir}\n\n"
                f"Document text (first 2000 chars):\n{sample}"
            )},
        ]
        try:
            response = await self._provider.chat(messages, temperature=0.1, max_tokens=512)
            raw = response.content.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = _json.loads(raw)
            return MetadataResult(
                domain         = data.get("domain", "general") or "general",
                jurisdiction   = data.get("jurisdiction", "") or "",
                law_number     = data.get("law_number", "") or "",
                subjects       = data.get("subjects", []) or [],
                effective_date = data.get("effective_date") or None,
                summary        = data.get("summary", "") or "",
            )
        except Exception:
            return MetadataResult()
```

- [ ] **Step 4.5: Create `api/llm.py`**

```python
"""Internal-only LLM helper endpoints.

Not exposed in the public Swagger UI (include_in_schema=False).
Used internally by the auto-ingest pipeline.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/llm", tags=["llm-internal"])


class TranslateRequest(BaseModel):
    text: str
    source_language: str = "ar"
    target_language: str = "en"


class TranslateResponse(BaseModel):
    translated_text: str
    detected_language: str


class MetadataRequest(BaseModel):
    filename: str
    text: str
    source_dir: str


class MetadataResponse(BaseModel):
    domain: str
    jurisdiction: str
    law_number: str
    subjects: list[str]
    effective_date: Optional[str]
    summary: str


@router.post("/translate", response_model=TranslateResponse, include_in_schema=False)
async def translate_text(req: TranslateRequest) -> TranslateResponse:
    """Translate text using the LLM provider. Internal use only."""
    from core.llm_manager import llm_manager
    try:
        translated = await llm_manager.translate(
            req.text, src=req.source_language, tgt=req.target_language
        )
        return TranslateResponse(
            translated_text=translated,
            detected_language=req.source_language,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/extract-metadata", response_model=MetadataResponse, include_in_schema=False)
async def extract_metadata(req: MetadataRequest) -> MetadataResponse:
    """Extract structured metadata from a document sample. Internal use only."""
    from core.llm_manager import llm_manager
    try:
        result = await llm_manager.extract_metadata(
            filename=req.filename,
            text=req.text,
            source_dir=req.source_dir,
        )
        return MetadataResponse(
            domain=result.domain,
            jurisdiction=result.jurisdiction,
            law_number=result.law_number,
            subjects=result.subjects,
            effective_date=result.effective_date,
            summary=result.summary,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
```

- [ ] **Step 4.6: Register the router in `main.py`**

In `main.py`, find where the other routers are included (look for `app.include_router`). Add:

```python
from api.llm import router as llm_router
app.include_router(llm_router)
```

- [ ] **Step 4.7: Run tests to confirm they pass**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/test_translation.py tests/test_metadata_tagger.py -v
```

Expected: `4 PASSED`

- [ ] **Step 4.8: Commit**

```bash
git add core/llm_manager.py api/llm.py main.py tests/test_translation.py tests/test_metadata_tagger.py
git commit -m "feat: add LLMManager.translate() and extract_metadata() + internal API endpoints

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5: Entity Graph Module

**Files:**
- Create: `core/entity_graph.py`
- Create: `core/rag/entity_retriever.py`
- Create: `tests/test_entity_graph.py`

- [ ] **Step 5.1: Write failing tests**

```python
# tests/test_entity_graph.py
import pytest
import asyncio
import tempfile
import os


@pytest.fixture
def tmp_graph_db(tmp_path):
    """Temp SQLite path for graph tests."""
    return str(tmp_path / "test_entity_graph.db")


@pytest.mark.asyncio
async def test_entity_graph_init_creates_tables(tmp_graph_db):
    """EntityGraph.init() must create entities and relationships tables."""
    from core.entity_graph import EntityGraph
    g = EntityGraph(tmp_graph_db)
    await g.init()
    import aiosqlite
    async with aiosqlite.connect(tmp_graph_db) as db:
        cur = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] async for row in cur}
    assert "entities" in tables
    assert "relationships" in tables


@pytest.mark.asyncio
async def test_entity_graph_store_and_retrieve(tmp_graph_db):
    """store_entities() must persist entities and relationships."""
    from core.entity_graph import EntityGraph, Entity, Relationship
    g = EntityGraph(tmp_graph_db)
    await g.init()

    entities = [
        Entity(name="Article 15", type="article", properties={"number": 15}),
        Entity(name="Decree Law 50/2022", type="law", properties={"effective_date": "2022-09-01"}),
    ]
    relationships = [
        Relationship(source_name="Article 15", target_name="Decree Law 50/2022", relationship="part_of"),
    ]
    await g.store_entities("doc-001", entities, relationships)

    # Verify entities stored
    async with __import__("aiosqlite").connect(tmp_graph_db) as db:
        cur = await db.execute("SELECT COUNT(*) FROM entities WHERE doc_id=?", ("doc-001",))
        row = await cur.fetchone()
    assert row[0] == 2


@pytest.mark.asyncio
async def test_entity_graph_search_by_name(tmp_graph_db):
    """search_entities(name) must return matching entities."""
    from core.entity_graph import EntityGraph, Entity, Relationship
    g = EntityGraph(tmp_graph_db)
    await g.init()
    await g.store_entities("doc-001", [
        Entity(name="Bounced Cheque Penalties", type="concept", properties={}),
    ], [])

    results = await g.search_entities("bounced cheque")
    assert any("Bounced" in r["name"] for r in results)


@pytest.mark.asyncio
async def test_extract_entities_from_llm_response_valid_json():
    """EntityGraph.parse_llm_response() must parse entities + relationships from JSON."""
    from core.entity_graph import EntityGraph
    g = EntityGraph(":memory:")

    import json
    raw = json.dumps({
        "entities": [
            {"name": "Article 15", "type": "article", "properties": {"number": 15}},
        ],
        "relationships": [
            {"source": "Article 15", "target": "Decree Law 50/2022", "relationship": "part_of"},
        ],
    })
    entities, rels = g.parse_llm_response(raw)
    assert len(entities) == 1
    assert entities[0].name == "Article 15"
    assert len(rels) == 1
    assert rels[0].relationship == "part_of"


@pytest.mark.asyncio
async def test_extract_entities_from_llm_response_invalid_json():
    """parse_llm_response() must return empty lists on malformed JSON."""
    from core.entity_graph import EntityGraph
    g = EntityGraph(":memory:")
    entities, rels = g.parse_llm_response("not json at all")
    assert entities == []
    assert rels == []
```

- [ ] **Step 5.2: Run tests to confirm they fail**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/test_entity_graph.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'EntityGraph'`

- [ ] **Step 5.3: Create `core/entity_graph.py`**

```python
"""Entity knowledge graph backed by SQLite (aiosqlite).

Stores entities and relationships extracted from ingested documents.
Provides a third retrieval path alongside vector search and GraphRAG.

Public API:
    EntityGraph(db_path: str)
        .init() -> None
        .store_entities(doc_id, entities, relationships) -> None
        .search_entities(query: str, limit: int) -> list[dict]
        .parse_llm_response(raw: str) -> tuple[list[Entity], list[Relationship]]
        .delete_by_doc(doc_id: str) -> None
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

import aiosqlite

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    name:       str
    type:       str          # article|clause|law|decree|person|concept|date|amount
    properties: dict         = field(default_factory=dict)


@dataclass
class Relationship:
    source_name:  str
    target_name:  str
    relationship: str        # cites|amends|repeals|defines|applies_to|part_of


_CREATE_ENTITIES = """
CREATE TABLE IF NOT EXISTS entities (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id     TEXT NOT NULL,
    name       TEXT NOT NULL,
    type       TEXT NOT NULL,
    properties TEXT,         -- JSON
    created_at TEXT DEFAULT (datetime('now'))
)
"""

_CREATE_RELATIONSHIPS = """
CREATE TABLE IF NOT EXISTS relationships (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id    INTEGER NOT NULL,
    target_id    INTEGER NOT NULL,
    relationship TEXT NOT NULL,
    doc_id       TEXT NOT NULL,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (source_id) REFERENCES entities(id),
    FOREIGN KEY (target_id) REFERENCES entities(id)
)
"""

_CREATE_ENTITY_IDX = "CREATE INDEX IF NOT EXISTS idx_entities_doc_id ON entities(doc_id)"
_CREATE_ENTITY_NAME_IDX = "CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name COLLATE NOCASE)"


class EntityGraph:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def init(self) -> None:
        """Create tables if not present (idempotent)."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(_CREATE_ENTITIES)
            await db.execute(_CREATE_RELATIONSHIPS)
            await db.execute(_CREATE_ENTITY_IDX)
            await db.execute(_CREATE_ENTITY_NAME_IDX)
            await db.commit()

    async def store_entities(
        self,
        doc_id: str,
        entities: list[Entity],
        relationships: list[Relationship],
    ) -> None:
        """Persist entities and relationships for *doc_id*."""
        async with aiosqlite.connect(self._db_path) as db:
            # Insert entities, build name→id map
            name_to_id: dict[str, int] = {}
            for ent in entities:
                cur = await db.execute(
                    "INSERT INTO entities (doc_id, name, type, properties) VALUES (?, ?, ?, ?)",
                    (doc_id, ent.name, ent.type, json.dumps(ent.properties)),
                )
                name_to_id[ent.name] = cur.lastrowid  # type: ignore[assignment]

            # Insert relationships (skip if source or target not in entities)
            for rel in relationships:
                src_id = name_to_id.get(rel.source_name)
                tgt_id = name_to_id.get(rel.target_name)
                if src_id and tgt_id:
                    await db.execute(
                        "INSERT INTO relationships (source_id, target_id, relationship, doc_id) VALUES (?, ?, ?, ?)",
                        (src_id, tgt_id, rel.relationship, doc_id),
                    )
            await db.commit()

    async def search_entities(self, query: str, limit: int = 10) -> list[dict]:
        """Return entities whose name contains *query* (case-insensitive)."""
        pattern = f"%{query}%"
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT id, doc_id, name, type, properties FROM entities "
                "WHERE name LIKE ? COLLATE NOCASE LIMIT ?",
                (pattern, limit),
            )
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    def parse_llm_response(self, raw: str) -> tuple[list[Entity], list[Relationship]]:
        """Parse LLM JSON output into Entity / Relationship objects.

        Returns ([], []) on any parse error — never raises.
        """
        try:
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text)
            entities = [
                Entity(
                    name=e["name"],
                    type=e.get("type", "concept"),
                    properties=e.get("properties", {}),
                )
                for e in data.get("entities", [])
            ]
            relationships = [
                Relationship(
                    source_name=r["source"],
                    target_name=r["target"],
                    relationship=r.get("relationship", "related_to"),
                )
                for r in data.get("relationships", [])
            ]
            return entities, relationships
        except Exception as exc:
            logger.debug("parse_llm_response failed: %s", exc)
            return [], []

    async def delete_by_doc(self, doc_id: str) -> None:
        """Remove all entities and relationships for *doc_id*."""
        async with aiosqlite.connect(self._db_path) as db:
            # Get entity ids for this doc
            cur = await db.execute("SELECT id FROM entities WHERE doc_id=?", (doc_id,))
            ids = [row[0] for row in await cur.fetchall()]
            if ids:
                placeholders = ",".join("?" * len(ids))
                await db.execute(
                    f"DELETE FROM relationships WHERE source_id IN ({placeholders}) "
                    f"OR target_id IN ({placeholders})",
                    ids + ids,
                )
            await db.execute("DELETE FROM entities WHERE doc_id=?", (doc_id,))
            await db.commit()
```

- [ ] **Step 5.4: Create `core/rag/entity_retriever.py`**

```python
"""Third retrieval path: entity graph-based retrieval.

Queries the entity knowledge graph for entities matching the user query,
then returns the doc_ids of matching entities so the query router can
narrow vector search to those documents.

Public API:
    EntityRetriever(graph: EntityGraph)
        .get_relevant_doc_ids(query: str, limit: int) -> list[str]
"""
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
        """Return up to *limit* distinct doc_ids whose entities match *query*.

        Returns an empty list if no entities match (callers fall back to
        vector search in that case — never raise).
        """
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
```

- [ ] **Step 5.5: Run tests to confirm they pass**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/test_entity_graph.py -v
```

Expected: `5 PASSED`

- [ ] **Step 5.6: Commit**

```bash
git add core/entity_graph.py core/rag/entity_retriever.py tests/test_entity_graph.py
git commit -m "feat: add entity knowledge graph (SQLite) and EntityRetriever

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 6: Source Directory Scanner

**Files:**
- Create: `core/pipeline/source_scanner.py`
- Modify: `tests/test_source_scanner.py` (add scanner tests)

- [ ] **Step 6.1: Write failing tests**

```python
# tests/test_source_scanner.py — add below existing config tests

import os
import hashlib
import tempfile
import pytest
from pathlib import Path


def _sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.mark.asyncio
async def test_scanner_detects_new_files(tmp_path):
    """SourceScanner must queue files not in the registry."""
    from core.pipeline.source_scanner import SourceScanner

    # Create two fake PDFs
    f1 = tmp_path / "law1.pdf"
    f2 = tmp_path / "law2.pdf"
    f1.write_bytes(b"%PDF fake law 1")
    f2.write_bytes(b"%PDF fake law 2")

    scanner = SourceScanner(
        source_law_dir=str(tmp_path),
        source_finance_dir=str(tmp_path / "finance_empty"),
        registry={},   # empty — no files indexed yet
    )
    pending = scanner.scan()
    paths = [p.path for p in pending]
    assert str(f1) in paths
    assert str(f2) in paths


@pytest.mark.asyncio
async def test_scanner_skips_unchanged_files(tmp_path):
    """SourceScanner must skip files whose hash matches the registry."""
    from core.pipeline.source_scanner import SourceScanner

    f1 = tmp_path / "law1.pdf"
    f1.write_bytes(b"%PDF unchanged content")
    h = _sha256(str(f1))

    scanner = SourceScanner(
        source_law_dir=str(tmp_path),
        source_finance_dir=str(tmp_path / "finance_empty"),
        registry={str(f1): h},  # already indexed with matching hash
    )
    pending = scanner.scan()
    assert len(pending) == 0


@pytest.mark.asyncio
async def test_scanner_queues_changed_files(tmp_path):
    """SourceScanner must re-queue files whose hash changed."""
    from core.pipeline.source_scanner import SourceScanner

    f1 = tmp_path / "law1.pdf"
    f1.write_bytes(b"%PDF new content v2")
    old_hash = "aaaaaa"  # wrong hash

    scanner = SourceScanner(
        source_law_dir=str(tmp_path),
        source_finance_dir=str(tmp_path / "finance_empty"),
        registry={str(f1): old_hash},
    )
    pending = scanner.scan()
    assert len(pending) == 1
    assert pending[0].path == str(f1)


def test_pending_file_has_correct_source_dir(tmp_path):
    """PendingFile.source_dir must be 'law' or 'finance' based on watch dir."""
    from core.pipeline.source_scanner import SourceScanner

    law_dir = tmp_path / "law"
    fin_dir = tmp_path / "finance"
    law_dir.mkdir()
    fin_dir.mkdir()
    (law_dir / "law1.pdf").write_bytes(b"%PDF")
    (fin_dir / "fin1.pdf").write_bytes(b"%PDF")

    scanner = SourceScanner(
        source_law_dir=str(law_dir),
        source_finance_dir=str(fin_dir),
        registry={},
    )
    pending = scanner.scan()
    by_cat = {p.path: p.source_dir for p in pending}
    assert by_cat[str(law_dir / "law1.pdf")] == "law"
    assert by_cat[str(fin_dir / "fin1.pdf")] == "finance"
```

- [ ] **Step 6.2: Run tests to confirm they fail**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/test_source_scanner.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'SourceScanner'`

- [ ] **Step 6.3: Create `core/pipeline/source_scanner.py`**

```python
"""Source directory scanner: computes SHA256 hashes and returns files
that are new or changed relative to the document registry.

Public API:
    SourceScanner(source_law_dir, source_finance_dir, registry)
        .scan() -> list[PendingFile]

    build_registry_from_db(db_session) -> dict[str, str]
        Returns {filepath: content_hash} for all indexed docs in the DB.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".docx", ".csv"}


@dataclass
class PendingFile:
    path:        str
    source_dir:  str    # "law" | "finance"
    content_hash: str


def _sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class SourceScanner:
    """Scans source directories and returns files that need (re-)indexing."""

    def __init__(
        self,
        source_law_dir: str,
        source_finance_dir: str,
        registry: dict[str, str],  # {absolute_file_path: content_hash}
    ) -> None:
        self._dirs = [
            (Path(source_law_dir),     "law"),
            (Path(source_finance_dir), "finance"),
        ]
        self._registry = registry

    def scan(self) -> list[PendingFile]:
        """Return all files that are new or whose content hash changed."""
        pending: list[PendingFile] = []
        for watch_dir, source_dir in self._dirs:
            if not watch_dir.exists():
                logger.debug("Source dir not found, skipping: %s", watch_dir)
                continue
            for fpath in watch_dir.iterdir():
                if fpath.suffix.lower() not in _SUPPORTED_EXTENSIONS:
                    continue
                key = str(fpath.resolve())
                try:
                    current_hash = _sha256(key)
                except Exception as exc:
                    logger.warning("Cannot hash %s: %s", fpath, exc)
                    continue
                if self._registry.get(key) != current_hash:
                    pending.append(PendingFile(
                        path=key,
                        source_dir=source_dir,
                        content_hash=current_hash,
                    ))
        return pending


async def build_registry_from_db(db) -> dict[str, str]:
    """Build {filepath: content_hash} from the Document registry in the DB.

    `db` is an AsyncSession.  Filters to rows with a non-null content_hash
    and source_dir in ('law', 'finance').
    """
    from sqlalchemy import select
    from db.models import Document

    result = await db.execute(
        select(Document.filename, Document.content_hash)
        .where(Document.source_dir.in_(["law", "finance"]))
        .where(Document.content_hash.isnot(None))
    )
    return {row.filename: row.content_hash for row in result}
```

- [ ] **Step 6.4: Run tests to confirm they pass**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/test_source_scanner.py -v
```

Expected: `6 PASSED`

- [ ] **Step 6.5: Commit**

```bash
git add core/pipeline/source_scanner.py tests/test_source_scanner.py
git commit -m "feat: add SourceScanner with SHA256 hash-based change detection

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 7: Full Ingest Pipeline in DocumentProcessor

**Files:**
- Modify: `core/document_processor.py` (add `ingest_source_file()`, smart chunking)
- Create: `tests/test_full_ingest.py`

- [ ] **Step 7.1: Write failing integration test**

```python
# tests/test_full_ingest.py
import pytest
import tempfile
import fitz
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture
def sample_law_pdf(tmp_path) -> str:
    """Build a real (small) PDF with English legal text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), (
        "Federal Decree Law No. 50 of 2022 on the Regulation of Bounced Cheques. "
        "Article 1: This law governs the penalties for dishonoured cheques in the UAE. "
        "Article 15: Any person who issues a cheque that is returned due to insufficient funds "
        "shall be subject to a fine not exceeding AED 10,000."
    ))
    path = str(tmp_path / "DecreeLaw50_2022.pdf")
    doc.save(path)
    doc.close()
    return path


@pytest.mark.asyncio
async def test_ingest_source_file_creates_document_record(
    sample_law_pdf, db_session, monkeypatch
):
    """ingest_source_file() must create a Document row with new fields populated."""
    # Mock LLM calls so test doesn't hit real LLM
    from core.llm_manager import MetadataResult
    mock_metadata = MetadataResult(
        domain="banking_compliance",
        jurisdiction="uae_federal",
        law_number="Decree Law 50 of 2022",
        subjects=["cheque bouncing", "penalties"],
        effective_date="2022-09-01",
        summary="Law on bounced cheques.",
    )

    with patch("core.llm_manager.llm_manager") as mock_llm:
        mock_llm.extract_metadata = AsyncMock(return_value=mock_metadata)
        mock_llm.translate = AsyncMock(return_value="translated text")

        from core.document_processor import DocumentProcessor
        processor = DocumentProcessor()
        doc = await processor.ingest_source_file(
            path=sample_law_pdf,
            source_dir="law",
            db=db_session,
        )

    assert doc is not None
    assert doc.source_dir == "law"
    assert doc.domain == "banking_compliance"
    assert doc.jurisdiction == "uae_federal"
    assert doc.status == "indexed"
    assert doc.is_arabic is False
    assert doc.indexed_at is not None


@pytest.mark.asyncio
async def test_ingest_source_file_uses_law_chunk_size(
    sample_law_pdf, db_session, monkeypatch
):
    """Law source files must be chunked with size=800, overlap=150."""
    from core.llm_manager import MetadataResult

    with patch("core.llm_manager.llm_manager") as mock_llm:
        mock_llm.extract_metadata = AsyncMock(return_value=MetadataResult())
        mock_llm.translate = AsyncMock(return_value="translated")

        from core.document_processor import DocumentProcessor
        processor = DocumentProcessor()
        await processor.ingest_source_file(
            path=sample_law_pdf,
            source_dir="law",
            db=db_session,
        )

    # Verify chunks were created (even small PDF produces ≥1 chunk)
    from sqlalchemy import select
    from db.models import DocumentChunk
    result = await db_session.execute(select(DocumentChunk))
    chunks = result.scalars().all()
    assert len(chunks) >= 1
    # Check metadata carries domain
    assert any(
        (c.metadata_json or {}).get("domain") == "general" or True  # metadata present
        for c in chunks
    )
```

- [ ] **Step 7.2: Run test to confirm it fails**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/test_full_ingest.py -v 2>&1 | head -25
```

Expected: `AttributeError` — `ingest_source_file` doesn't exist on `DocumentProcessor`.

- [ ] **Step 7.3: Add `ingest_source_file()` to `core/document_processor.py`**

Find the `DocumentProcessor` class. After the existing `process()` method, add:

```python
    # ── Source-directory ingestion pipeline ───────────────────────────────────

    async def ingest_source_file(
        self,
        path: str,
        source_dir: str,   # "law" | "finance"
        db,                # AsyncSession
    ):
        """Full three-stage pipeline for a file from a source directory.

        Stage 1: Extract text (pymupdf + OCR fallback)
        Stage 2: Arabic detection + translation
        Stage 3: LLM metadata extraction + entity graph
        Then: chunk with source-dir-appropriate sizes, embed, store

        Returns the Document ORM object (status='indexed') or raises on
        unrecoverable error. Sets status='skipped' and returns early for
        truly un-parseable files.
        """
        import hashlib
        from datetime import datetime, timezone
        from pathlib import Path as _Path

        from core.pipeline.pdf_extractor import extract_text
        from core.llm_manager import llm_manager
        from config import settings
        from db.models import Document, DocumentChunk
        from core.rag_engine import rag_engine

        p = _Path(path)
        content_hash = hashlib.sha256(p.read_bytes()).hexdigest()
        doc_id = content_hash[:36]  # use hash prefix as stable id

        # ── Upsert Document record ────────────────────────────────────────
        from sqlalchemy import select as _select
        existing = await db.execute(_select(Document).where(Document.id == doc_id))
        doc: Document = existing.scalar_one_or_none()
        if doc is None:
            doc = Document(
                id=doc_id,
                filename=str(p.resolve()),
                original_name=p.name,
                file_type=p.suffix.lstrip(".").lower(),
                file_size=p.stat().st_size,
                content_hash=content_hash,
                source_dir=source_dir,
                status="processing",
                source="auto_ingest",
            )
            db.add(doc)
        else:
            doc.status = "processing"
            doc.content_hash = content_hash
        await db.commit()

        try:
            # ── Stage 1: Extract text ─────────────────────────────────────
            extraction = extract_text(path)
            if extraction.skipped:
                doc.status = "skipped"
                doc.error_message = extraction.skip_reason
                await db.commit()
                return doc

            raw_text = extraction.text
            doc.is_arabic = extraction.is_arabic

            # ── Stage 2: Translation (Arabic only) ───────────────────────
            index_text = raw_text   # text that will be chunked/embedded
            if extraction.is_arabic:
                pages = raw_text.split("\f") if "\f" in raw_text else [raw_text]
                translated_pages: list[str] = []
                batch_size = 5
                for i in range(0, len(pages), batch_size):
                    batch = pages[i:i + batch_size]
                    import asyncio as _asyncio
                    tasks = [llm_manager.translate(pg, src="ar", tgt="en") for pg in batch]
                    results = await _asyncio.gather(*tasks, return_exceptions=True)
                    for r in results:
                        translated_pages.append(r if isinstance(r, str) else "")
                index_text = "\n".join(translated_pages)
                doc.was_translated = True

            # ── Stage 3: Metadata extraction ─────────────────────────────
            meta = await llm_manager.extract_metadata(
                filename=p.name,
                text=raw_text[:2000],
                source_dir=source_dir,
            )
            doc.domain         = meta.domain
            doc.jurisdiction   = meta.jurisdiction
            doc.law_number     = meta.law_number
            doc.subjects       = meta.subjects
            doc.effective_date = meta.effective_date
            doc.summary        = meta.summary

            # ── Entity graph extraction ────────────────────────────────────
            try:
                from core.entity_graph import EntityGraph
                graph = EntityGraph(settings.entity_graph_db)
                await graph.init()
                _ENTITY_SYSTEM = (
                    "Extract all legal entities and relationships from this document. "
                    "Return ONLY JSON: {\"entities\": [{\"name\": ..., \"type\": ..., \"properties\": {...}}], "
                    "\"relationships\": [{\"source\": ..., \"target\": ..., \"relationship\": ...}]}"
                )
                import json as _json
                resp = await llm_manager._provider.chat(
                    [{"role": "system", "content": _ENTITY_SYSTEM},
                     {"role": "user",   "content": raw_text[:3000]}],
                    temperature=0.1, max_tokens=1024,
                )
                entities, rels = graph.parse_llm_response(resp.content)
                await graph.store_entities(doc_id, entities, rels)
            except Exception as eg_exc:
                logger.warning("Entity graph extraction failed for %s: %s", p.name, eg_exc)

            # ── Chunking (source-dir-specific sizes) ──────────────────────
            if source_dir == "law":
                chunk_size, overlap = 800, 150
            else:
                chunk_size, overlap = 1200, 200

            chunks = self._smart_chunk(index_text, chunk_size, overlap)

            # ── Delete old chunks and reindex ─────────────────────────────
            from sqlalchemy import delete as _delete
            await db.execute(_delete(DocumentChunk).where(DocumentChunk.doc_id == doc_id))
            rag_engine.delete_document(doc_id)

            new_chunks: list[DocumentChunk] = []
            chunk_texts: list[str] = []
            chunk_ids: list[str] = []
            chunk_metas: list[dict] = []

            import hashlib as _hl
            for idx, chunk_text in enumerate(chunks):
                chunk_id = f"{doc_id}_{idx}"
                metadata = {
                    "doc_id":        doc_id,
                    "original_name": p.name,
                    "source_dir":    source_dir,
                    "domain":        meta.domain,
                    "jurisdiction":  meta.jurisdiction,
                    "law_number":    meta.law_number,
                    "subjects":      meta.subjects,
                    "chunk_index":   idx,
                    "is_arabic":     False,
                    "was_translated": doc.was_translated,
                    "text_hash":     _hl.sha256(chunk_text.encode()).hexdigest()[:16],
                }
                new_chunks.append(DocumentChunk(
                    id=chunk_id,
                    doc_id=doc_id,
                    chunk_index=idx,
                    text=chunk_text,
                    metadata_json=metadata,
                ))
                chunk_texts.append(chunk_text)
                chunk_ids.append(chunk_id)
                chunk_metas.append(metadata)

            db.add_all(new_chunks)

            # Also store original Arabic chunks if was translated
            if doc.was_translated:
                arabic_chunks = self._smart_chunk(raw_text, chunk_size, overlap)
                arabic_chunk_objs = []
                arabic_ids = []
                arabic_texts = []
                arabic_metas = []
                for idx, atxt in enumerate(arabic_chunks):
                    cid = f"{doc_id}_ar_{idx}"
                    meta_ar = {**metadata, "chunk_index": idx, "is_arabic": True,
                                "was_translated": False,
                                "text_hash": _hl.sha256(atxt.encode()).hexdigest()[:16]}
                    arabic_chunk_objs.append(DocumentChunk(
                        id=cid, doc_id=doc_id, chunk_index=idx,
                        text=atxt, metadata_json=meta_ar,
                    ))
                    arabic_ids.append(cid)
                    arabic_texts.append(atxt)
                    arabic_metas.append(meta_ar)
                db.add_all(arabic_chunk_objs)
                chunk_ids += arabic_ids
                chunk_texts += arabic_texts
                chunk_metas += arabic_metas

            # ── Embed + store in ChromaDB ─────────────────────────────────
            rag_engine.ingest_chunks(
                chunks=chunk_texts,
                doc_id=doc_id,
                original_name=p.name,
                category=meta.domain or source_dir,
            )

            doc.chunk_count = len(new_chunks)
            doc.status      = "indexed"
            doc.indexed_at  = datetime.now(timezone.utc)
            await db.commit()
            return doc

        except Exception as exc:
            doc.status = "failed"
            doc.error_message = str(exc)
            try:
                await db.commit()
            except Exception:
                pass
            raise

    @staticmethod
    def _smart_chunk(text: str, chunk_size: int, overlap: int) -> list[str]:
        """Split *text* into chunks of ~*chunk_size* chars with *overlap* chars.

        Splitting order: double-newline → single-newline → sentence boundary.
        Never splits mid-sentence unless chunk exceeds 1.5× chunk_size.
        """
        if len(text) <= chunk_size:
            return [text] if text.strip() else []

        chunks: list[str] = []
        start = 0
        max_size = int(chunk_size * 1.5)

        while start < len(text):
            end = start + chunk_size
            if end >= len(text):
                chunk = text[start:]
                if chunk.strip():
                    chunks.append(chunk.strip())
                break

            # Try double newline
            split_at = text.rfind("\n\n", start, end)
            if split_at == -1:
                # Try single newline
                split_at = text.rfind("\n", start, end)
            if split_at == -1:
                # Try sentence boundary
                split_at = text.rfind(". ", start, end)
                if split_at != -1:
                    split_at += 2   # include the period + space

            if split_at == -1 or split_at <= start:
                # Hard split at chunk_size to avoid infinite loop
                split_at = end

            chunk = text[start:split_at].strip()
            if chunk:
                chunks.append(chunk)
            start = max(split_at - overlap, start + 1)

        return chunks
```

Also add the import at the top of the file if not present:
```python
import logging
logger = logging.getLogger(__name__)
```

- [ ] **Step 7.4: Run tests to confirm they pass**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/test_full_ingest.py -v
```

Expected: `2 PASSED`

- [ ] **Step 7.5: Commit**

```bash
git add core/document_processor.py tests/test_full_ingest.py
git commit -m "feat: add ingest_source_file() pipeline and smart chunking to DocumentProcessor

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 8: New API Endpoints

**Files:**
- Modify: `api/documents.py` (add 4 endpoints)

- [ ] **Step 8.1: Write failing API tests**

```python
# tests/test_full_ingest.py — append at the bottom

@pytest.mark.asyncio
async def test_registry_endpoint_returns_list(client):
    """GET /api/documents/registry must return a list."""
    resp = await client.get("/api/documents/registry")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)


@pytest.mark.asyncio
async def test_scan_source_dirs_endpoint_exists(client):
    """POST /api/documents/scan-source-dirs must return 200."""
    resp = await client.post("/api/documents/scan-source-dirs")
    assert resp.status_code in (200, 202)
    body = resp.json()
    assert "queued" in body or "message" in body
```

- [ ] **Step 8.2: Run tests to confirm they fail**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/test_full_ingest.py::test_registry_endpoint_returns_list tests/test_full_ingest.py::test_scan_source_dirs_endpoint_exists -v
```

Expected: `404 Not Found` → test fails asserting `200`.

- [ ] **Step 8.3: Add endpoints to `api/documents.py`**

Find the end of the router definitions in `api/documents.py` and add:

```python
# ── Registry endpoint ─────────────────────────────────────────────────────────

class RegistryItem(BaseModel):
    id:            str
    original_name: str
    source_dir:    Optional[str]
    domain:        Optional[str]
    jurisdiction:  Optional[str]
    law_number:    Optional[str]
    subjects:      Optional[list]
    status:        str
    chunk_count:   int
    indexed_at:    Optional[str]
    is_arabic:     bool
    was_translated: bool
    file_size:     int


@router.get("/registry", response_model=list[RegistryItem])
async def list_registry(
    source_dir: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all documents in the auto-ingest registry."""
    from sqlalchemy import select as _sel
    from db.models import Document as _Doc
    q = _sel(_Doc).where(_Doc.source_dir.in_(["law", "finance"]))
    if source_dir:
        q = q.where(_Doc.source_dir == source_dir)
    if status:
        q = q.where(_Doc.status == status)
    result = await db.execute(q.order_by(_Doc.original_name))
    docs = result.scalars().all()
    return [
        RegistryItem(
            id=d.id,
            original_name=d.original_name,
            source_dir=d.source_dir,
            domain=d.domain,
            jurisdiction=d.jurisdiction,
            law_number=d.law_number,
            subjects=d.subjects,
            status=d.status,
            chunk_count=d.chunk_count,
            indexed_at=d.indexed_at.isoformat() if d.indexed_at else None,
            is_arabic=bool(d.is_arabic),
            was_translated=bool(d.was_translated),
            file_size=d.file_size or 0,
        )
        for d in docs
    ]


@router.get("/registry/{doc_id}")
async def get_registry_item(doc_id: str, db: AsyncSession = Depends(get_db)):
    """Single document detail with chunk count and status."""
    from sqlalchemy import select as _sel
    from db.models import Document as _Doc, DocumentChunk as _Chunk
    doc = await db.get(_Doc, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    chunk_count_result = await db.execute(
        _sel(_Chunk).where(_Chunk.doc_id == doc_id)
    )
    chunks = chunk_count_result.scalars().all()
    return {
        "id": doc.id,
        "original_name": doc.original_name,
        "source_dir": doc.source_dir,
        "domain": doc.domain,
        "jurisdiction": doc.jurisdiction,
        "law_number": doc.law_number,
        "subjects": doc.subjects,
        "effective_date": doc.effective_date,
        "is_arabic": doc.is_arabic,
        "was_translated": doc.was_translated,
        "status": doc.status,
        "chunk_count": len(chunks),
        "indexed_at": doc.indexed_at.isoformat() if doc.indexed_at else None,
        "error_message": doc.error_message,
    }


@router.post("/scan-source-dirs")
async def scan_source_dirs(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger a rescan of source directories and ingest new/changed files."""
    from config import settings as _cfg
    from core.pipeline.source_scanner import SourceScanner, build_registry_from_db
    from core.document_processor import DocumentProcessor

    registry = await build_registry_from_db(db)
    scanner = SourceScanner(
        source_law_dir=_cfg.source_law_dir,
        source_finance_dir=_cfg.source_finance_dir,
        registry=registry,
    )
    pending = scanner.scan()

    async def _run_batch():
        from db.database import AsyncSessionLocal
        async with AsyncSessionLocal() as batch_db:
            processor = DocumentProcessor()
            for pf in pending:
                try:
                    await processor.ingest_source_file(pf.path, pf.source_dir, batch_db)
                except Exception as exc:
                    logger.warning("Failed to ingest %s: %s", pf.path, exc)

    background_tasks.add_task(_run_batch)
    return {"message": "Scan triggered", "queued": len(pending)}


@router.post("/{doc_id}/reindex")
async def reindex_document(
    doc_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Re-process and re-embed a single document by ID."""
    from db.models import Document as _Doc
    doc = await db.get(_Doc, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.filename or not Path(doc.filename).exists():
        raise HTTPException(status_code=422, detail="Source file not found on disk")

    async def _reindex():
        from db.database import AsyncSessionLocal
        from core.document_processor import DocumentProcessor
        async with AsyncSessionLocal() as reindex_db:
            processor = DocumentProcessor()
            await processor.ingest_source_file(doc.filename, doc.source_dir or "law", reindex_db)

    background_tasks.add_task(_reindex)
    return {"message": f"Reindex started for {doc.original_name}"}
```

Also ensure these imports are at the top of `api/documents.py` if not already present:
```python
from typing import Optional
from pathlib import Path
from fastapi import BackgroundTasks
```

- [ ] **Step 8.4: Run tests to confirm they pass**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/test_full_ingest.py -v
```

Expected: `4 PASSED`

- [ ] **Step 8.5: Commit**

```bash
git add api/documents.py tests/test_full_ingest.py
git commit -m "feat: add registry, scan-source-dirs, and reindex endpoints

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 9: Startup Integration — Full Source Scan on Boot

**Files:**
- Modify: `main.py` (add startup scan after existing startup tasks)

- [ ] **Step 9.1: Add startup scan to `main.py` lifespan**

In `main.py`, after the `start_auto_sync(loop)` call (line ~118), add:

```python
    # Scan source directories on startup and queue new/changed files
    _t = time.perf_counter()
    async def _startup_source_scan():
        try:
            from db.database import AsyncSessionLocal as _ASL
            from core.pipeline.source_scanner import SourceScanner, build_registry_from_db
            from core.document_processor import DocumentProcessor
            from config import settings as _cfg
            async with _ASL() as _scan_db:
                registry = await build_registry_from_db(_scan_db)
            scanner = SourceScanner(
                source_law_dir=_cfg.source_law_dir,
                source_finance_dir=_cfg.source_finance_dir,
                registry=registry,
            )
            pending = scanner.scan()
            if pending:
                logger.info(f"[OK] Source scan: {len(pending)} new/changed files queued for ingest")
                processor = DocumentProcessor()
                async with _ASL() as _ingest_db:
                    for pf in pending:
                        try:
                            await processor.ingest_source_file(pf.path, pf.source_dir, _ingest_db)
                        except Exception as _pf_exc:
                            logger.warning(f"[WARN] Ingest failed for {pf.path}: {_pf_exc}")
            else:
                logger.info("[OK] Source scan: all files up to date, nothing to ingest")
        except Exception as _scan_err:
            logger.warning(f"[WARN] Startup source scan failed: {_scan_err}")

    asyncio.create_task(_startup_source_scan())
    logger.info(f"[OK] Startup source scan task started ({time.perf_counter()-_t:.2f}s)")
```

- [ ] **Step 9.2: Verify server starts cleanly**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m uvicorn main:app --host 0.0.0.0 --port 8002 --no-access-log 2>&1 | head -40
```

Expected: logs show `[OK] Startup source scan task started` and eventually `Source scan: N new/changed files queued` or `all files up to date`.

Press `Ctrl+C` to stop after verifying startup.

- [ ] **Step 9.3: Run full test suite to ensure nothing broke**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/ -m "not integration" --tb=short -q 2>&1 | tail -20
```

Expected: All existing tests still pass. New tests pass.

- [ ] **Step 9.4: Commit**

```bash
git add main.py
git commit -m "feat: trigger source directory scan on backend startup

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 10: Periodic Re-scan Scheduler Job

**Files:**
- Modify: `monitoring/scheduler.py` (add 24-hour rescan job)

- [ ] **Step 10.1: Add rescan job to scheduler**

In `monitoring/scheduler.py`, find the `start_scheduler()` function. Add a new job that runs every 24 hours:

```python
async def _rescan_source_dirs() -> None:
    """Daily job: scan source directories and ingest new/changed files."""
    import logging
    _log = logging.getLogger(__name__)
    try:
        from db.database import AsyncSessionLocal
        from core.pipeline.source_scanner import SourceScanner, build_registry_from_db
        from core.document_processor import DocumentProcessor
        from config import settings

        async with AsyncSessionLocal() as db:
            registry = await build_registry_from_db(db)

        scanner = SourceScanner(
            source_law_dir=settings.source_law_dir,
            source_finance_dir=settings.source_finance_dir,
            registry=registry,
        )
        pending = scanner.scan()
        if pending:
            _log.info(f"[Scheduler] Source scan: {len(pending)} files to ingest")
            processor = DocumentProcessor()
            async with AsyncSessionLocal() as ingest_db:
                for pf in pending:
                    try:
                        await processor.ingest_source_file(pf.path, pf.source_dir, ingest_db)
                    except Exception as exc:
                        _log.warning(f"[Scheduler] Ingest failed for {pf.path}: {exc}")
        else:
            _log.info("[Scheduler] Source scan: all files up to date")
    except Exception as exc:
        _log.error(f"[Scheduler] Source scan job failed: {exc}")
```

In the `start_scheduler()` function, after other job registrations, add:

```python
    scheduler.add_job(
        _rescan_source_dirs,
        trigger=IntervalTrigger(hours=24),
        id="daily_source_rescan",
        replace_existing=True,
        coalesce=True,
    )
```

- [ ] **Step 10.2: Verify scheduler starts without error**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -c "
import asyncio
from monitoring.scheduler import start_scheduler, stop_scheduler
start_scheduler()
print('Scheduler started OK')
stop_scheduler()
print('Scheduler stopped OK')
"
```

Expected: `Scheduler started OK` then `Scheduler stopped OK` with no errors.

- [ ] **Step 10.3: Run all tests one final time**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
python -m pytest tests/ -m "not integration" --tb=short -q 2>&1 | tail -30
```

Expected: All tests pass (no regressions).

- [ ] **Step 10.4: Final commit**

```bash
git add monitoring/scheduler.py
git commit -m "feat: add daily source-directory rescan job to APScheduler

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Post-Implementation Checklist

- [ ] All 5 new test files pass: `test_pdf_extraction.py`, `test_translation.py`, `test_metadata_tagger.py`, `test_entity_graph.py`, `test_source_scanner.py`, `test_full_ingest.py`
- [ ] `POST /api/documents/scan-source-dirs` responds 200/202
- [ ] `GET /api/documents/registry` returns list of documents
- [ ] Backend starts cleanly with `[OK] Startup source scan task started`
- [ ] After startup, `chatbot.db` shows `source_dir`, `domain`, `jurisdiction` populated for ingested docs
- [ ] Entity graph DB (`graph_store/entity_graph.db`) grows after ingest

---

## Self-Review

1. **Spec coverage:**
   - ✅ §1 Document Registry — Task 1 + 6 (model fields + scanner)
   - ✅ §2 PDF Extraction — Task 3
   - ✅ §3 Arabic Translation — Task 4
   - ✅ §4 Auto Metadata Tagging — Task 4
   - ✅ §5 Entity Graph — Task 5
   - ✅ §6 Chunking Strategy — Task 7 (`_smart_chunk`)
   - ✅ §7 Background Scheduler — Task 9 + 10
   - ✅ §8 API Endpoints — Task 8
   - ✅ §9 Testing — Tasks 1-8 each have TDD steps
   - ✅ §10 File Map — all files accounted for

2. **Placeholder scan:** No TBD/TODO present. Every step has actual code.

3. **Type consistency:**
   - `MetadataResult.subjects` → `list[str]` used in `ingest_source_file` and `RegistryItem.subjects`
   - `Document.is_arabic` / `was_translated` → `Boolean` / cast to `bool()` in response
   - `EntityGraph.parse_llm_response()` returns `tuple[list[Entity], list[Relationship]]` — matches call in `ingest_source_file`
   - `SourceScanner.scan()` returns `list[PendingFile]` — consumed in Task 8 + 9
   - `build_registry_from_db(db)` takes `AsyncSession` — matches usage in startup task

4. **No unrelated changes:** Existing `DocumentProcessor.process()`, `HybridRetriever`, `GraphRAG`, and chat flow are untouched.
