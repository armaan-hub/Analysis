# Fast Format Learning — Design Spec
**Date:** 2026-04-19  
**Goal:** Any user uploads any audit PDF → format learned in <5 minutes, 95%+ pixel accuracy, zero manual touch  
**Scope:** UAE/GCC now, global (any country, any standard) later  

---

## 1. Problem Statement

The current template learning flow requires 25–30 minutes of manual fine-tuning after extraction. The bottleneck is not the extraction speed (PyMuPDF runs in ~10 sec) — it is that the extracted column positions, line spacing, and font assignments are approximate, forcing a human to correct them.

Three specific extraction failures cause 95% of manual work:
- **Column widths** — current extraction does not detect x-coordinate column boundaries
- **Spacing** — current extraction does not measure y-gap between lines per section
- **Fonts** — current extraction sorts all sizes together instead of role-mapping them

The fix is to upgrade the extraction precision and add automated verification — not to build a parallel pipeline.

---

## 2. Architecture

The upgrade touches the existing pipeline at exactly 3 points: before extraction (fingerprint match), during extraction (precise coordinate mining), and after extraction (automated visual verification). No parallel pipeline is created.

```
EXISTING PIPELINE (manual path — still works, unchanged):
  Upload PDF → TemplateAnalyzer.analyze() → TemplateStore

UPGRADED PIPELINE (fast path):

  Upload PDF
       │
  FormatFingerprinter          NEW FILE: format_fingerprinter.py
  (2 sec)                      Reuses: prebuilt_formats.py
       │                                document_format_analyzer._CURRENCY_PATTERNS
  Match ≥88%?                           document_format_analyzer._AUDIT_SECTION_PATTERNS
  YES → clone prebuilt (8 sec)
  NO  → full extraction
       │
  TemplateAnalyzer             EXISTING FILE: template_analyzer.py
  .analyze_precise()           NEW METHOD added to existing class
  (20 sec)                     Existing .analyze() untouched
       │
  AutoVerifier                 NEW FILE: auto_verifier.py
  (30 sec)                     Uses: Pillow, ReportLab, ConfidenceCalibrator
  ≥95%  → auto-approve
  85-95%→ 1 auto-adjust pass
  <85%  → structured hints to user
       │
  TemplateStore                UNCHANGED
  (same schema, same API)
```

**Files changed:**

| File | Type | Change |
|---|---|---|
| `backend/core/format_fingerprinter.py` | NEW | Phase 1 — match against library |
| `backend/core/template_analyzer.py` | UPGRADED | Add `analyze_precise()` method |
| `backend/core/auto_verifier.py` | NEW | Phase 3 — render + pixel diff |
| `backend/api/templates.py` | MINOR EDIT | Add `fast_learn=true` flag to existing upload route |
| `backend/core/prebuilt_formats.py` | MINOR EDIT | Add fingerprint signatures to each entry |

**Files unchanged:** `template_store.py`, `batch_template_learner.py`, `confidence_calibrator.py`, `template_report_generator.py`, `document_format_analyzer.py`, `format_extractor.py`

---

## 3. Phase 1 — FormatFingerprinter

**File:** `backend/core/format_fingerprinter.py`  
**Time budget:** ≤2 seconds  
**Purpose:** Determine if the uploaded PDF is close enough to an existing template to skip full extraction

### Fingerprint Schema

A fingerprint is a small dict computed from the PDF in <1 second:

```python
{
  "page_size": "A4" | "US_LETTER" | "CUSTOM",
  "currency": "AED" | "SAR" | "USD" | "INR" | ...,
  "section_count": int,            # number of detected audit sections
  "has_notes": bool,               # Notes section present
  "col_count": int,                # number of data columns (2=single year, 3=comparative)
  "format_family": "IFRS" | "GAAP" | "local-tax" | "unknown"
}
```

### Matching Logic

1. Open PDF with PyMuPDF, scan first 3 pages only (fast)
2. Detect page size from `page.rect`
3. Detect currency using `_CURRENCY_PATTERNS` from `document_format_analyzer.py` (reuse, do not copy)
4. Detect section headings using `_AUDIT_SECTION_PATTERNS` from `document_format_analyzer.py`
5. Count data columns by detecting year headers (2021, 2020 etc.)
6. Compute similarity score against each entry in `prebuilt_formats.PREBUILT_FORMATS` + user's saved templates in `TemplateStore`

### Similarity Score

```python
score = 0
if fingerprint["page_size"] == candidate["page_size"]:     score += 30
if fingerprint["currency"] == candidate["currency"]:        score += 25
if fingerprint["format_family"] == candidate["format_family"]: score += 20
if abs(fingerprint["section_count"] - candidate["section_count"]) <= 1: score += 15
if fingerprint["col_count"] == candidate["col_count"]:      score += 10
# max = 100
```

**If best match ≥88:** Clone that template config, pass to Phase 3 (skip Phase 2 full extraction, run delta extraction only for columns + spacing)  
**If best match <88:** Pass to Phase 2 full precise extraction

### Fingerprint Library Growth

Every format approved by AutoVerifier adds its fingerprint to the library. Over time, more uploads hit the fast path (≥88 match) and skip full extraction entirely. This is the self-improving mechanism.

**Prebuilt fingerprints to add to `prebuilt_formats.py`:**

```python
# Add to each entry in PREBUILT_FORMATS:
"fingerprint": {
  "page_size": "A4",
  "currency": "AED",   # varies per format
  "section_count": 6,
  "has_notes": True,
  "col_count": 3,
  "format_family": "IFRS"
}
```

---

## 4. Phase 2 — TemplateAnalyzer.analyze_precise()

**File:** `backend/core/template_analyzer.py` (existing)  
**Time budget:** ≤20 seconds  
**Change:** Add one new public method `analyze_precise()` alongside existing `analyze()`

### What the existing `analyze()` gets wrong

The current `_extract_fonts()` sorts all font sizes descending and assigns the top 3 to heading/body/footer. This fails when a document has many font sizes (like ABC Magnus with 14 pages of notes) — the "largest" font may be a page number, not a heading.

The current `_extract_margins()` finds the outermost text bounding box. This gives margins correctly but does not detect internal column positions or line spacing.

### New Method: `analyze_precise(pdf_path: str) -> Dict[str, Any]`

Returns the same schema as `analyze()` but with higher precision fields added:

```python
{
  # All existing fields from analyze() ...
  "page": {...},
  "margins": {...},
  "fonts": {...},        # improved — see font role mapping below
  "tables": [...],       # improved — now includes column x-positions
  "sections": [...],
  "confidence": float,
  "source": str,
  "page_count": int,

  # New precision fields:
  "columns": {           # NEW: precise x-coordinate column boundaries
    "label_col_x": float,      # left edge of label column
    "notes_col_x": float,      # x-position of Notes/Ref column
    "year1_col_x": float,      # x-position of current year values
    "year2_col_x": float,      # x-position of prior year values
    "currency_label_y": float  # y-position of "AED AED" header row
  },
  "spacing": {           # NEW: measured line heights per section type
    "heading_after": float,    # gap after section headings (pt)
    "row_height": float,       # standard data row height (pt)
    "section_gap": float,      # gap between major sections (pt)
    "subtotal_gap": float,     # gap before/after subtotal lines
    "indent_level_1": float,   # first-level indent (pt)
    "indent_level_2": float    # second-level indent (pt, for sub-items)
  }
}
```

### Column Detection Algorithm

Uses `get_text("dict")` — already used by existing methods — but at span level instead of block level:

1. Collect all span x0 values from pages 1–4 (financial statements, not notes)
2. Filter to spans containing only numbers or dashes (value cells, not labels)
3. Use 1D k-means clustering with k=2 (current year, prior year) or k=3 (notes ref, current, prior)
4. Cluster centroids = column x-positions
5. Label column = leftmost text block x0 (already detected by `_extract_margins`)

**Fallback:** If clustering fails (fewer than 10 numeric spans found), use page-width proportions from the matched prebuilt template

### Spacing Detection Algorithm

1. For each page 1–4, extract all text spans with their y0 coordinates
2. Sort spans by y0, compute consecutive y-gaps
3. Cluster gaps into 3 groups: small (same line), medium (row gap), large (section gap)
4. Assign: `row_height` = median of medium cluster, `section_gap` = median of large cluster
5. For indentation: collect label spans, find two most-common x0 values → `indent_level_1` and `indent_level_2`

### Font Role Mapping (improved)

Instead of sorting all sizes, classify by role:

1. Scan all spans, collect (text, font_name, font_size, is_bold, page_num)
2. Apply rules:
   - Spans matching `_AUDIT_SECTION_PATTERNS` → `heading` role
   - Spans with font_size ≤ 8 and in bottom 10% of page → `footer` role
   - Numeric-only spans in value columns → `number` role
   - All remaining spans → `body` role
3. For each role, take the most common (font_name, font_size) pair

**Note references** (Note 6, Note 7 etc.) get their own role `note_ref` with detected size — this is what drives Notes column alignment.

---

## 5. Phase 3 — AutoVerifier

**File:** `backend/core/auto_verifier.py`  
**Time budget:** ≤30 seconds (single pass), ≤90 seconds (with 1 adjust cycle)  
**Purpose:** Confirm extracted config produces a 95%+ pixel match against the reference, without human review

### Verification Flow

```
config from Phase 2
        │
Render test page (ReportLab)   — render page 1 of reference using extracted config
        │
Convert both to images (Pillow) — reference PDF page 1 → image, test render → image
        │
Pixel diff                      — compare pixel-by-pixel, compute similarity score
        │
Score ≥95%?
  YES → status = "verified", confidence = score, save to TemplateStore
  NO (85-95%) → run AutoAdjust (one pass), re-verify
  NO (<85%) → status = "needs_review", return StructuredHints to user
```

### Pixel Diff Method

```python
from PIL import Image, ImageChops
import numpy as np

def pixel_similarity(img_ref: Image, img_test: Image) -> float:
    # Resize test to match reference dimensions
    img_test = img_test.resize(img_ref.size)
    # Convert to grayscale arrays
    arr_ref = np.array(img_ref.convert("L"), dtype=float)
    arr_test = np.array(img_test.convert("L"), dtype=float)
    # Mean absolute difference, normalized
    diff = np.abs(arr_ref - arr_test).mean()
    return round(1.0 - (diff / 255.0), 4)
```

Renders at 150 DPI (fast enough, precise enough for layout detection).

### AutoAdjust Pass

If score is 85–95%, the system identifies which region failed:

1. Split both images into 6 horizontal bands
2. Find band(s) with highest pixel diff
3. Map band to config element:
   - Top band → header/margin issue → nudge `margins.top` ±4pt
   - Column bands → column positions → nudge `columns.year1_col_x` ±3pt
   - Row bands → spacing → nudge `spacing.row_height` ±1pt
4. Re-render, re-score
5. Keep adjustment only if score improves

**AutoAdjust runs once only** — not a loop. If one pass does not reach 95%, fall through to StructuredHints.

### StructuredHints (for <85% or failed adjust)

Instead of free-form editing, present the user with targeted binary choices:

```json
{
  "hints": [
    {
      "element": "columns",
      "message": "The 2021 column appears to be 12 points to the right of the reference",
      "options": ["shift left 12pt", "leave as-is"]
    },
    {
      "element": "spacing.row_height",
      "message": "Row height appears 2pt smaller than reference",
      "options": ["increase by 2pt", "leave as-is"]
    }
  ]
}
```

User answers 2–3 questions (radio buttons in UI) → system applies → re-verifies. This replaces 20 minutes of free-form editing with 30 seconds of guided correction.

### Integration with ConfidenceCalibrator

After save, `ConfidenceCalibrator` is called with the pixel similarity score as the initial confidence. When users later give feedback ("output looks correct" / "output looks wrong"), the calibrator adjusts. This is already built — AutoVerifier just feeds it the initial score.

---

## 6. API Changes

**File:** `backend/api/templates.py`  
**Change:** Add `fast_learn: bool = False` query param to existing upload route

```
POST /api/templates/upload-reference?fast_learn=true
```

When `fast_learn=true`:
1. Save uploaded PDF to temp
2. Call `FormatFingerprinter.match(pdf_path)` → best_match + score
3. If score ≥88: clone best_match config, skip to AutoVerifier
4. If score <88: call `TemplateAnalyzer.analyze_precise(pdf_path)`
5. Call `AutoVerifier.verify(config, pdf_path)`
6. Call `TemplateStore.save(...)` with result
7. Return `{template_id, status, confidence, time_taken_sec}`

When `fast_learn=false` (default): existing behavior unchanged.

**New response fields** (added to existing response schema):

```json
{
  "template_id": "uuid",
  "status": "verified | needs_review",
  "confidence": 0.96,
  "time_taken_sec": 52,
  "match_source": "prebuilt-gcc-standard | user-template-xyz | none",
  "hints": null
}
```

If `status = "needs_review"`, `hints` contains the StructuredHints array.

---

## 7. Timing Targets

| Scenario | Phase 1 | Phase 2 | Phase 3 | Total |
|---|---|---|---|---|
| Known format (≥88% match) | 2 sec | 8 sec (delta only) | 30 sec | **~40 sec** |
| Similar format (70–88% match) | 2 sec | 20 sec (full precise) | 30 sec | **~52 sec** |
| New format (<70% match) | 2 sec | 20 sec (full precise) | 60 sec (with adjust) | **~82 sec** |
| Failed format (<85% verify) | 2 sec | 20 sec | 10 sec + hints | **<2 min + 30 sec user input** |

All scenarios are under 5 minutes. Most known formats (UAE/GCC) hit under 1 minute.

---

## 8. Error Handling

| Failure | Behaviour |
|---|---|
| PDF cannot be opened | Return 400 with `"error": "invalid_pdf"` |
| Fingerprint match fails (no library) | Skip to Phase 2 full extraction |
| PyMuPDF extract returns empty | Fall back to existing `analyze()` method |
| Column clustering fails (<10 numeric spans) | Use prebuilt column proportions |
| Render fails (ReportLab error) | Skip AutoVerifier, save with `status="needs_review"` and `confidence=0.75` |
| All phases fail | Save with prebuilt IFRS Standard config + `status="needs_review"` — user always gets something usable |

No format upload should ever return a 500. The system always produces a usable config.

---

## 9. Global Scope Readiness

The design handles global expansion without code changes:

- **Currency detection** reuses `_CURRENCY_PATTERNS` in `document_format_analyzer.py` which already covers 30+ currencies (AED, SAR, INR, USD, GBP, EUR, PKR, BDT etc.)
- **Format family detection** is pattern-based — adding India GAAP or Bangladesh FRS requires only adding entries to `prebuilt_formats.py`, not touching pipeline code
- **Section patterns** in `_AUDIT_SECTION_PATTERNS` already match IFRS and GAAP section names
- **Fingerprint library** grows with every approved format — as more international users join, the library expands automatically

To add a new country/standard: add 1 entry to `prebuilt_formats.py` with its fingerprint. No pipeline changes needed.

---

## 10. Testing Plan

| Test | What it checks |
|---|---|
| `test_fingerprinter_gcc.py` | ABC Magnus matches `prebuilt-gcc-standard` at ≥88% |
| `test_fingerprinter_unknown.py` | Truly new format returns <70% and falls through to full extraction |
| `test_analyze_precise_columns.py` | Column x-positions within ±5pt of manually measured reference |
| `test_analyze_precise_spacing.py` | `row_height` and `section_gap` within ±2pt |
| `test_analyze_precise_fonts.py` | Font roles (heading/body/footer) match reference |
| `test_autoverifier_pass.py` | Known format passes ≥95% pixel similarity |
| `test_autoverifier_adjust.py` | 85–95% format passes after one AutoAdjust cycle |
| `test_autoverifier_hints.py` | <85% format returns StructuredHints with ≥1 actionable item |
| `test_fast_learn_api.py` | `POST /upload-reference?fast_learn=true` returns in <90 sec for ABC Magnus |
| `test_manual_path_unchanged.py` | `fast_learn=false` still works exactly as before |

---

## 11. Files Summary

```
MODIFIED (minor):
  backend/core/template_analyzer.py      — add analyze_precise() method
  backend/core/prebuilt_formats.py       — add fingerprint signatures to each entry
  backend/api/templates.py               — add fast_learn flag + fast path logic

NEW:
  backend/core/format_fingerprinter.py   — Phase 1: fingerprint + library match
  backend/core/auto_verifier.py          — Phase 3: render + pixel diff + adjust

UNCHANGED (zero edits):
  backend/core/template_store.py
  backend/core/batch_template_learner.py
  backend/core/confidence_calibrator.py
  backend/core/document_format_analyzer.py
  backend/core/format_extractor.py
  backend/core/template_report_generator.py
```
