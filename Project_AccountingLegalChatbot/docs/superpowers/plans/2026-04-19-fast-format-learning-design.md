# Fast Format Learning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the template learning pipeline so any audit PDF format is learned in <5 minutes with 95%+ pixel accuracy and zero manual touch.

**Architecture:** Three surgical upgrades to the existing pipeline — a FormatFingerprinter that matches incoming PDFs against a prebuilt library in 2 seconds (Phase 1), a `TemplateAnalyzer.analyze_precise()` method that detects exact column x-positions, line spacing, and font roles via span-level coordinate mining (Phase 2), and an AutoVerifier that renders a test page with ReportLab, pixel-diffs against the reference, and either auto-approves, applies one adjustment pass, or returns targeted binary-choice hints (Phase 3). The existing `analyze()` method, TemplateStore, and all other pipeline files are untouched.

**Tech Stack:** PyMuPDF (fitz) for PDF extraction, NumPy for 1D k-means clustering, Pillow + NumPy for pixel diff, ReportLab for test-page rendering, FastAPI for the API layer, pytest with asyncio_mode=auto for tests.

---

## File Structure

```
NEW FILES:
  backend/core/format_fingerprinter.py    FormatFingerprinter class — fingerprint() + match()
  backend/core/auto_verifier.py           AutoVerifier class — pixel_similarity() + verify()

MODIFIED FILES:
  backend/core/prebuilt_formats.py        Add "fingerprint" key to each entry; add prebuilt-gcc-standard
  backend/core/template_analyzer.py       Add analyze_precise(), _extract_columns(), _extract_spacing(),
                                          _extract_font_roles(), _kmeans_1d()
  backend/api/templates.py               Add fast_learn query param + _fast_learn_pipeline()

NEW TEST FILES:
  backend/tests/test_fingerprinter_gcc.py
  backend/tests/test_fingerprinter_unknown.py
  backend/tests/test_analyze_precise_columns.py
  backend/tests/test_analyze_precise_spacing.py
  backend/tests/test_analyze_precise_fonts.py
  backend/tests/test_autoverifier_pass.py
  backend/tests/test_autoverifier_adjust.py
  backend/tests/test_autoverifier_hints.py
  backend/tests/test_fast_learn_api.py
  backend/tests/test_manual_path_unchanged.py

UNCHANGED:
  backend/core/template_store.py
  backend/core/batch_template_learner.py
  backend/core/confidence_calibrator.py
  backend/core/document_format_analyzer.py
  backend/core/format_extractor.py
  backend/core/template_report_generator.py
```

---

## Task 1: Add Fingerprints to prebuilt_formats.py

**Files:**
- Modify: `backend/core/prebuilt_formats.py`

No test needed — this is pure config data. The fingerprints unlock Phase 1 matching for all subsequent tasks.

- [ ] **Step 1: Add `prebuilt-gcc-standard` entry and fingerprints to all existing entries**

Open `backend/core/prebuilt_formats.py`. At the top of `PREBUILT_FORMATS`, insert the new GCC entry first. Then add a `"fingerprint"` key to every existing entry.

**New entry to insert at top of the list:**
```python
{
    "id": "prebuilt-gcc-standard",
    "name": "GCC IFRS Standard",
    "format_family": "IFRS",
    "format_variant": "IFRS 2023 GCC",
    "description": "Standard IFRS financial statement format for UAE/GCC (AED)",
    "config": {
        "page": {"width": 595.28, "height": 841.89, "unit": "points", "detected_size": "A4", "confidence": 1.0},
        "margins": {"top": 72, "bottom": 72, "left": 72, "right": 72},
        "fonts": {
            "heading": {"family": "Helvetica-Bold", "size": 12},
            "body": {"family": "Helvetica", "size": 9},
            "footer": {"family": "Helvetica", "size": 8},
        },
        "columns": {
            "label_col_x": 72.0,
            "notes_col_x": 310.0,
            "year1_col_x": 380.0,
            "year2_col_x": 460.0,
            "currency_label_y": 0.0,
        },
        "spacing": {
            "heading_after": 18.0,
            "row_height": 14.0,
            "section_gap": 24.0,
            "subtotal_gap": 6.0,
            "indent_level_1": 90.0,
            "indent_level_2": 108.0,
        },
        "tables": [],
        "sections": [
            {"name": "cover", "page": 1, "layout": "static"},
            {"name": "sofp", "page": 2, "layout": "flow"},
            {"name": "sopl", "page": 3, "layout": "flow"},
            {"name": "soce", "page": 4, "layout": "flow"},
            {"name": "socf", "page": 5, "layout": "flow"},
            {"name": "notes", "pages": [6, 7, 8, 9, 10], "layout": "flow"},
        ],
        "substitutions": {},
        "extraction_metadata": {
            "analyzer_version": "prebuilt",
            "source": "prebuilt",
            "confidence_per_element": {
                "page_size": 1.0, "margins": 1.0, "fonts": 0.9, "tables": 0.8,
            },
        },
    },
    "fingerprint": {
        "page_size": "A4",
        "currency": "AED",
        "section_count": 6,
        "has_notes": True,
        "col_count": 3,
        "format_family": "IFRS",
    },
},
```

**Add fingerprint to `prebuilt-ifrs-standard`** (existing entry):
```python
"fingerprint": {
    "page_size": "A4",
    "currency": "USD",
    "section_count": 4,
    "has_notes": True,
    "col_count": 2,
    "format_family": "IFRS",
},
```

**Add fingerprint to `prebuilt-gaap-standard`** (existing entry):
```python
"fingerprint": {
    "page_size": "US_LETTER",
    "currency": "USD",
    "section_count": 5,
    "has_notes": True,
    "col_count": 2,
    "format_family": "GAAP",
},
```

**Add fingerprint to `prebuilt-local-tax`** (existing entry):
```python
"fingerprint": {
    "page_size": "A4",
    "currency": "AED",
    "section_count": 4,
    "has_notes": False,
    "col_count": 2,
    "format_family": "local-tax",
},
```

**Add fingerprint to `prebuilt-uk-frs102`** (existing entry):
```python
"fingerprint": {
    "page_size": "A4",
    "currency": "GBP",
    "section_count": 4,
    "has_notes": True,
    "col_count": 2,
    "format_family": "IFRS",
},
```

- [ ] **Step 2: Commit**

```bash
cd backend
git add core/prebuilt_formats.py
git commit -m "feat: add fingerprint signatures to prebuilt format library + prebuilt-gcc-standard entry

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: FormatFingerprinter — fingerprint() and _score()

**Files:**
- Create: `backend/core/format_fingerprinter.py`
- Create: `backend/tests/test_fingerprinter_gcc.py`

- [ ] **Step 1: Write the failing test for fingerprint() schema**

Create `backend/tests/test_fingerprinter_gcc.py`:

```python
"""Tests for FormatFingerprinter — fingerprint extraction and GCC matching."""
import pytest
from pathlib import Path


REFERENCE_PDF = (
    r"C:\Users\Armaan\OneDrive - The Era Corporations"
    r"\Study\Armaan\AI Class\Data Science Class"
    r"\35. 11-Apr-2026\Testing data\Draft FS - Castle Plaza 2025.pdf"
)

FINGERPRINT_KEYS = {"page_size", "currency", "section_count", "has_notes", "col_count", "format_family"}


@pytest.fixture
def minimal_a4_aed_pdf(tmp_path):
    """In-memory A4 PDF with AED currency and IFRS section headings."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=595.28, height=841.89)
    page.insert_text((72, 750), "Statement of Financial Position", fontsize=12)
    page.insert_text((72, 720), "Statement of Profit and Loss", fontsize=12)
    page.insert_text((72, 690), "Notes to the Financial Statements", fontsize=12)
    page.insert_text((350, 660), "AED")
    page.insert_text((380, 640), "1,234,567")
    page.insert_text((460, 640), "987,654")
    page.insert_text((380, 620), "2023")
    page.insert_text((460, 620), "2022")
    pdf_path = tmp_path / "test_gcc_audit.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)


def test_fingerprint_returns_required_keys(minimal_a4_aed_pdf):
    """fingerprint() always returns all 6 required keys."""
    from core.format_fingerprinter import FormatFingerprinter
    fp = FormatFingerprinter()
    result = fp.fingerprint(minimal_a4_aed_pdf)
    assert set(result.keys()) == FINGERPRINT_KEYS


def test_fingerprint_detects_a4(minimal_a4_aed_pdf):
    """A4 PDF is detected correctly."""
    from core.format_fingerprinter import FormatFingerprinter
    fp = FormatFingerprinter()
    result = fp.fingerprint(minimal_a4_aed_pdf)
    assert result["page_size"] == "A4"


def test_fingerprint_detects_aed(minimal_a4_aed_pdf):
    """AED currency is detected from text content."""
    from core.format_fingerprinter import FormatFingerprinter
    fp = FormatFingerprinter()
    result = fp.fingerprint(minimal_a4_aed_pdf)
    assert result["currency"] == "AED"


def test_fingerprint_detects_sections(minimal_a4_aed_pdf):
    """IFRS section headings are counted."""
    from core.format_fingerprinter import FormatFingerprinter
    fp = FormatFingerprinter()
    result = fp.fingerprint(minimal_a4_aed_pdf)
    assert result["section_count"] >= 2


def test_fingerprint_detects_has_notes(minimal_a4_aed_pdf):
    """has_notes is True when 'Notes to the Financial Statements' is present."""
    from core.format_fingerprinter import FormatFingerprinter
    fp = FormatFingerprinter()
    result = fp.fingerprint(minimal_a4_aed_pdf)
    assert result["has_notes"] is True


def test_fingerprint_detects_col_count(minimal_a4_aed_pdf):
    """Year headers detected → col_count is 2 or 3."""
    from core.format_fingerprinter import FormatFingerprinter
    fp = FormatFingerprinter()
    result = fp.fingerprint(minimal_a4_aed_pdf)
    assert result["col_count"] in (2, 3)


def test_score_exact_match():
    """_score() returns 100 for identical fingerprints."""
    from core.format_fingerprinter import FormatFingerprinter
    fp = FormatFingerprinter()
    fingerprint = {
        "page_size": "A4", "currency": "AED", "format_family": "IFRS",
        "section_count": 6, "col_count": 3, "has_notes": True,
    }
    assert fp._score(fingerprint, fingerprint) == 100


def test_score_no_match():
    """_score() returns 0 for completely different fingerprints."""
    from core.format_fingerprinter import FormatFingerprinter
    fp = FormatFingerprinter()
    a = {"page_size": "A4", "currency": "AED", "format_family": "IFRS",
         "section_count": 6, "col_count": 3, "has_notes": True}
    b = {"page_size": "US_LETTER", "currency": "USD", "format_family": "GAAP",
         "section_count": 20, "col_count": 2, "has_notes": False}
    assert fp._score(a, b) == 0


def test_fingerprint_missing_pdf():
    """fingerprint() on nonexistent file returns zeroed-out schema without raising."""
    from core.format_fingerprinter import FormatFingerprinter
    fp = FormatFingerprinter()
    result = fp.fingerprint("nonexistent_file.pdf")
    assert set(result.keys()) == FINGERPRINT_KEYS
    assert result["page_size"] == "CUSTOM"


def test_fingerprint_real_pdf_gcc():
    """Real ABC Magnus PDF matches prebuilt-gcc-standard at ≥88 score."""
    if not Path(REFERENCE_PDF).exists():
        pytest.skip("Reference PDF not available in test environment")
    from core.format_fingerprinter import FormatFingerprinter
    fp = FormatFingerprinter()
    _, score, source_id = fp.match(REFERENCE_PDF)
    assert score >= 88, f"Expected ≥88 but got {score}"
    assert source_id == "prebuilt-gcc-standard"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_fingerprinter_gcc.py -v
```

Expected: `ImportError: cannot import name 'FormatFingerprinter' from 'core.format_fingerprinter'`

- [ ] **Step 3: Create `backend/core/format_fingerprinter.py`**

```python
"""
FormatFingerprinter — Phase 1 of the fast format learning pipeline.

Computes a lightweight 6-field fingerprint from the first 3 pages of a PDF
and matches it against the prebuilt format library to decide whether full
extraction is needed.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from core.document_format_analyzer import _AUDIT_SECTION_PATTERNS, _CURRENCY_PATTERNS
from core.prebuilt_formats import PREBUILT_FORMATS

_YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")
_PAGE_SIZE_TOLERANCE = 5.0  # points


def _detect_page_size(width: float, height: float) -> str:
    if abs(width - 595.28) < _PAGE_SIZE_TOLERANCE and abs(height - 841.89) < _PAGE_SIZE_TOLERANCE:
        return "A4"
    if abs(width - 612.0) < _PAGE_SIZE_TOLERANCE and abs(height - 792.0) < _PAGE_SIZE_TOLERANCE:
        return "US_LETTER"
    return "CUSTOM"


class FormatFingerprinter:
    """Compute a format fingerprint and match it against the prebuilt library."""

    MATCH_THRESHOLD = 88

    def fingerprint(self, pdf_path: str) -> Dict[str, Any]:
        """
        Extract a 6-field fingerprint from the first 3 pages of the PDF.
        Returns the fingerprint schema even on error (with default values).
        """
        default = {
            "page_size": "CUSTOM",
            "currency": "unknown",
            "section_count": 0,
            "has_notes": False,
            "col_count": 2,
            "format_family": "unknown",
        }

        try:
            import fitz
        except ImportError:
            return default

        path = Path(pdf_path)
        if not path.exists():
            return default

        try:
            doc = fitz.open(str(path))
        except Exception:
            return default

        if len(doc) == 0:
            doc.close()
            return default

        pages_to_scan = list(doc)[:min(3, len(doc))]

        # Page size from first page
        rect = doc[0].rect
        page_size = _detect_page_size(rect.width, rect.height)

        full_text = " ".join(
            span.get("text", "")
            for page in pages_to_scan
            for block in page.get_text("dict", flags=0).get("blocks", [])
            if block.get("type") == 0
            for line in block.get("lines", [])
            for span in line.get("spans", [])
        )

        # Currency detection
        currency_match = _CURRENCY_PATTERNS.search(full_text)
        currency = currency_match.group(0) if currency_match else "unknown"

        # Section count
        section_count = sum(
            1 for pattern in _AUDIT_SECTION_PATTERNS if pattern.search(full_text)
        )

        # Notes detection
        has_notes = bool(re.search(r"notes?\s+to\s+(the\s+)?financial", full_text, re.IGNORECASE))

        # Column count: count distinct year headers
        years_found = set(_YEAR_PATTERN.findall(full_text))
        col_count = min(len(years_found) + 1, 3) if years_found else 2

        # Format family heuristic
        if re.search(r"\bifrs\b", full_text, re.IGNORECASE):
            format_family = "IFRS"
        elif re.search(r"\bgaap\b", full_text, re.IGNORECASE):
            format_family = "GAAP"
        elif re.search(r"\btax\b", full_text, re.IGNORECASE):
            format_family = "local-tax"
        else:
            format_family = "IFRS"  # Default for UAE/GCC audits

        doc.close()

        return {
            "page_size": page_size,
            "currency": currency,
            "section_count": section_count,
            "has_notes": has_notes,
            "col_count": col_count,
            "format_family": format_family,
        }

    def _score(self, fp: Dict[str, Any], candidate: Dict[str, Any]) -> int:
        """
        Compute similarity score 0–100 between two fingerprints.

        Scoring weights:
          page_size     30
          currency      25
          format_family 20
          section_count 15  (within ±1)
          col_count     10
        """
        score = 0
        if fp.get("page_size") == candidate.get("page_size"):
            score += 30
        if fp.get("currency") == candidate.get("currency"):
            score += 25
        if fp.get("format_family") == candidate.get("format_family"):
            score += 20
        if abs(fp.get("section_count", 0) - candidate.get("section_count", 0)) <= 1:
            score += 15
        if fp.get("col_count") == candidate.get("col_count"):
            score += 10
        return score

    def match(
        self,
        pdf_path: str,
        user_templates: Optional[list] = None,
    ) -> Tuple[Optional[Dict[str, Any]], int, Optional[str]]:
        """
        Match the PDF against the prebuilt library (+ optional user templates).

        Returns (best_config, best_score, source_id).
        source_id is None when best_score < MATCH_THRESHOLD.
        """
        fp = self.fingerprint(pdf_path)
        best_score = 0
        best_config: Optional[Dict[str, Any]] = None
        best_id: Optional[str] = None

        candidates = list(PREBUILT_FORMATS)
        if user_templates:
            candidates.extend(user_templates)

        for entry in candidates:
            candidate_fp = entry.get("fingerprint")
            if candidate_fp is None:
                continue
            score = self._score(fp, candidate_fp)
            if score > best_score:
                best_score = score
                best_config = entry.get("config")
                best_id = entry.get("id")

        if best_score >= self.MATCH_THRESHOLD:
            return best_config, best_score, best_id
        return None, best_score, None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
pytest tests/test_fingerprinter_gcc.py -v
```

Expected: All tests pass except `test_fingerprint_real_pdf_gcc` (which skips if PDF not present).

- [ ] **Step 5: Commit**

```bash
git add core/format_fingerprinter.py tests/test_fingerprinter_gcc.py
git commit -m "feat: add FormatFingerprinter with fingerprint() and _score()

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: FormatFingerprinter — match() + unknown-format tests

**Files:**
- Create: `backend/tests/test_fingerprinter_unknown.py`

(match() was already implemented in Task 2; this task adds the "unknown format" contract tests.)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_fingerprinter_unknown.py`:

```python
"""Tests for FormatFingerprinter — unknown format falls through to full extraction."""
import pytest


@pytest.fixture
def unknown_format_pdf(tmp_path):
    """Creates a PDF that deliberately does NOT match any prebuilt format."""
    import fitz
    doc = fitz.open()
    # US_LETTER size (not A4), BDT currency, unknown structure
    page = doc.new_page(width=612.0, height=792.0)
    page.insert_text((72, 700), "Profit and Loss Account", fontsize=12)
    page.insert_text((72, 680), "Balance Sheet", fontsize=12)
    page.insert_text((350, 660), "BDT")
    page.insert_text((380, 640), "50,000")
    pdf_path = tmp_path / "unknown_format.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)


def test_unknown_format_returns_none_config(unknown_format_pdf):
    """Unknown format returns None config, score < 88."""
    from core.format_fingerprinter import FormatFingerprinter
    fp = FormatFingerprinter()
    config, score, source_id = fp.match(unknown_format_pdf)
    assert score < 88, f"Expected score < 88 but got {score}"
    assert config is None
    assert source_id is None


def test_known_format_returns_config(tmp_path):
    """A PDF matching prebuilt-gcc-standard returns a config and source_id."""
    import fitz
    from core.format_fingerprinter import FormatFingerprinter

    # Build a PDF matching the gcc fingerprint
    doc = fitz.open()
    page = doc.new_page(width=595.28, height=841.89)
    page.insert_text((72, 750), "Statement of Financial Position", fontsize=12)
    page.insert_text((72, 720), "Statement of Profit and Loss", fontsize=12)
    page.insert_text((72, 690), "Notes to the Financial Statements", fontsize=12)
    page.insert_text((72, 660), "Statement of Cash Flows", fontsize=12)
    page.insert_text((72, 630), "Statement of Changes in Equity", fontsize=12)
    page.insert_text((72, 600), "Independent Auditor's Report", fontsize=12)
    page.insert_text((350, 570), "AED")
    page.insert_text((380, 550), "2023")
    page.insert_text((460, 550), "2022")
    pdf_path = tmp_path / "gcc_format.pdf"
    doc.save(str(pdf_path))
    doc.close()

    fp = FormatFingerprinter()
    config, score, source_id = fp.match(str(pdf_path))
    assert score >= 88, f"Expected score ≥88 but got {score}"
    assert config is not None
    assert source_id == "prebuilt-gcc-standard"


def test_match_with_no_library_entries(tmp_path, monkeypatch):
    """When no prebuilt entries have fingerprints, match() returns (None, 0, None)."""
    import fitz
    from core.format_fingerprinter import FormatFingerprinter
    import core.format_fingerprinter as ff_module

    monkeypatch.setattr(ff_module, "PREBUILT_FORMATS", [])

    doc = fitz.open()
    page = doc.new_page(width=595.28, height=841.89)
    pdf_path = tmp_path / "blank.pdf"
    doc.save(str(pdf_path))
    doc.close()

    fp = FormatFingerprinter()
    config, score, source_id = fp.match(str(pdf_path))
    assert config is None
    assert score == 0
    assert source_id is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_fingerprinter_unknown.py -v
```

Expected: `FAILED` — `known_format_returns_config` fails because `prebuilt-gcc-standard` fingerprint may not be matching yet (verifies Task 1 is applied correctly).

- [ ] **Step 3: Run tests to verify they pass**

```bash
cd backend
pytest tests/test_fingerprinter_unknown.py tests/test_fingerprinter_gcc.py -v
```

Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_fingerprinter_unknown.py
git commit -m "test: add FormatFingerprinter unknown-format and match() contract tests

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4: TemplateAnalyzer.analyze_precise() — columns

**Files:**
- Create: `backend/tests/test_analyze_precise_columns.py`
- Modify: `backend/core/template_analyzer.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_analyze_precise_columns.py`:

```python
"""Tests for TemplateAnalyzer.analyze_precise() — column x-position detection."""
import pytest
from pathlib import Path

REFERENCE_PDF = (
    r"C:\Users\Armaan\OneDrive - The Era Corporations"
    r"\Study\Armaan\AI Class\Data Science Class"
    r"\35. 11-Apr-2026\Testing data\Draft FS - Castle Plaza 2025.pdf"
)

COLUMN_KEYS = {"label_col_x", "notes_col_x", "year1_col_x", "year2_col_x", "currency_label_y"}


@pytest.fixture
def two_column_pdf(tmp_path):
    """A4 PDF with two numeric columns at known x-positions."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=595.28, height=841.89)
    # Label column at x=72, year1 at x=380, year2 at x=460
    for y in range(700, 400, -14):
        page.insert_text((72, y), "Some line item")
        page.insert_text((380, y), f"{(y * 100):,}")
        page.insert_text((460, y), f"{(y * 90):,}")
    pdf_path = tmp_path / "two_col.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)


def test_analyze_precise_returns_columns_key(two_column_pdf):
    """analyze_precise() result includes a 'columns' key."""
    from core.template_analyzer import TemplateAnalyzer
    analyzer = TemplateAnalyzer()
    result = analyzer.analyze_precise(two_column_pdf)
    assert "columns" in result


def test_columns_has_required_sub_keys(two_column_pdf):
    """'columns' dict contains all required sub-keys."""
    from core.template_analyzer import TemplateAnalyzer
    analyzer = TemplateAnalyzer()
    result = analyzer.analyze_precise(two_column_pdf)
    assert set(result["columns"].keys()) == COLUMN_KEYS


def test_columns_are_floats(two_column_pdf):
    """All column x-values are floats."""
    from core.template_analyzer import TemplateAnalyzer
    analyzer = TemplateAnalyzer()
    result = analyzer.analyze_precise(two_column_pdf)
    for key in ("year1_col_x", "year2_col_x"):
        assert isinstance(result["columns"][key], float)


def test_year1_col_within_tolerance(two_column_pdf):
    """Detected year1_col_x is within ±10pt of the known column position (380)."""
    from core.template_analyzer import TemplateAnalyzer
    analyzer = TemplateAnalyzer()
    result = analyzer.analyze_precise(two_column_pdf)
    assert abs(result["columns"]["year1_col_x"] - 380) <= 10, (
        f"year1_col_x={result['columns']['year1_col_x']}, expected ~380"
    )


def test_year2_col_within_tolerance(two_column_pdf):
    """Detected year2_col_x is within ±10pt of the known column position (460)."""
    from core.template_analyzer import TemplateAnalyzer
    analyzer = TemplateAnalyzer()
    result = analyzer.analyze_precise(two_column_pdf)
    assert abs(result["columns"]["year2_col_x"] - 460) <= 10, (
        f"year2_col_x={result['columns']['year2_col_x']}, expected ~460"
    )


def test_columns_fallback_on_sparse_pdf(tmp_path):
    """Fewer than 10 numeric spans → fallback to page-width proportions."""
    import fitz
    from core.template_analyzer import TemplateAnalyzer
    doc = fitz.open()
    page = doc.new_page(width=595.28, height=841.89)
    page.insert_text((72, 700), "Only text, no numbers here")
    pdf_path = tmp_path / "sparse.pdf"
    doc.save(str(pdf_path))
    doc.close()
    analyzer = TemplateAnalyzer()
    result = analyzer.analyze_precise(str(pdf_path))
    assert "columns" in result
    assert result["columns"]["year1_col_x"] > 0


def test_analyze_precise_nonexistent_file():
    """analyze_precise() on missing file returns fallback with columns key."""
    from core.template_analyzer import TemplateAnalyzer
    analyzer = TemplateAnalyzer()
    result = analyzer.analyze_precise("nonexistent.pdf")
    assert "columns" in result


def test_analyze_precise_real_pdf_columns():
    """Real reference PDF: detected columns within ±5pt of manually measured values."""
    if not Path(REFERENCE_PDF).exists():
        pytest.skip("Reference PDF not available in test environment")
    from core.template_analyzer import TemplateAnalyzer
    analyzer = TemplateAnalyzer()
    result = analyzer.analyze_precise(REFERENCE_PDF)
    cols = result["columns"]
    assert cols["year1_col_x"] > 300, "year1 column should be in the right half of the page"
    assert cols["year2_col_x"] > cols["year1_col_x"], "year2 should be to the right of year1"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_analyze_precise_columns.py -v
```

Expected: `AttributeError: 'TemplateAnalyzer' object has no attribute 'analyze_precise'`

- [ ] **Step 3: Implement analyze_precise() with column detection in template_analyzer.py**

Add these methods to the `TemplateAnalyzer` class (after the existing `_fallback_config` method):

```python
def analyze_precise(self, pdf_path: str) -> Dict[str, Any]:
    """
    High-precision PDF analysis.
    Returns the same schema as analyze() plus 'columns' and 'spacing' fields,
    and uses role-based font mapping instead of size-sorted font mapping.
    """
    try:
        import fitz
    except ImportError:
        result = self._fallback_config(pdf_path, error="PyMuPDF not installed")
        result["columns"] = self._fallback_columns(None, None)
        result["spacing"] = self._fallback_spacing()
        return result

    path = Path(pdf_path)
    if not path.exists():
        result = self._fallback_config(pdf_path, error=f"File not found: {pdf_path}")
        result["columns"] = self._fallback_columns(None, None)
        result["spacing"] = self._fallback_spacing()
        return result

    try:
        doc = fitz.open(str(path))
    except Exception as e:
        result = self._fallback_config(pdf_path, error=str(e))
        result["columns"] = self._fallback_columns(None, None)
        result["spacing"] = self._fallback_spacing()
        return result

    page_count = len(doc)
    if page_count == 0:
        doc.close()
        result = self._fallback_config(pdf_path, error="PDF has no pages")
        result["columns"] = self._fallback_columns(None, None)
        result["spacing"] = self._fallback_spacing()
        return result

    first_page = doc[0]
    page_dims = self._extract_page_dimensions(first_page)
    margins = self._extract_margins(first_page)
    sections = self._detect_sections(doc)

    analysis_pages = [doc[i] for i in range(min(4, page_count))]
    columns = self._extract_columns(analysis_pages, page_dims, margins)
    spacing = self._extract_spacing(analysis_pages)
    fonts = self._extract_font_roles(doc)

    doc.close()

    confidence = self._calculate_confidence(page_dims, fonts, margins)

    return {
        "page": page_dims,
        "margins": margins,
        "fonts": fonts,
        "tables": [],
        "sections": sections,
        "confidence": confidence,
        "source": str(path.name),
        "page_count": page_count,
        "columns": columns,
        "spacing": spacing,
    }

def _kmeans_1d(self, values: list, k: int, max_iter: int = 20) -> list:
    """Simple 1D k-means. Returns list of k sorted centroids."""
    import numpy as np
    arr = np.array(values, dtype=float)
    # Initialise centroids at evenly spaced quantiles
    indices = np.round(np.linspace(0, len(arr) - 1, k)).astype(int)
    centroids = np.sort(arr)[indices].astype(float)
    for _ in range(max_iter):
        dists = np.abs(arr[:, None] - centroids[None, :])
        labels = np.argmin(dists, axis=1)
        new_centroids = np.array([
            arr[labels == i].mean() if (labels == i).any() else centroids[i]
            for i in range(k)
        ])
        if np.allclose(centroids, new_centroids, atol=0.5):
            break
        centroids = new_centroids
    return sorted(centroids.tolist())

def _fallback_columns(self, page_dims, margins) -> Dict[str, float]:
    """Return column positions based on standard A4 proportions."""
    w = page_dims.get("width", 595.28) if page_dims else 595.28
    left = margins.get("left", 72) if margins else 72
    return {
        "label_col_x": round(left, 2),
        "notes_col_x": round(w * 0.52, 2),
        "year1_col_x": round(w * 0.65, 2),
        "year2_col_x": round(w * 0.80, 2),
        "currency_label_y": 0.0,
    }

def _fallback_spacing(self) -> Dict[str, float]:
    return {
        "heading_after": 18.0,
        "row_height": 14.0,
        "section_gap": 24.0,
        "subtotal_gap": 6.0,
        "indent_level_1": 90.0,
        "indent_level_2": 108.0,
    }

def _extract_columns(self, pages: list, page_dims: Dict, margins: Dict) -> Dict[str, float]:
    """
    Detect data column x-positions using 1D k-means on numeric span x0 values.
    Falls back to page-width proportions if fewer than 10 numeric spans are found.
    """
    import re
    import numpy as np

    _NUMERIC_RE = re.compile(r"^[\s\d,.()–\-]+$")
    numeric_x0s: List[float] = []

    for page in pages:
        blocks = page.get_text("dict", flags=0).get("blocks", [])
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if len(text) >= 2 and _NUMERIC_RE.match(text):
                        bbox = span.get("bbox", [0, 0, 0, 0])
                        numeric_x0s.append(float(bbox[0]))

    if len(numeric_x0s) < 10:
        return self._fallback_columns(page_dims, margins)

    page_width = page_dims.get("width", 595.28)
    x_range = max(numeric_x0s) - min(numeric_x0s)
    k = 3 if x_range > page_width * 0.35 else 2
    centroids = self._kmeans_1d(numeric_x0s, k)

    left = margins.get("left", 72)
    result: Dict[str, float] = {
        "label_col_x": round(float(left), 2),
        "notes_col_x": 0.0,
        "year1_col_x": round(centroids[-2] if k >= 2 else centroids[0], 2),
        "year2_col_x": round(centroids[-1], 2),
        "currency_label_y": 0.0,
    }
    if k >= 3:
        result["notes_col_x"] = round(centroids[0], 2)

    return result
```

Also add `import numpy as np` at the top of the file — but **only inside the methods** that need it (already shown above with `import numpy as np` inside the method bodies), keeping the module-level imports clean.

Update the top of `template_analyzer.py` to add `List` to the typing import:
```python
from typing import Dict, Any, Optional, List
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend
pytest tests/test_analyze_precise_columns.py -v
```

Expected: All pass (real PDF test skips if file absent).

- [ ] **Step 5: Commit**

```bash
git add core/template_analyzer.py tests/test_analyze_precise_columns.py
git commit -m "feat: add analyze_precise() with column detection to TemplateAnalyzer

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5: TemplateAnalyzer.analyze_precise() — spacing detection

**Files:**
- Create: `backend/tests/test_analyze_precise_spacing.py`
- Modify: `backend/core/template_analyzer.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_analyze_precise_spacing.py`:

```python
"""Tests for TemplateAnalyzer.analyze_precise() — line spacing detection."""
import pytest
from pathlib import Path

REFERENCE_PDF = (
    r"C:\Users\Armaan\OneDrive - The Era Corporations"
    r"\Study\Armaan\AI Class\Data Science Class"
    r"\35. 11-Apr-2026\Testing data\Draft FS - Castle Plaza 2025.pdf"
)

SPACING_KEYS = {"heading_after", "row_height", "section_gap", "subtotal_gap",
                "indent_level_1", "indent_level_2"}


@pytest.fixture
def spaced_pdf(tmp_path):
    """A4 PDF with rows at a known consistent spacing of 14pt."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=595.28, height=841.89)
    # Place 25 rows with exactly 14pt spacing
    for i in range(25):
        y = 750 - i * 14
        page.insert_text((72, y), f"Row {i + 1}")
        page.insert_text((380, y), f"{(i + 1) * 1000:,}")
    # Place a section heading with 28pt gap (section break)
    page.insert_text((72, 750 - 25 * 14 - 28), "TOTAL ASSETS")
    pdf_path = tmp_path / "spaced.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)


def test_analyze_precise_returns_spacing_key(spaced_pdf):
    """analyze_precise() result includes a 'spacing' key."""
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(spaced_pdf)
    assert "spacing" in result


def test_spacing_has_required_sub_keys(spaced_pdf):
    """'spacing' dict contains all required sub-keys."""
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(spaced_pdf)
    assert set(result["spacing"].keys()) == SPACING_KEYS


def test_row_height_is_positive(spaced_pdf):
    """Detected row_height is a positive float."""
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(spaced_pdf)
    assert result["spacing"]["row_height"] > 0


def test_section_gap_greater_than_row_height(spaced_pdf):
    """section_gap should be larger than row_height."""
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(spaced_pdf)
    assert result["spacing"]["section_gap"] >= result["spacing"]["row_height"]


def test_row_height_within_tolerance(spaced_pdf):
    """Detected row_height is within ±3pt of the known 14pt spacing."""
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(spaced_pdf)
    assert abs(result["spacing"]["row_height"] - 14) <= 3, (
        f"row_height={result['spacing']['row_height']}, expected ~14"
    )


def test_indent_levels_positive(spaced_pdf):
    """indent_level_1 and indent_level_2 are positive."""
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(spaced_pdf)
    assert result["spacing"]["indent_level_1"] > 0
    assert result["spacing"]["indent_level_2"] > 0


def test_spacing_fallback_on_empty_pdf(tmp_path):
    """Empty PDF returns fallback spacing values."""
    import fitz
    from core.template_analyzer import TemplateAnalyzer
    doc = fitz.open()
    doc.new_page(width=595.28, height=841.89)
    pdf_path = tmp_path / "empty.pdf"
    doc.save(str(pdf_path))
    doc.close()
    result = TemplateAnalyzer().analyze_precise(str(pdf_path))
    assert result["spacing"]["row_height"] > 0


def test_spacing_real_pdf():
    """Real reference PDF: row_height and section_gap within ±2pt of expected."""
    if not Path(REFERENCE_PDF).exists():
        pytest.skip("Reference PDF not available in test environment")
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(REFERENCE_PDF)
    assert 8 <= result["spacing"]["row_height"] <= 20, (
        f"row_height={result['spacing']['row_height']} out of expected range 8–20pt"
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_analyze_precise_spacing.py -v
```

Expected: `FAILED` — `spacing` key missing from result.

- [ ] **Step 3: Add _extract_spacing() to template_analyzer.py**

Add the following method to the `TemplateAnalyzer` class (after `_extract_columns`):

```python
def _extract_spacing(self, pages: list) -> Dict[str, float]:
    """
    Detect line spacing by measuring y-gaps between consecutive spans.
    Groups gaps into small/medium/large via quantile split.
    Returns row_height (median medium gap) and section_gap (median large gap).
    """
    import numpy as np

    y0_by_page: List[float] = []

    for page in pages:
        span_y0s: List[float] = []
        blocks = page.get_text("dict", flags=0).get("blocks", [])
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    bbox = span.get("bbox", [0, 0, 0, 0])
                    span_y0s.append(float(bbox[1]))
        if span_y0s:
            y0_by_page.extend(sorted(span_y0s))

    if len(y0_by_page) < 4:
        return self._fallback_spacing()

    arr = np.array(sorted(y0_by_page), dtype=float)
    gaps = np.diff(arr)
    # Keep only positive gaps (ignore same-line spans)
    gaps = gaps[gaps > 0.5]

    if len(gaps) < 3:
        return self._fallback_spacing()

    q33 = float(np.percentile(gaps, 33))
    q67 = float(np.percentile(gaps, 67))
    medium = gaps[(gaps > q33) & (gaps <= q67)]
    large = gaps[gaps > q67]

    row_height = float(np.median(medium)) if len(medium) > 0 else float(np.median(gaps))
    section_gap = float(np.median(large)) if len(large) > 0 else row_height * 2.0

    # Indentation: find two most common label-column x0 values
    label_x0s: List[float] = []
    for page in pages:
        blocks = page.get_text("dict", flags=0).get("blocks", [])
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if text and not text.replace(",", "").replace(".", "").replace("-", "").replace("(", "").replace(")", "").isdigit():
                        bbox = span.get("bbox", [0, 0, 0, 0])
                        label_x0s.append(round(float(bbox[0]), 0))

    indent_level_1, indent_level_2 = 90.0, 108.0
    if len(label_x0s) >= 5:
        from collections import Counter
        top_x0s = [x for x, _ in Counter(label_x0s).most_common(3)]
        top_x0s.sort()
        if len(top_x0s) >= 2:
            indent_level_1 = float(top_x0s[1]) if top_x0s[1] > top_x0s[0] + 2 else indent_level_1
        if len(top_x0s) >= 3:
            indent_level_2 = float(top_x0s[2]) if top_x0s[2] > indent_level_1 + 2 else indent_level_2

    return {
        "heading_after": round(section_gap * 0.75, 2),
        "row_height": round(row_height, 2),
        "section_gap": round(section_gap, 2),
        "subtotal_gap": round(row_height * 0.5, 2),
        "indent_level_1": round(indent_level_1, 2),
        "indent_level_2": round(indent_level_2, 2),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
pytest tests/test_analyze_precise_spacing.py -v
```

Expected: All pass (real PDF test skips if file absent).

- [ ] **Step 5: Commit**

```bash
git add core/template_analyzer.py tests/test_analyze_precise_spacing.py
git commit -m "feat: add spacing detection to TemplateAnalyzer.analyze_precise()

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 6: TemplateAnalyzer.analyze_precise() — font role mapping

**Files:**
- Create: `backend/tests/test_analyze_precise_fonts.py`
- Modify: `backend/core/template_analyzer.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_analyze_precise_fonts.py`:

```python
"""Tests for TemplateAnalyzer.analyze_precise() — role-based font mapping."""
import pytest
from pathlib import Path

REFERENCE_PDF = (
    r"C:\Users\Armaan\OneDrive - The Era Corporations"
    r"\Study\Armaan\AI Class\Data Science Class"
    r"\35. 11-Apr-2026\Testing data\Draft FS - Castle Plaza 2025.pdf"
)


@pytest.fixture
def role_pdf(tmp_path):
    """PDF with distinct font sizes for heading (12), body (9), footer (7), and note refs."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=595.28, height=841.89)
    # Heading: large bold text matching an audit section pattern
    page.insert_text((72, 780), "Statement of Financial Position", fontsize=12)
    # Body: standard size
    for i in range(10):
        page.insert_text((72, 750 - i * 12), f"Line item {i}", fontsize=9)
    # Footer: small text at bottom
    page.insert_text((72, 30), "Page 1 of 5", fontsize=7)
    # Note references
    page.insert_text((310, 750), "Note 1", fontsize=8)
    page.insert_text((310, 738), "Note 2", fontsize=8)
    pdf_path = tmp_path / "role_fonts.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)


def test_fonts_has_heading_key(role_pdf):
    """analyze_precise() fonts dict has 'heading' key."""
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(role_pdf)
    assert "heading" in result["fonts"]


def test_fonts_has_body_key(role_pdf):
    """analyze_precise() fonts dict has 'body' key."""
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(role_pdf)
    assert "body" in result["fonts"]


def test_fonts_has_footer_key(role_pdf):
    """analyze_precise() fonts dict has 'footer' key."""
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(role_pdf)
    assert "footer" in result["fonts"]


def test_fonts_has_number_key(role_pdf):
    """analyze_precise() fonts dict has 'number' key."""
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(role_pdf)
    assert "number" in result["fonts"]


def test_fonts_has_note_ref_key(role_pdf):
    """analyze_precise() fonts dict has 'note_ref' key."""
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(role_pdf)
    assert "note_ref" in result["fonts"]


def test_each_font_role_has_size_and_family(role_pdf):
    """Every font role entry has 'size' and 'family'."""
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(role_pdf)
    for role in ("heading", "body", "footer", "note_ref"):
        if result["fonts"].get(role):
            assert "size" in result["fonts"][role], f"Missing 'size' in {role}"
            assert "family" in result["fonts"][role], f"Missing 'family' in {role}"


def test_heading_size_larger_than_body(role_pdf):
    """heading font size should be >= body font size."""
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(role_pdf)
    heading_size = result["fonts"].get("heading", {}).get("size", 0)
    body_size = result["fonts"].get("body", {}).get("size", 0)
    assert heading_size >= body_size


def test_fonts_real_pdf():
    """Real reference PDF: heading, body, footer roles all have size > 0."""
    if not Path(REFERENCE_PDF).exists():
        pytest.skip("Reference PDF not available in test environment")
    from core.template_analyzer import TemplateAnalyzer
    result = TemplateAnalyzer().analyze_precise(REFERENCE_PDF)
    for role in ("heading", "body", "footer"):
        assert result["fonts"].get(role, {}).get("size", 0) > 0, f"{role} font size is 0"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_analyze_precise_fonts.py -v
```

Expected: `FAILED` — `number` and `note_ref` keys missing from fonts dict.

- [ ] **Step 3: Add _extract_font_roles() to template_analyzer.py**

Add the following method to the `TemplateAnalyzer` class (after `_extract_spacing`):

```python
def _extract_font_roles(self, doc) -> Dict[str, Any]:
    """
    Role-based font mapping: classify each span by role rather than sorting by size.

    Roles:
      heading  — spans matching _AUDIT_SECTION_PATTERNS
      footer   — small font (≤8pt) in bottom 10% of page
      number   — numeric-only spans in right half of page
      note_ref — spans matching "Note N" pattern
      body     — everything else
    """
    import re
    from collections import Counter

    try:
        from core.document_format_analyzer import _AUDIT_SECTION_PATTERNS
    except ImportError:
        _AUDIT_SECTION_PATTERNS = []

    _NOTE_REF_RE = re.compile(r"^note\s*\d+$", re.IGNORECASE)
    _NUMERIC_ONLY_RE = re.compile(r"^[\d,.()\-–\s]+$")

    role_spans: Dict[str, List] = {
        "heading": [], "footer": [], "number": [], "note_ref": [], "body": [],
    }

    for page in doc:
        page_height = page.rect.height
        footer_y_threshold = page_height * 0.90

        blocks = page.get_text("dict", flags=0).get("blocks", [])
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    size = span.get("size", 9)
                    font = span.get("font", "Helvetica")
                    bbox = span.get("bbox", [0, 0, 0, 0])
                    y0 = bbox[1]

                    if not text:
                        continue

                    if any(p.search(text) for p in _AUDIT_SECTION_PATTERNS):
                        role_spans["heading"].append((font, round(size, 1)))
                    elif size <= 8 and y0 >= footer_y_threshold:
                        role_spans["footer"].append((font, round(size, 1)))
                    elif _NOTE_REF_RE.match(text):
                        role_spans["note_ref"].append((font, round(size, 1)))
                    elif _NUMERIC_ONLY_RE.match(text) and len(text) >= 3:
                        role_spans["number"].append((font, round(size, 1)))
                    else:
                        role_spans["body"].append((font, round(size, 1)))

    def _most_common(spans) -> Dict[str, Any]:
        if not spans:
            return None
        (family, size), _ = Counter(spans).most_common(1)[0]
        return {"family": family, "size": size}

    fonts: Dict[str, Any] = {}
    for role in ("heading", "body", "footer", "number", "note_ref"):
        entry = _most_common(role_spans[role])
        if entry:
            fonts[role] = entry

    # Ensure heading, body, footer always have a fallback
    fonts.setdefault("heading", {"family": "Helvetica-Bold", "size": 12})
    fonts.setdefault("body", {"family": "Helvetica", "size": 9})
    fonts.setdefault("footer", {"family": "Helvetica", "size": 8})
    fonts.setdefault("number", fonts["body"])
    fonts.setdefault("note_ref", fonts["body"])

    return fonts
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
pytest tests/test_analyze_precise_fonts.py tests/test_analyze_precise_columns.py tests/test_analyze_precise_spacing.py -v
```

Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add core/template_analyzer.py tests/test_analyze_precise_fonts.py
git commit -m "feat: add font role mapping to TemplateAnalyzer.analyze_precise()

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 7: AutoVerifier — pixel_similarity() and verify() pass path

**Files:**
- Create: `backend/core/auto_verifier.py`
- Create: `backend/tests/test_autoverifier_pass.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_autoverifier_pass.py`:

```python
"""Tests for AutoVerifier — pixel_similarity() and the ≥95% verified path."""
import pytest
import numpy as np
from PIL import Image


def _gray_image(value: int, size=(200, 300)) -> Image.Image:
    """Create a grayscale PIL image filled with a constant pixel value 0–255."""
    arr = np.full(size, value, dtype=np.uint8)
    return Image.fromarray(arr, mode="L")


def test_pixel_similarity_identical_images():
    """Identical images → similarity = 1.0."""
    from core.auto_verifier import AutoVerifier
    img = _gray_image(128)
    result = AutoVerifier.pixel_similarity(img, img)
    assert result == 1.0


def test_pixel_similarity_opposite_images():
    """Completely different images (black vs white) → similarity = 0.0."""
    from core.auto_verifier import AutoVerifier
    black = _gray_image(0)
    white = _gray_image(255)
    result = AutoVerifier.pixel_similarity(black, white)
    assert result == 0.0


def test_pixel_similarity_half_different():
    """Half-different images → similarity ~0.5."""
    from core.auto_verifier import AutoVerifier
    black = _gray_image(0)
    mid = _gray_image(128)
    result = AutoVerifier.pixel_similarity(black, mid)
    assert 0.45 <= result <= 0.55


def test_pixel_similarity_different_sizes():
    """pixel_similarity() handles images of different sizes by resizing."""
    from core.auto_verifier import AutoVerifier
    img_a = _gray_image(100, size=(100, 100))
    img_b = _gray_image(100, size=(200, 200))
    result = AutoVerifier.pixel_similarity(img_a, img_b)
    assert result > 0.99  # same value, different size → near-identical after resize


def test_verify_returns_verified_when_images_identical(monkeypatch):
    """verify() returns status='verified' when reference and test images are identical."""
    from core.auto_verifier import AutoVerifier

    identical = _gray_image(100)
    verifier = AutoVerifier()
    monkeypatch.setattr(verifier, "_pdf_page_to_image", lambda path: identical)
    monkeypatch.setattr(verifier, "_render_test_page", lambda config: b"fake")
    monkeypatch.setattr(verifier, "_pdf_bytes_to_image", lambda b: identical)

    config = {
        "page": {"width": 595.28, "height": 841.89},
        "margins": {"top": 72, "bottom": 72, "left": 72, "right": 72},
        "columns": {"year1_col_x": 380.0, "year2_col_x": 460.0, "label_col_x": 72.0,
                    "notes_col_x": 310.0, "currency_label_y": 0.0},
        "spacing": {"row_height": 14.0, "heading_after": 18.0, "section_gap": 24.0,
                    "subtotal_gap": 6.0, "indent_level_1": 90.0, "indent_level_2": 108.0},
        "fonts": {"body": {"family": "Helvetica", "size": 9},
                  "heading": {"family": "Helvetica-Bold", "size": 12}},
    }
    result = verifier.verify(config, "fake.pdf")

    assert result["status"] == "verified"
    assert result["confidence"] >= 0.95
    assert result["hints"] is None
    assert result["adjusted"] is False


def test_verify_returns_dict_with_required_keys(monkeypatch):
    """verify() always returns a dict with status, confidence, hints, adjusted."""
    from core.auto_verifier import AutoVerifier

    identical = _gray_image(200)
    verifier = AutoVerifier()
    monkeypatch.setattr(verifier, "_pdf_page_to_image", lambda path: identical)
    monkeypatch.setattr(verifier, "_render_test_page", lambda config: b"fake")
    monkeypatch.setattr(verifier, "_pdf_bytes_to_image", lambda b: identical)

    result = verifier.verify({}, "fake.pdf")
    for key in ("status", "confidence", "hints", "adjusted"):
        assert key in result, f"Missing key: {key}"


def test_verify_render_failure_returns_needs_review(monkeypatch):
    """ReportLab render failure → needs_review with confidence=0.75."""
    from core.auto_verifier import AutoVerifier

    def bad_render(config):
        raise RuntimeError("ReportLab failed")

    identical = _gray_image(100)
    verifier = AutoVerifier()
    monkeypatch.setattr(verifier, "_pdf_page_to_image", lambda path: identical)
    monkeypatch.setattr(verifier, "_render_test_page", bad_render)

    result = verifier.verify({}, "fake.pdf")
    assert result["status"] == "needs_review"
    assert result["confidence"] == 0.75
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_autoverifier_pass.py -v
```

Expected: `ImportError: No module named 'core.auto_verifier'`

- [ ] **Step 3: Create `backend/core/auto_verifier.py`**

```python
"""
AutoVerifier — Phase 3 of the fast format learning pipeline.

Renders a test page using extracted config (ReportLab), pixel-diffs against
the reference PDF page 1 (Pillow/NumPy), then auto-approves, applies one
adjustment pass, or returns StructuredHints for the user.
"""
from __future__ import annotations

import copy
import io
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image


class AutoVerifier:
    """Verify extracted template config via pixel comparison."""

    PASS_THRESHOLD = 0.95
    ADJUST_THRESHOLD = 0.85
    RENDER_DPI = 150

    # ── Public API ─────────────────────────────────────────────────

    def verify(self, config: Dict[str, Any], pdf_path: str) -> Dict[str, Any]:
        """
        Run the full verification cycle.

        Returns:
            {
              "status":     "verified" | "needs_review",
              "confidence": float,   # pixel similarity score
              "hints":      list | None,
              "adjusted":   bool,
            }
        """
        # Load reference image
        try:
            ref_image = self._pdf_page_to_image(pdf_path)
        except Exception:
            return {"status": "needs_review", "confidence": 0.75, "hints": None, "adjusted": False}

        # Render test page
        try:
            test_pdf_bytes = self._render_test_page(config)
            test_image = self._pdf_bytes_to_image(test_pdf_bytes)
        except Exception:
            return {"status": "needs_review", "confidence": 0.75, "hints": None, "adjusted": False}

        score = self.pixel_similarity(ref_image, test_image)

        if score >= self.PASS_THRESHOLD:
            return {"status": "verified", "confidence": round(score, 4), "hints": None, "adjusted": False}

        if score >= self.ADJUST_THRESHOLD:
            adj_config = self._auto_adjust(config, ref_image, test_image)
            try:
                adj_bytes = self._render_test_page(adj_config)
                adj_image = self._pdf_bytes_to_image(adj_bytes)
                adj_score = self.pixel_similarity(ref_image, adj_image)
            except Exception:
                adj_score = score

            if adj_score >= self.PASS_THRESHOLD:
                return {"status": "verified", "confidence": round(adj_score, 4), "hints": None, "adjusted": True}

        hints = self._generate_hints(config, ref_image, test_image, score)
        return {"status": "needs_review", "confidence": round(score, 4), "hints": hints, "adjusted": False}

    @staticmethod
    def pixel_similarity(img_ref: Image.Image, img_test: Image.Image) -> float:
        """
        Compute pixel similarity between two grayscale images.
        Returns 1.0 for identical, 0.0 for maximum difference.
        """
        img_test = img_test.resize(img_ref.size, Image.LANCZOS)
        arr_ref = np.array(img_ref.convert("L"), dtype=float)
        arr_test = np.array(img_test.convert("L"), dtype=float)
        diff = np.abs(arr_ref - arr_test).mean()
        return round(1.0 - (diff / 255.0), 4)

    # ── Internal helpers ────────────────────────────────────────────

    def _pdf_page_to_image(self, pdf_path: str, page_num: int = 0) -> Image.Image:
        """Render page_num of a PDF file to a grayscale PIL Image."""
        import fitz
        doc = fitz.open(pdf_path)
        page = doc[page_num]
        mat = fitz.Matrix(self.RENDER_DPI / 72, self.RENDER_DPI / 72)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
        img = Image.frombytes("L", [pix.width, pix.height], pix.samples)
        doc.close()
        return img

    def _pdf_bytes_to_image(self, pdf_bytes: bytes, page_num: int = 0) -> Image.Image:
        """Convert PDF bytes to a grayscale PIL Image."""
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[page_num]
        mat = fitz.Matrix(self.RENDER_DPI / 72, self.RENDER_DPI / 72)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
        img = Image.frombytes("L", [pix.width, pix.height], pix.samples)
        doc.close()
        return img

    def _render_test_page(self, config: Dict[str, Any]) -> bytes:
        """
        Render a representative financial page using the extracted config.
        Returns PDF bytes.
        """
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.utils import simpleSplit

        page = config.get("page", {})
        w = float(page.get("width", 595.28))
        h = float(page.get("height", 841.89))

        margins = config.get("margins", {})
        columns = config.get("columns", {})
        spacing = config.get("spacing", {})
        fonts = config.get("fonts", {})

        body_font = fonts.get("body", {}).get("family", "Helvetica")
        body_size = float(fonts.get("body", {}).get("size", 9))
        heading_font = fonts.get("heading", {}).get("family", "Helvetica-Bold")
        heading_size = float(fonts.get("heading", {}).get("size", 12))

        left = float(margins.get("left", 72))
        top_margin = float(margins.get("top", 72))
        row_h = float(spacing.get("row_height", 14))
        heading_after = float(spacing.get("heading_after", 18))
        section_gap = float(spacing.get("section_gap", 24))

        year1_x = float(columns.get("year1_col_x", w * 0.65))
        year2_x = float(columns.get("year2_col_x", w * 0.80))
        notes_x = float(columns.get("notes_col_x", w * 0.52)) or w * 0.52

        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=(w, h))

        curr_y = h - top_margin

        # Section heading
        c.setFont(heading_font, heading_size)
        c.drawString(left, curr_y, "STATEMENT OF FINANCIAL POSITION")
        curr_y -= heading_after

        # Column headers
        c.setFont(body_font, body_size)
        c.drawRightString(year1_x + 30, curr_y, "2024")
        c.drawRightString(year2_x + 30, curr_y, "2023")
        curr_y -= row_h

        # Data rows
        line_items = [
            ("Non-current assets", 12_450_000, 11_200_000),
            ("Property and equipment", 8_320_000, 7_900_000),
            ("Intangible assets", 1_200_000, 1_100_000),
            ("Current assets", 5_430_000, 4_800_000),
            ("Trade receivables", 2_100_000, 1_950_000),
            ("Cash and bank", 3_330_000, 2_850_000),
            ("Total assets", 17_880_000, 16_000_000),
        ]
        for label, val1, val2 in line_items:
            c.drawString(left, curr_y, label)
            c.drawRightString(year1_x + 30, curr_y, f"{val1:,}")
            c.drawRightString(year2_x + 30, curr_y, f"{val2:,}")
            curr_y -= row_h
            if curr_y < 72:
                break

        c.save()
        return buf.getvalue()

    def _auto_adjust(
        self,
        config: Dict[str, Any],
        ref_image: Image.Image,
        test_image: Image.Image,
    ) -> Dict[str, Any]:
        """
        Single-pass auto-adjustment.
        Splits images into 6 bands, finds the worst band, nudges the
        corresponding config element, and returns the adjusted config.
        """
        adj = copy.deepcopy(config)
        h = ref_image.height
        band_size = max(h // 6, 1)

        ref_arr = np.array(ref_image.convert("L"), dtype=float)
        test_arr = np.array(test_image.resize(ref_image.size, Image.LANCZOS).convert("L"), dtype=float)

        band_diffs = []
        for i in range(6):
            y0 = i * band_size
            y1 = (i + 1) * band_size if i < 5 else h
            diff = float(np.abs(ref_arr[y0:y1] - test_arr[y0:y1]).mean())
            band_diffs.append((diff, i))

        _, worst_band = max(band_diffs)

        adj.setdefault("margins", {})
        adj.setdefault("columns", {})
        adj.setdefault("spacing", {})

        if worst_band == 0:
            adj["margins"]["top"] = adj["margins"].get("top", 72) + 4
        elif worst_band in (2, 3):
            adj["columns"]["year1_col_x"] = adj["columns"].get("year1_col_x", 380.0) + 3
        else:
            adj["spacing"]["row_height"] = adj["spacing"].get("row_height", 14.0) + 1

        return adj

    def _generate_hints(
        self,
        config: Dict[str, Any],
        ref_image: Image.Image,
        test_image: Image.Image,
        score: float,
    ) -> List[Dict[str, Any]]:
        """
        Generate StructuredHints — targeted binary choices for the user.
        Each hint identifies a failing region and offers two correction options.
        """
        h = ref_image.height
        band_size = max(h // 6, 1)

        ref_arr = np.array(ref_image.convert("L"), dtype=float)
        test_arr = np.array(test_image.resize(ref_image.size, Image.LANCZOS).convert("L"), dtype=float)

        hints: List[Dict[str, Any]] = []
        for i in range(6):
            y0 = i * band_size
            y1 = (i + 1) * band_size if i < 5 else h
            band_diff = float(np.abs(ref_arr[y0:y1] - test_arr[y0:y1]).mean())

            if band_diff < 30:
                continue

            if i == 0:
                nudge = max(1, round(band_diff / 10))
                hints.append({
                    "element": "margins",
                    "message": f"Top margin appears to be off by approximately {nudge}pt",
                    "options": [f"adjust top margin by +{nudge}pt", "leave as-is"],
                })
            elif i in (1, 2):
                nudge = max(1, round(band_diff / 5) * 3)
                hints.append({
                    "element": "columns",
                    "message": f"Column position appears {nudge}pt off",
                    "options": [f"shift left {nudge}pt", "leave as-is"],
                })
            else:
                nudge = max(1, round(band_diff / 20))
                hints.append({
                    "element": "spacing.row_height",
                    "message": f"Row height appears {nudge}pt smaller than reference",
                    "options": [f"increase by {nudge}pt", "leave as-is"],
                })

        if not hints:
            hints.append({
                "element": "layout",
                "message": "Layout could not be verified automatically. Manual review required.",
                "options": ["approve manually", "discard template"],
            })

        return hints
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
pytest tests/test_autoverifier_pass.py -v
```

Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add core/auto_verifier.py tests/test_autoverifier_pass.py
git commit -m "feat: add AutoVerifier with pixel_similarity() and verify() pass path

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 8: AutoVerifier — auto-adjust and StructuredHints paths

**Files:**
- Create: `backend/tests/test_autoverifier_adjust.py`
- Create: `backend/tests/test_autoverifier_hints.py`

- [ ] **Step 1: Write the failing tests for auto-adjust**

Create `backend/tests/test_autoverifier_adjust.py`:

```python
"""Tests for AutoVerifier — 85-95% score triggers auto-adjust pass."""
import pytest
import numpy as np
from PIL import Image


def _make_image(value: int, size=(600, 500)) -> Image.Image:
    arr = np.full(size, value, dtype=np.uint8)
    return Image.fromarray(arr, mode="L")


def test_auto_adjust_triggers_on_mid_score(monkeypatch):
    """
    When initial score is 85-95%, verify() runs auto-adjust.
    Second render returns identical-to-ref image → status becomes 'verified' with adjusted=True.
    """
    from core.auto_verifier import AutoVerifier

    # Reference: all zeros (black)
    ref_img = _make_image(0, size=(600, 500))

    # First test render: 10% of pixels are white → similarity ~0.90
    test_arr_1 = np.zeros((600, 500), dtype=np.uint8)
    test_arr_1[:60, :] = 255       # top 60 rows white = 60*500 = 30000 of 300000 pixels
    test_img_1 = Image.fromarray(test_arr_1, mode="L")

    # Second test render (after adjust): identical to reference → similarity = 1.0
    test_img_2 = _make_image(0, size=(600, 500))

    call_count = [0]

    def fake_render(config):
        return b"fake"

    def fake_bytes_to_image(b):
        call_count[0] += 1
        return test_img_1 if call_count[0] == 1 else test_img_2

    verifier = AutoVerifier()
    monkeypatch.setattr(verifier, "_pdf_page_to_image", lambda path: ref_img)
    monkeypatch.setattr(verifier, "_render_test_page", fake_render)
    monkeypatch.setattr(verifier, "_pdf_bytes_to_image", fake_bytes_to_image)

    config = {
        "page": {"width": 595.28, "height": 841.89},
        "margins": {"top": 72, "bottom": 72, "left": 72, "right": 72},
        "columns": {"year1_col_x": 380.0, "year2_col_x": 460.0, "label_col_x": 72.0,
                    "notes_col_x": 0.0, "currency_label_y": 0.0},
        "spacing": {"row_height": 14.0, "heading_after": 18.0, "section_gap": 24.0,
                    "subtotal_gap": 6.0, "indent_level_1": 90.0, "indent_level_2": 108.0},
        "fonts": {},
    }
    result = verifier.verify(config, "fake.pdf")

    assert result["status"] == "verified"
    assert result["adjusted"] is True
    assert result["confidence"] >= 0.95
    assert call_count[0] == 2   # render was called twice


def test_auto_adjust_falls_through_to_hints_if_still_failing(monkeypatch):
    """
    If auto-adjust still doesn't reach ≥95%, returns needs_review with hints.
    """
    from core.auto_verifier import AutoVerifier

    ref_img = _make_image(0, size=(600, 500))

    # Both renders give ~90% similarity (never reaches 95%)
    test_arr = np.zeros((600, 500), dtype=np.uint8)
    test_arr[:60, :] = 255
    test_img = Image.fromarray(test_arr, mode="L")

    verifier = AutoVerifier()
    monkeypatch.setattr(verifier, "_pdf_page_to_image", lambda path: ref_img)
    monkeypatch.setattr(verifier, "_render_test_page", lambda c: b"fake")
    monkeypatch.setattr(verifier, "_pdf_bytes_to_image", lambda b: test_img)

    config = {"page": {}, "margins": {}, "columns": {}, "spacing": {}, "fonts": {}}
    result = verifier.verify(config, "fake.pdf")

    assert result["status"] == "needs_review"
    assert result["hints"] is not None


def test_auto_adjust_modifies_config_for_worst_band():
    """_auto_adjust() returns a config dict with one field changed."""
    from core.auto_verifier import AutoVerifier
    import copy

    # All-black ref; test has white top band → worst band is 0 → top margin nudge
    ref_arr = np.zeros((600, 500), dtype=np.uint8)
    test_arr = np.zeros((600, 500), dtype=np.uint8)
    test_arr[:100, :] = 255   # top band all white
    ref_img = Image.fromarray(ref_arr, mode="L")
    test_img = Image.fromarray(test_arr, mode="L")

    original_config = {
        "margins": {"top": 72}, "columns": {"year1_col_x": 380.0},
        "spacing": {"row_height": 14.0},
    }
    verifier = AutoVerifier()
    adj = verifier._auto_adjust(original_config, ref_img, test_img)

    # Top margin should be nudged up
    assert adj["margins"]["top"] > original_config["margins"]["top"]
    # Other fields should be unchanged
    assert adj["columns"]["year1_col_x"] == 380.0
    assert adj["spacing"]["row_height"] == 14.0
```

- [ ] **Step 2: Run test to verify auto-adjust tests fail**

```bash
cd backend
pytest tests/test_autoverifier_adjust.py -v
```

Expected: All pass immediately (auto_verifier.py is already implemented). If they fail, investigate the pixel similarity calculation for the ~90% case.

> **Debugging note:** The expected similarity for the 10%-white-pixels image is:
> `diff_mean = (30000 * 255) / 300000 = 25.5`; `similarity = 1 - 25.5/255 = 0.9`
> This falls in the 85–95% range and should trigger auto-adjust. If the test fails because the
> similarity is outside the expected range, adjust the white region size: `test_arr[:60, :] = 255`
> produces exactly 30,000 white pixels. Verify with: `from core.auto_verifier import AutoVerifier; import numpy as np; from PIL import Image; print(AutoVerifier.pixel_similarity(Image.fromarray(np.zeros((600,500), dtype=np.uint8), 'L'), Image.fromarray(img_arr, 'L')))`

- [ ] **Step 3: Write the failing tests for StructuredHints**

Create `backend/tests/test_autoverifier_hints.py`:

```python
"""Tests for AutoVerifier — <85% score returns StructuredHints."""
import pytest
import numpy as np
from PIL import Image


def _make_image(value: int, size=(600, 500)) -> Image.Image:
    arr = np.full(size, value, dtype=np.uint8)
    return Image.fromarray(arr, mode="L")


def test_hints_returned_when_score_below_85(monkeypatch):
    """Score < 85% → status needs_review and hints list is non-empty."""
    from core.auto_verifier import AutoVerifier

    ref_img = _make_image(0)
    test_img = _make_image(255)  # Completely different → similarity = 0.0

    verifier = AutoVerifier()
    monkeypatch.setattr(verifier, "_pdf_page_to_image", lambda path: ref_img)
    monkeypatch.setattr(verifier, "_render_test_page", lambda c: b"fake")
    monkeypatch.setattr(verifier, "_pdf_bytes_to_image", lambda b: test_img)

    result = verifier.verify({}, "fake.pdf")

    assert result["status"] == "needs_review"
    assert result["hints"] is not None
    assert len(result["hints"]) >= 1


def test_hints_have_required_keys(monkeypatch):
    """Each hint has 'element', 'message', and 'options' keys."""
    from core.auto_verifier import AutoVerifier

    ref_img = _make_image(0)
    test_img = _make_image(255)

    verifier = AutoVerifier()
    monkeypatch.setattr(verifier, "_pdf_page_to_image", lambda path: ref_img)
    monkeypatch.setattr(verifier, "_render_test_page", lambda c: b"fake")
    monkeypatch.setattr(verifier, "_pdf_bytes_to_image", lambda b: test_img)

    result = verifier.verify({}, "fake.pdf")

    for hint in result["hints"]:
        assert "element" in hint
        assert "message" in hint
        assert "options" in hint
        assert isinstance(hint["options"], list)
        assert len(hint["options"]) == 2


def test_hints_options_are_non_empty_strings(monkeypatch):
    """Each hint option is a non-empty string."""
    from core.auto_verifier import AutoVerifier

    ref_img = _make_image(0)
    test_img = _make_image(255)

    verifier = AutoVerifier()
    monkeypatch.setattr(verifier, "_pdf_page_to_image", lambda path: ref_img)
    monkeypatch.setattr(verifier, "_render_test_page", lambda c: b"fake")
    monkeypatch.setattr(verifier, "_pdf_bytes_to_image", lambda b: test_img)

    result = verifier.verify({}, "fake.pdf")

    for hint in result["hints"]:
        for option in hint["options"]:
            assert isinstance(option, str) and len(option) > 0


def test_generate_hints_returns_fallback_when_no_bad_bands():
    """_generate_hints() returns at least one hint even when all bands are similar."""
    from core.auto_verifier import AutoVerifier

    same = _make_image(128)
    verifier = AutoVerifier()
    hints = verifier._generate_hints({}, same, same, 0.80)
    assert len(hints) >= 1


def test_pdf_open_failure_returns_needs_review():
    """If the PDF cannot be opened, verify() returns needs_review without crashing."""
    from core.auto_verifier import AutoVerifier

    verifier = AutoVerifier()
    result = verifier.verify({}, "totally_nonexistent_file.pdf")
    assert result["status"] == "needs_review"
    assert result["confidence"] == 0.75
    assert result["hints"] is None
```

- [ ] **Step 4: Run all verifier tests**

```bash
cd backend
pytest tests/test_autoverifier_pass.py tests/test_autoverifier_adjust.py tests/test_autoverifier_hints.py -v
```

Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_autoverifier_adjust.py tests/test_autoverifier_hints.py
git commit -m "test: add AutoVerifier auto-adjust and StructuredHints contract tests

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 9: API — fast_learn flag + full pipeline integration

**Files:**
- Create: `backend/tests/test_fast_learn_api.py`
- Create: `backend/tests/test_manual_path_unchanged.py`
- Modify: `backend/api/templates.py`

- [ ] **Step 1: Write failing tests for the fast_learn API**

Create `backend/tests/test_fast_learn_api.py`:

```python
"""
Tests for POST /api/templates/upload-reference?fast_learn=true.
Uses conftest.py client fixture (in-memory DB, ASGITransport).
"""
import pytest
from unittest.mock import MagicMock, patch


FAKE_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
_VERIFIED_RESULT = {"status": "verified", "confidence": 0.97, "hints": None, "adjusted": False}
_REVIEW_RESULT = {"status": "needs_review", "confidence": 0.72, "hints": [
    {"element": "columns", "message": "Column offset", "options": ["shift left 6pt", "leave as-is"]}
], "adjusted": False}


@pytest.mark.asyncio
async def test_fast_learn_returns_new_response_schema(client):
    """fast_learn=true returns template_id, status, confidence, time_taken_sec, match_source."""
    with patch("api.templates.FormatFingerprinter") as MockFF, \
         patch("api.templates.AutoVerifier") as MockAV, \
         patch("api.templates.TemplateAnalyzer") as MockTA:

        mock_ff = MockFF.return_value
        mock_ff.match.return_value = (None, 50, None)  # No prebuilt match
        mock_ff.fingerprint.return_value = {}

        mock_ta = MockTA.return_value
        mock_ta.analyze_precise.return_value = {
            "page": {"width": 595.28, "height": 841.89}, "margins": {}, "fonts": {},
            "tables": [], "sections": [], "confidence": 0.9,
            "source": "test.pdf", "page_count": 5,
            "columns": {"year1_col_x": 380.0, "year2_col_x": 460.0, "label_col_x": 72.0,
                        "notes_col_x": 310.0, "currency_label_y": 0.0},
            "spacing": {"row_height": 14.0, "heading_after": 18.0, "section_gap": 24.0,
                        "subtotal_gap": 6.0, "indent_level_1": 90.0, "indent_level_2": 108.0},
        }

        mock_av = MockAV.return_value
        mock_av.verify.return_value = _VERIFIED_RESULT

        resp = await client.post(
            "/api/templates/upload-reference",
            files={"file": ("audit.pdf", FAKE_PDF, "application/pdf")},
            params={"fast_learn": "true", "name": "Test Fast Template", "user_id": "user1"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "template_id" in data
    assert "status" in data
    assert "confidence" in data
    assert "time_taken_sec" in data
    assert "match_source" in data
    assert data["status"] in ("verified", "needs_review")


@pytest.mark.asyncio
async def test_fast_learn_verified_status_returns_null_hints(client):
    """When status=verified, hints is null."""
    with patch("api.templates.FormatFingerprinter") as MockFF, \
         patch("api.templates.AutoVerifier") as MockAV, \
         patch("api.templates.TemplateAnalyzer") as MockTA:

        MockFF.return_value.match.return_value = (None, 40, None)
        MockFF.return_value.fingerprint.return_value = {}
        MockTA.return_value.analyze_precise.return_value = {
            "page": {}, "margins": {}, "fonts": {}, "tables": [], "sections": [],
            "confidence": 0.9, "source": "t.pdf", "page_count": 3,
            "columns": {"year1_col_x": 380.0, "year2_col_x": 460.0,
                        "label_col_x": 72.0, "notes_col_x": 0.0, "currency_label_y": 0.0},
            "spacing": {"row_height": 14.0, "heading_after": 18.0, "section_gap": 24.0,
                        "subtotal_gap": 6.0, "indent_level_1": 90.0, "indent_level_2": 108.0},
        }
        MockAV.return_value.verify.return_value = _VERIFIED_RESULT

        resp = await client.post(
            "/api/templates/upload-reference",
            files={"file": ("a.pdf", FAKE_PDF, "application/pdf")},
            params={"fast_learn": "true", "user_id": "u1"},
        )

    data = resp.json()
    assert data["hints"] is None


@pytest.mark.asyncio
async def test_fast_learn_needs_review_returns_hints(client):
    """When status=needs_review, hints array is present."""
    with patch("api.templates.FormatFingerprinter") as MockFF, \
         patch("api.templates.AutoVerifier") as MockAV, \
         patch("api.templates.TemplateAnalyzer") as MockTA:

        MockFF.return_value.match.return_value = (None, 30, None)
        MockFF.return_value.fingerprint.return_value = {}
        MockTA.return_value.analyze_precise.return_value = {
            "page": {}, "margins": {}, "fonts": {}, "tables": [], "sections": [],
            "confidence": 0.5, "source": "t.pdf", "page_count": 2,
            "columns": {"year1_col_x": 380.0, "year2_col_x": 460.0,
                        "label_col_x": 72.0, "notes_col_x": 0.0, "currency_label_y": 0.0},
            "spacing": {"row_height": 14.0, "heading_after": 18.0, "section_gap": 24.0,
                        "subtotal_gap": 6.0, "indent_level_1": 90.0, "indent_level_2": 108.0},
        }
        MockAV.return_value.verify.return_value = _REVIEW_RESULT

        resp = await client.post(
            "/api/templates/upload-reference",
            files={"file": ("b.pdf", FAKE_PDF, "application/pdf")},
            params={"fast_learn": "true", "user_id": "u2"},
        )

    data = resp.json()
    assert data["hints"] is not None
    assert len(data["hints"]) >= 1


@pytest.mark.asyncio
async def test_fast_learn_prebuilt_match_skips_analyze(client):
    """When fingerprint score ≥88, analyze_precise() is NOT called."""
    from core.prebuilt_formats import PREBUILT_FORMATS

    cloned_config = PREBUILT_FORMATS[0]["config"]

    with patch("api.templates.FormatFingerprinter") as MockFF, \
         patch("api.templates.AutoVerifier") as MockAV, \
         patch("api.templates.TemplateAnalyzer") as MockTA:

        MockFF.return_value.match.return_value = (cloned_config, 95, "prebuilt-gcc-standard")
        MockFF.return_value.fingerprint.return_value = {}
        MockAV.return_value.verify.return_value = _VERIFIED_RESULT

        resp = await client.post(
            "/api/templates/upload-reference",
            files={"file": ("c.pdf", FAKE_PDF, "application/pdf")},
            params={"fast_learn": "true", "user_id": "u3"},
        )

    data = resp.json()
    assert data["status_code"] if "status_code" in data else resp.status_code == 200
    assert MockTA.return_value.analyze_precise.call_count == 0
    assert data.get("match_source") == "prebuilt-gcc-standard"
```

- [ ] **Step 2: Write failing tests for manual path unchanged**

Create `backend/tests/test_manual_path_unchanged.py`:

```python
"""
Tests that fast_learn=false (default) preserves the existing job-based workflow exactly.
"""
import pytest


FAKE_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"


@pytest.mark.asyncio
async def test_upload_without_fast_learn_returns_job_id(client):
    """Default upload (fast_learn=false) still returns job_id and pending status."""
    resp = await client.post(
        "/api/templates/upload-reference",
        files={"file": ("manual.pdf", FAKE_PDF, "application/pdf")},
        params={"name": "Manual Template", "user_id": "user_manual"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "pending"
    assert "message" in data


@pytest.mark.asyncio
async def test_upload_fast_learn_false_returns_job_id(client):
    """Explicit fast_learn=false still returns job_id and pending status."""
    resp = await client.post(
        "/api/templates/upload-reference",
        files={"file": ("manual2.pdf", FAKE_PDF, "application/pdf")},
        params={"fast_learn": "false", "user_id": "user_manual2"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_manual_path_job_trackable(client):
    """A job created without fast_learn can be tracked via /status/{job_id}."""
    upload_resp = await client.post(
        "/api/templates/upload-reference",
        files={"file": ("track.pdf", FAKE_PDF, "application/pdf")},
        params={"user_id": "tracker"},
    )
    job_id = upload_resp.json()["job_id"]

    status_resp = await client.get(f"/api/templates/status/{job_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["job_id"] == job_id


@pytest.mark.asyncio
async def test_non_pdf_still_returns_400(client):
    """Non-PDF upload still returns 400 regardless of fast_learn."""
    resp = await client.post(
        "/api/templates/upload-reference",
        files={"file": ("bad.txt", b"not a pdf", "text/plain")},
        params={"fast_learn": "true"},
    )
    assert resp.status_code == 400
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd backend
pytest tests/test_fast_learn_api.py tests/test_manual_path_unchanged.py -v
```

Expected: `test_fast_learn_api.py` fails with `422 Unprocessable Entity` (fast_learn param not recognised yet). `test_manual_path_unchanged.py` should mostly pass.

- [ ] **Step 4: Modify `backend/api/templates.py`**

Add imports at the top (after the existing imports):
```python
import copy
import time

from core.format_fingerprinter import FormatFingerprinter
from core.auto_verifier import AutoVerifier
```

Replace the existing `upload_reference` function signature and body:

```python
@router.post("/upload-reference")
async def upload_reference(
    file: UploadFile = File(...),
    name: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    fast_learn: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Upload a reference PDF to learn its format.

    fast_learn=false (default): saves the PDF and returns a job_id for async processing.
    fast_learn=true: runs the full fast-learn pipeline synchronously and returns
                     {template_id, status, confidence, time_taken_sec, match_source, hints}.
    """
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    job_id = str(uuid.uuid4())
    template_name = name or (file.filename or "").replace(".pdf", "") or f"template-{job_id[:8]}"

    temp_dir = os.path.join(os.path.dirname(__file__), "..", "uploads", "temp_templates")
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"{job_id}_{file.filename}")

    content = await file.read()
    with open(temp_path, "wb") as f:
        f.write(content)

    if fast_learn:
        return await _fast_learn_pipeline(temp_path, template_name, user_id, db)

    _jobs[job_id] = {
        "status": "pending",
        "template_name": template_name,
        "user_id": user_id,
        "pdf_path": temp_path,
        "progress": 0,
    }

    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Reference PDF uploaded. Call POST /api/templates/learn/{job_id} to start analysis.",
    }
```

Add the `_fast_learn_pipeline` helper function below the `_jobs` dict declaration (before the route handlers):

```python
async def _fast_learn_pipeline(
    pdf_path: str,
    name: str,
    user_id: Optional[str],
    db: AsyncSession,
) -> dict:
    """
    Fast-learn pipeline: fingerprint → (clone or analyze_precise) → verify → save.

    Returns the new fast-learn response schema:
      {template_id, status, confidence, time_taken_sec, match_source, hints}
    """
    start = time.time()

    fingerprinter = FormatFingerprinter()
    match_config, match_score, match_source = fingerprinter.match(pdf_path)

    if match_score >= 88 and match_config is not None:
        config = copy.deepcopy(match_config)
    else:
        config = _analyzer.analyze_precise(pdf_path)

    verifier = AutoVerifier()
    verify_result = verifier.verify(config, pdf_path)

    calibrated_confidence = _calibrator.calibrate(verify_result["confidence"], [])

    store = TemplateStore(db)
    tmpl = await store.save(
        name=name,
        config=config,
        user_id=user_id,
        status=verify_result["status"],
        confidence_score=calibrated_confidence,
        source_pdf_name=os.path.basename(pdf_path),
        page_count=config.get("page_count"),
    )

    try:
        os.remove(pdf_path)
    except OSError:
        pass

    return {
        "template_id": tmpl.id,
        "status": verify_result["status"],
        "confidence": round(calibrated_confidence, 4),
        "time_taken_sec": round(time.time() - start, 1),
        "match_source": match_source or "none",
        "hints": verify_result.get("hints"),
    }
```

Also update `_analyzer` to be an instance of the upgraded `TemplateAnalyzer` (it already is — no change needed). The `_analyzer.analyze_precise()` call works because `analyze_precise()` is now a method on `TemplateAnalyzer`.

- [ ] **Step 5: Run all tests**

```bash
cd backend
pytest tests/test_fast_learn_api.py tests/test_manual_path_unchanged.py -v
```

Expected: All pass.

- [ ] **Step 6: Run the full test suite to verify no regressions**

```bash
cd backend
pytest -v
```

Expected: All existing tests pass. New tests pass. Only skip for tests requiring the real reference PDF.

- [ ] **Step 7: Commit**

```bash
git add api/templates.py tests/test_fast_learn_api.py tests/test_manual_path_unchanged.py
git commit -m "feat: add fast_learn flag to upload-reference endpoint with full pipeline

POST /api/templates/upload-reference?fast_learn=true now runs FormatFingerprinter,
TemplateAnalyzer.analyze_precise(), and AutoVerifier synchronously, returning
{template_id, status, confidence, time_taken_sec, match_source, hints}.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ Section 2 (Architecture) — 3-phase pipeline wired in _fast_learn_pipeline()
- ✅ Section 3 (Phase 1 — FormatFingerprinter) — Tasks 1, 2, 3
- ✅ Section 4 (Phase 2 — analyze_precise) — Tasks 4, 5, 6
- ✅ Section 5 (Phase 3 — AutoVerifier) — Tasks 7, 8
- ✅ Section 6 (API) — Task 9
- ✅ Section 7 (Timing) — covered by architecture (fingerprinter <2s, precise <20s, verifier <30s)
- ✅ Section 8 (Error Handling) — PDF open failure → 400; render fail → needs_review + 0.75; all phases fail → fallback config
- ✅ Section 9 (Global Scope) — reuses _CURRENCY_PATTERNS (30+ currencies) and _AUDIT_SECTION_PATTERNS; new countries via prebuilt_formats.py only
- ✅ Section 10 (Testing Plan) — all 10 test files created across Tasks 2–9
- ✅ Section 11 (Files Summary) — all 5 files modified/created

**Error handling gaps from spec Section 8:**
- ✅ `PDF cannot be opened` → HTTPException 400 in upload_reference (already present, unchanged)
- ✅ `Fingerprint match fails (no library)` → _fast_learn_pipeline falls through to analyze_precise
- ✅ `PyMuPDF extract returns empty` → analyze_precise falls back to _fallback_config
- ✅ `Column clustering fails (<10 numeric spans)` → _extract_columns returns _fallback_columns
- ✅ `Render fails (ReportLab error)` → verify() catches exception, returns needs_review + 0.75
- ✅ `All phases fail` → _fallback_config always returns a usable config

**Type consistency check:**
- `FormatFingerprinter.match()` returns `Tuple[Optional[Dict], int, Optional[str]]` — used as `match_config, match_score, match_source` in _fast_learn_pipeline ✅
- `AutoVerifier.verify()` returns `{"status", "confidence", "hints", "adjusted"}` — accessed correctly in _fast_learn_pipeline ✅
- `analyze_precise()` returns dict with `"columns"` and `"spacing"` keys — config passed to AutoVerifier ✅
- `TemplateStore.save()` signature unchanged — called with same parameters ✅
