# Audit Pipeline Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the full audit wizard end-to-end: scanned PDF extraction (NotebookLM approach), account grouping, analysis chat SSE error, and report formatting.

**Architecture:** PyMuPDF's `fitz.get_pixmap()` renders scanned PDF pages to images in-memory (no poppler needed), which are sent to the vision LLM for extraction — the same approach NotebookLM uses with Gemini. Once extraction works, the template analyzer gets real formatting data, account grouping produces IFRS-structured drafts, and the analysis chat SSE format mismatch is patched.

**Tech Stack:** Python/FastAPI, PyMuPDF (fitz already installed), python-docx, OpenAI vision API, SQLAlchemy async.

**Do first:** Tasks run in order — each unlocks the next.

---

## File Map

| File | What changes |
|------|-------------|
| `backend/core/prior_year_extractor.py` | Replace `_extract_via_vision` (uses poppler) with `_extract_via_fitz_vision` (uses fitz pixmap) |
| `backend/core/document_format_analyzer.py` | Add `_analyze_via_vision()` called when scanned PDF returns empty text |
| `backend/api/reports.py` | (a) Default opinion fix; (b) `/analysis-chat` context trim + JSON SSE fix |
| `backend/core/agents/trial_balance_classifier.py` | New `group_tb_for_ifrs()` function |
| `backend/core/agents/audit_agent.py` | Call `group_tb_for_ifrs()` before building LLM prompt |
| `backend/core/template_report_generator.py` | Apply `formatting_rules` from template to DOCX column widths and number format |
| `backend/tests/test_prior_year_extractor.py` | Add tests for fitz vision path |
| `backend/tests/test_audit_formatter.py` | Add test for formatting_rules application |

---

## Task 1 — Replace pdf2image with fitz.get_pixmap() in prior_year_extractor.py

**Files:**
- Modify: `backend/core/prior_year_extractor.py`
- Test: `backend/tests/test_prior_year_extractor.py`

**Background:** The existing `_extract_via_vision()` function calls `pdf2image.convert_from_path()` which requires poppler (not installed). PyMuPDF (`fitz`) is already installed and can render pages to images natively. The vision LLM call itself is correct — only the image-generation step needs replacing.

- [ ] **Step 1: Read the existing function to understand what you're replacing**

Open `backend/core/prior_year_extractor.py` lines 130–201. Note:
- It calls `convert_from_path(file_path, first_page=1, last_page=8, dpi=150)`
- It iterates `pages[:4]` and sends each as a base64 PNG to the vision LLM
- The LLM call pattern (messages with `image_url`) is correct and must be kept

- [ ] **Step 2: Write a failing test**

In `backend/tests/test_prior_year_extractor.py`, add at the bottom:

```python
import pytest
import os

@pytest.mark.asyncio
async def test_fitz_vision_extraction_returns_rows():
    """
    Smoke test: given a real scanned PDF, fitz vision extraction returns at least one row.
    Uses the sample PDF at backend/tests/fixtures/scanned_sample.pdf if present,
    otherwise skips (the function should not crash on a valid digital PDF either).
    """
    from core.prior_year_extractor import _extract_via_fitz_vision

    fixture = os.path.join(os.path.dirname(__file__), "fixtures", "scanned_sample.pdf")
    if not os.path.exists(fixture):
        pytest.skip("No fixture PDF — skipping vision extraction test")

    rows = await _extract_via_fitz_vision(fixture)
    assert isinstance(rows, list)
    # If the PDF has financial tables the LLM should find at least one row
    # (If fixture is empty/blank, zero rows is acceptable — just must not raise)
```

- [ ] **Step 3: Run test to confirm it fails (function does not exist yet)**

```bash
cd backend
uv run pytest tests/test_prior_year_extractor.py::test_fitz_vision_extraction_returns_rows -v
```

Expected: `ImportError: cannot import name '_extract_via_fitz_vision'`

- [ ] **Step 4: Add the new `_extract_via_fitz_vision` function**

In `backend/core/prior_year_extractor.py`, add this function **after the existing `_extract_via_vision` function** (around line 200):

```python
async def _extract_via_fitz_vision(file_path: str) -> list[dict]:
    """
    Render PDF pages to images using fitz.get_pixmap() (no poppler needed),
    then send to the vision LLM to extract financial table rows.
    This is the NotebookLM approach: direct visual understanding of the document.
    """
    try:
        import fitz  # already installed as PyMuPDF
        import base64
        import io
        from core.llm_manager import get_llm_provider

        doc = fitz.open(file_path)
        if doc.page_count == 0:
            doc.close()
            return []

        # Build multimodal message: text instruction + up to 8 page images
        content_parts: list[dict] = [
            {
                "type": "text",
                "text": (
                    "These are pages from a financial audit report. "
                    "Extract every financial statement table row that has an account name "
                    "and a numeric amount. "
                    "The prior year column is the SECOND (rightmost) numeric column. "
                    "Ignore page numbers, percentages, and note references. "
                    "Return ONLY a valid JSON array with no explanation. "
                    "Each element: {\"account_name\": \"string\", \"prior_year_value\": number_or_null}"
                ),
            }
        ]

        for i in range(min(8, doc.page_count)):
            # 2x scale gives ~150 dpi on standard A4 — readable by vision LLM
            mat = fitz.Matrix(2, 2)
            pix = doc[i].get_pixmap(matrix=mat)
            png_bytes = pix.tobytes("png")
            b64 = base64.b64encode(png_bytes).decode()
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            })

        doc.close()

        llm = get_llm_provider("openai")  # vision requires OpenAI or Claude provider
        resp = await llm.chat(
            [{"role": "user", "content": content_parts}],
            temperature=0.1,
            max_tokens=3000,
        )

        raw = resp.content.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```\s*$", "", raw, flags=re.MULTILINE)
        raw = raw.strip()

        # Find the JSON array in the response
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            raw = match.group(0)

        page_rows = json.loads(raw)
        if not isinstance(page_rows, list):
            return []

        result = []
        for r in page_rows:
            if not isinstance(r, dict):
                continue
            account = r.get("account_name", "")
            val = r.get("prior_year_value")
            if account and val is not None:
                try:
                    result.append({
                        "account_name": str(account),
                        "prior_year_value": float(val),
                    })
                except (ValueError, TypeError):
                    continue

        # Deduplicate by account name (keep last occurrence)
        seen: dict[str, dict] = {}
        for row in result:
            seen[row["account_name"].lower()] = row
        return list(seen.values())

    except ImportError:
        logger.warning("fitz (PyMuPDF) not available for vision extraction")
        return []
    except Exception as exc:
        logger.error(f"fitz vision extraction failed: {exc}")
        return []
```

- [ ] **Step 5: Wire the new function into `extract_prior_year_from_pdf`**

In the same file, find the `extract_prior_year_from_pdf` function. Replace the section starting `# Last resort: vision LLM (requires poppler)`:

**Find (around line 266):**
```python
    # Last resort: vision LLM (requires poppler)
    if all_text.strip():
        logger.info("Text extraction found no financial data, trying vision fallback")
    rows = await _extract_via_vision(file_path)
    if rows:
        return {
            "rows": rows,
            "extraction_method": "vision",
            "confidence": 0.75,
            "context": build_prior_year_context(rows),
            "template": template,
        }
```

**Replace with:**
```python
    # Stage 4: fitz pixmap → vision LLM (no poppler required — NotebookLM approach)
    logger.info("Trying fitz vision extraction (pixmap → vision LLM)")
    rows = await _extract_via_fitz_vision(file_path)
    if rows:
        return {
            "rows": rows,
            "extraction_method": "vision",
            "confidence": 0.75,
            "context": build_prior_year_context(rows),
            "template": template,
        }

    # Stage 5: pdf2image fallback (only if poppler happens to be installed)
    rows = await _extract_via_vision(file_path)
    if rows:
        return {
            "rows": rows,
            "extraction_method": "vision_poppler",
            "confidence": 0.70,
            "context": build_prior_year_context(rows),
            "template": template,
        }
```

- [ ] **Step 6: Run all prior-year extractor tests**

```bash
cd backend
uv run pytest tests/test_prior_year_extractor.py -v
```

Expected: all existing tests pass + new test passes (or skips if no fixture).

- [ ] **Step 7: Commit**

```bash
git add backend/core/prior_year_extractor.py backend/tests/test_prior_year_extractor.py
git commit -m "fix: replace pdf2image with fitz.get_pixmap() for scanned PDF extraction"
```

---

## Task 2 — Fix document_format_analyzer.py for scanned PDFs

**Files:**
- Modify: `backend/core/document_format_analyzer.py`
- Test: `backend/tests/test_document_format_analyzer.py`

**Background:** When a scanned PDF is opened with PyMuPDF, `page.get_text()` returns empty string. The analyzer hits line 72: `if not full_text.strip(): return _empty_result()` and exits immediately. This is why template confidence = 0%, method = failed, pages = undefined. Fix: when text is empty, use fitz pixmap → vision LLM to extract the template structure.

- [ ] **Step 1: Write a failing test**

In `backend/tests/test_document_format_analyzer.py`, add:

```python
@pytest.mark.asyncio
async def test_analyze_returns_pages_count_not_zero():
    """
    For any valid PDF (even if scanned), pages should not be 0 and
    document_structure should be populated.
    """
    import os
    from core.document_format_analyzer import analyze_audit_document

    fixture = os.path.join(os.path.dirname(__file__), "fixtures", "scanned_sample.pdf")
    if not os.path.exists(fixture):
        pytest.skip("No fixture PDF")

    result = await analyze_audit_document(fixture)
    assert result["document_structure"]["pages"] > 0, "pages must not be 0 for a valid PDF"
    assert result["document_structure"]["pages"] is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/test_document_format_analyzer.py::test_analyze_returns_pages_count_not_zero -v
```

Expected: FAIL — `AssertionError: pages must not be 0` (or test skips if no fixture — in that case, create a minimal fixture first by copying any PDF you have to `backend/tests/fixtures/scanned_sample.pdf`).

- [ ] **Step 3: Add `_analyze_via_vision()` to document_format_analyzer.py**

At the **bottom** of `backend/core/document_format_analyzer.py`, before the `_empty_result()` function, add:

```python
async def _analyze_via_vision(file_path: str) -> dict:
    """
    For scanned PDFs where text extraction yields nothing.
    Renders pages via fitz pixmap and sends to vision LLM to extract
    document structure, formatting rules, account grouping, and metadata.
    """
    try:
        import base64
        from core.llm_manager import get_llm_provider

        doc = fitz.open(file_path)
        actual_pages = doc.page_count

        content_parts: list[dict] = [
            {
                "type": "text",
                "text": (
                    "Analyze these pages from a financial audit report PDF. "
                    "Return ONLY valid JSON (no explanation) with this exact structure:\n"
                    "{\n"
                    '  "document_structure": {\n'
                    '    "title": "string",\n'
                    '    "date_range": "string",\n'
                    '    "company_name": "string",\n'
                    '    "auditor_name": "string or empty",\n'
                    '    "sections": [\n'
                    '      {"title": "string", "level": 1, "content_type": "table or narrative"}\n'
                    "    ]\n"
                    "  },\n"
                    '  "account_grouping": {},\n'
                    '  "terminology": {"currency": "AED or USD", "common_phrases": [], "headings_seen": []},\n'
                    '  "formatting_rules": {\n'
                    '    "table_formatting": {"currency_format": "#,##0 or #,##0.00", "negative_number_format": "(X,XXX) or -X,XXX"},\n'
                    '    "font_hierarchy": {"heading_1_bold": true, "table_header_bold": true},\n'
                    '    "page_break_after_sections": []\n'
                    "  }\n"
                    "}"
                ),
            }
        ]

        for i in range(min(6, actual_pages)):
            mat = fitz.Matrix(2, 2)
            pix = doc[i].get_pixmap(matrix=mat)
            b64 = base64.b64encode(pix.tobytes("png")).decode()
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            })

        doc.close()

        llm = get_llm_provider("openai")
        resp = await llm.chat(
            [{"role": "user", "content": content_parts}],
            temperature=0.1,
            max_tokens=3000,
        )

        raw = resp.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```\s*$", "", raw, flags=re.MULTILINE)
        raw = raw.strip()

        result = json.loads(raw)

        # Ensure sections have required fields
        for s in result.get("document_structure", {}).get("sections", []):
            if "section_id" not in s:
                s["section_id"] = str(uuid.uuid4())
            if "start_page" not in s:
                s["start_page"] = 1
            if "estimated_position" not in s:
                s["estimated_position"] = "top"
            if "table_structure" not in s:
                s["table_structure"] = None

        # Always set pages from actual count (fixes "pages: undefined")
        result["document_structure"]["pages"] = actual_pages

        return result

    except Exception as exc:
        logger.error(f"Vision template analysis failed: {exc}")
        empty = _empty_result()
        # Even on failure, try to set real page count
        try:
            doc2 = fitz.open(file_path)
            empty["document_structure"]["pages"] = doc2.page_count
            doc2.close()
        except Exception:
            pass
        return empty
```

- [ ] **Step 4: Update `analyze_audit_document` to call vision path when text is empty**

Find the block in `analyze_audit_document` (lines 66–74):

```python
    full_text = "\n".join(
        blk["text"] for page in page_blocks for blk in page
    )

    if not full_text.strip():
        doc.close()
        return _empty_result()
```

Replace with:

```python
    full_text = "\n".join(
        blk["text"] for page in page_blocks for blk in page
    )

    if not full_text.strip():
        actual_pages = doc.page_count
        doc.close()
        logger.info(f"Scanned PDF detected (no text layer) — using vision LLM for template extraction")
        result = await _analyze_via_vision(file_path)
        # Guarantee pages is set from the real count
        result["document_structure"]["pages"] = actual_pages
        return result
```

- [ ] **Step 5: Run all document_format_analyzer tests**

```bash
cd backend
uv run pytest tests/test_document_format_analyzer.py -v
```

Expected: all pass (or skip if no fixture).

- [ ] **Step 6: Commit**

```bash
git add backend/core/document_format_analyzer.py backend/tests/test_document_format_analyzer.py
git commit -m "fix: use fitz vision LLM for scanned PDF template extraction"
```

---

## Task 3 — Fix default Disclaimer of Opinion

**Files:**
- Modify: `backend/api/reports.py`

**Background:** When prior year data is missing (`extraction_method == "failed"`), the audit draft defaults to `DISCLAIMER_OF_OPINION` ("we cannot express an opinion"). This should only happen when the user explicitly selects it. Default should be `unqualified` with "N/A" for prior year comparatives.

- [ ] **Step 1: Find where the disclaimer default is set**

Search `backend/api/reports.py` for `disclaimer` and `opinion`. Look for the audit draft generation endpoint (around line 1570) and find where `opinion` defaults to `"disclaimer"` or where the disclaimer text is auto-populated.

Run:
```bash
grep -n "disclaimer\|opinion.*default\|default.*opinion" backend/api/reports.py
```

- [ ] **Step 2: Fix the default opinion value**

Find the code that sets the opinion when prior year data is missing. It will look something like:
```python
if not prior_year_rows:
    opinion = "disclaimer"
    disclaimer_text = "Due to insufficient audit evidence..."
```

Replace the auto-downgrade logic with:
```python
# Do NOT downgrade opinion just because prior year data is missing.
# Prior year absence = first year audit or user didn't upload — not a scope limitation.
# Keep whatever opinion was selected (default: unqualified).
if not prior_year_rows:
    prior_year_note = (
        "Comparative figures not available — "
        "first year of audit or prior year report not uploaded."
    )
else:
    prior_year_note = ""
```

Pass `prior_year_note` into the audit agent's kwargs so it can include it in the report body.

- [ ] **Step 3: Fix "Not provided" → "N/A" in the draft table**

Search for where `"Not provided"` is set as the prior year cell value:
```bash
grep -n "Not provided" backend/api/reports.py backend/core/agents/audit_agent.py
```

Replace every occurrence of `"Not provided"` with `"N/A"`.

- [ ] **Step 4: Manual test**

Start the backend and run through the audit wizard with a trial balance but NO prior year PDF. The draft report should now say "Unqualified Opinion" (not Disclaimer) and prior year column should show "N/A".

- [ ] **Step 5: Commit**

```bash
git add backend/api/reports.py backend/core/agents/audit_agent.py
git commit -m "fix: default to unqualified opinion when prior year data is absent"
```

---

## Task 4 — Add IFRS account grouping function

**Files:**
- Modify: `backend/core/agents/trial_balance_classifier.py`
- Test: `backend/tests/test_account_placement_engine.py`

**Background:** The audit draft currently shows every account as a flat individual row. We need a function that groups TB rows into the IFRS Statement of Financial Position and Statement of Profit or Loss hierarchy, computes subtotals, and returns a structured dict the LLM can format as a proper financial statement.

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_account_placement_engine.py`, add:

```python
def test_group_tb_for_ifrs_produces_correct_structure():
    from core.agents.trial_balance_classifier import group_tb_for_ifrs

    tb_data = [
        {"account": "Cash in Hand", "mappedTo": "Current Assets", "amount": 10000},
        {"account": "Bank Account", "mappedTo": "Current Assets", "amount": 50000},
        {"account": "Fixed Assets", "mappedTo": "Non-Current Assets", "amount": 200000},
        {"account": "Sundry Creditors", "mappedTo": "Current Liabilities", "amount": -30000},
        {"account": "Capital Account", "mappedTo": "Equity", "amount": -100000},
        {"account": "Commission Revenue", "mappedTo": "Revenue", "amount": -500000},
        {"account": "Salary Expense", "mappedTo": "Operating Expenses", "amount": 80000},
    ]

    grouped = group_tb_for_ifrs(tb_data)

    # Must have these top-level sections
    assert "current_assets" in grouped
    assert "non_current_assets" in grouped
    assert "current_liabilities" in grouped
    assert "equity" in grouped
    assert "revenue" in grouped
    assert "operating_expenses" in grouped

    # Subtotals must be correct
    assert grouped["current_assets"]["total"] == 60000   # 10000 + 50000
    assert grouped["non_current_assets"]["total"] == 200000
    assert abs(grouped["current_liabilities"]["total"]) == 30000

    # Each section must have rows list
    assert len(grouped["current_assets"]["rows"]) == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/test_account_placement_engine.py::test_group_tb_for_ifrs_produces_correct_structure -v
```

Expected: `ImportError: cannot import name 'group_tb_for_ifrs'`

- [ ] **Step 3: Add `group_tb_for_ifrs()` to trial_balance_classifier.py**

At the **bottom** of `backend/core/agents/trial_balance_classifier.py`, add:

```python
# ── IFRS category → section key mapping ──────────────────────────────────────

_IFRS_SECTION_MAP: dict[str, str] = {
    # Assets
    "Current Assets": "current_assets",
    "current assets": "current_assets",
    "Non-Current Assets": "non_current_assets",
    "non-current assets": "non_current_assets",
    "Fixed Assets": "non_current_assets",
    # Liabilities
    "Current Liabilities": "current_liabilities",
    "current liabilities": "current_liabilities",
    "Non-Current Liabilities": "non_current_liabilities",
    "non-current liabilities": "non_current_liabilities",
    # Equity
    "Equity": "equity",
    "equity": "equity",
    "Retained Earnings": "equity",
    # P&L
    "Revenue": "revenue",
    "revenue": "revenue",
    "Income": "revenue",
    "Cost of Sales": "cost_of_sales",
    "cost of sales": "cost_of_sales",
    "Operating Expenses": "operating_expenses",
    "operating expenses": "operating_expenses",
    "Finance Costs": "finance_costs",
    "Other Income": "other_income",
    "Input VAT": "current_assets",
    "Output VAT": "current_liabilities",
    "Cash and Cash Equivalents": "current_assets",
}

_SECTION_LABELS: dict[str, str] = {
    "non_current_assets": "Non-Current Assets",
    "current_assets": "Current Assets",
    "current_liabilities": "Current Liabilities",
    "non_current_liabilities": "Non-Current Liabilities",
    "equity": "Equity",
    "revenue": "Revenue",
    "cost_of_sales": "Cost of Sales",
    "operating_expenses": "Operating Expenses",
    "finance_costs": "Finance Costs",
    "other_income": "Other Income / (Expense)",
    "unclassified": "Other",
}

_SOFP_ORDER = [
    "non_current_assets", "current_assets",
    "current_liabilities", "non_current_liabilities",
    "equity",
]

_SOPL_ORDER = [
    "revenue", "cost_of_sales", "operating_expenses",
    "finance_costs", "other_income",
]


def group_tb_for_ifrs(tb_data: list[dict]) -> dict:
    """
    Group trial balance rows into IFRS financial statement sections.

    Input rows have keys: account, mappedTo, amount (positive = debit).
    Returns a dict of section_key → {label, rows, total}.

    Totals:
    - Assets: sum of positive amounts
    - Liabilities/Equity: sum of absolute amounts (stored as negatives in TB)
    - Revenue: absolute value of negative amounts
    - Expenses: sum of positive amounts
    """
    sections: dict[str, dict] = {}

    for row in tb_data:
        mapped = row.get("mappedTo", "") or ""
        amount = float(row.get("amount", 0) or 0)

        # Resolve section key
        section_key = _IFRS_SECTION_MAP.get(mapped)
        if not section_key:
            # Try case-insensitive match
            for k, v in _IFRS_SECTION_MAP.items():
                if k.lower() == mapped.lower():
                    section_key = v
                    break
        if not section_key:
            section_key = "unclassified"

        if section_key not in sections:
            sections[section_key] = {
                "label": _SECTION_LABELS.get(section_key, mapped),
                "rows": [],
                "total": 0.0,
            }

        sections[section_key]["rows"].append({
            "account": row.get("account", ""),
            "amount": amount,
        })
        sections[section_key]["total"] += amount

    # Make totals absolute for display consistency
    for key, sec in sections.items():
        sec["total"] = abs(sec["total"])

    # Add computed grand totals
    total_assets = (
        sections.get("non_current_assets", {}).get("total", 0)
        + sections.get("current_assets", {}).get("total", 0)
    )
    total_liabilities = (
        sections.get("current_liabilities", {}).get("total", 0)
        + sections.get("non_current_liabilities", {}).get("total", 0)
    )
    total_equity = sections.get("equity", {}).get("total", 0)
    gross_profit = (
        sections.get("revenue", {}).get("total", 0)
        - sections.get("cost_of_sales", {}).get("total", 0)
    )
    net_profit = (
        gross_profit
        - sections.get("operating_expenses", {}).get("total", 0)
        - sections.get("finance_costs", {}).get("total", 0)
        + sections.get("other_income", {}).get("total", 0)
    )

    sections["_totals"] = {
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "total_liabilities_and_equity": total_liabilities + total_equity,
        "gross_profit": gross_profit,
        "net_profit": net_profit,
    }

    return sections


def format_ifrs_for_llm(grouped: dict) -> str:
    """
    Format the grouped IFRS data as a readable text block for the LLM prompt.
    Produces a compact but structured representation.
    """
    lines = []

    lines.append("=== STATEMENT OF FINANCIAL POSITION ===")
    for key in _SOFP_ORDER:
        sec = grouped.get(key)
        if not sec:
            continue
        lines.append(f"\n{sec['label'].upper()}")
        for row in sec["rows"]:
            lines.append(f"  {row['account']:<45} AED {abs(row['amount']):>15,.0f}")
        lines.append(f"  {'Total ' + sec['label']:<45} AED {sec['total']:>15,.0f}")

    t = grouped.get("_totals", {})
    lines.append(f"\n  {'TOTAL ASSETS':<45} AED {t.get('total_assets', 0):>15,.0f}")
    lines.append(f"  {'TOTAL LIABILITIES':<45} AED {t.get('total_liabilities', 0):>15,.0f}")
    lines.append(f"  {'TOTAL EQUITY':<45} AED {t.get('total_equity', 0):>15,.0f}")
    lines.append(f"  {'TOTAL LIABILITIES AND EQUITY':<45} AED {t.get('total_liabilities_and_equity', 0):>15,.0f}")

    lines.append("\n=== STATEMENT OF PROFIT OR LOSS ===")
    for key in _SOPL_ORDER:
        sec = grouped.get(key)
        if not sec:
            continue
        lines.append(f"\n{sec['label'].upper()}")
        for row in sec["rows"]:
            lines.append(f"  {row['account']:<45} AED {abs(row['amount']):>15,.0f}")
        lines.append(f"  {'Total ' + sec['label']:<45} AED {sec['total']:>15,.0f}")

    lines.append(f"\n  {'GROSS PROFIT':<45} AED {t.get('gross_profit', 0):>15,.0f}")
    lines.append(f"  {'NET PROFIT / (LOSS)':<45} AED {t.get('net_profit', 0):>15,.0f}")

    return "\n".join(lines)
```

- [ ] **Step 4: Run the test**

```bash
cd backend
uv run pytest tests/test_account_placement_engine.py::test_group_tb_for_ifrs_produces_correct_structure -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/core/agents/trial_balance_classifier.py backend/tests/test_account_placement_engine.py
git commit -m "feat: add group_tb_for_ifrs() and format_ifrs_for_llm() for IFRS-structured audit drafts"
```

---

## Task 5 — Use grouped TB in audit_agent.py

**Files:**
- Modify: `backend/core/agents/audit_agent.py`
- Test: `backend/tests/test_audit_flow.py`

**Background:** `AuditAgent.generate()` currently sends raw individual TB rows to the LLM in a flat markdown table. Replace with the grouped IFRS structure from Task 4, so the LLM receives a properly structured financial statement and outputs the correct IFRS format.

- [ ] **Step 1: Write a failing test**

In `backend/tests/test_audit_flow.py`, add:

```python
@pytest.mark.asyncio
async def test_audit_draft_uses_grouped_structure(monkeypatch):
    """The LLM prompt sent to audit agent must contain IFRS section headers."""
    from core.agents.audit_agent import AuditAgent

    captured_messages = []

    class MockLLM:
        async def chat(self, messages, **kwargs):
            captured_messages.extend(messages)
            from core.llm_manager import LLMResponse
            return LLMResponse("Draft report content", "mock-model", "mock", 100)

    monkeypatch.setattr("core.agents.audit_agent.get_llm_provider", lambda *a: MockLLM())

    agent = AuditAgent()
    tb_data = [
        {"account": "Cash", "mappedTo": "Current Assets", "amount": 50000},
        {"account": "Revenue", "mappedTo": "Revenue", "amount": -200000},
        {"account": "Salaries", "mappedTo": "Operating Expenses", "amount": 80000},
    ]
    await agent.generate(tb_data, {})

    # The user message sent to LLM must contain IFRS section headers
    user_msg = next(m for m in captured_messages if m["role"] == "user")
    assert "STATEMENT OF FINANCIAL POSITION" in user_msg["content"]
    assert "STATEMENT OF PROFIT OR LOSS" in user_msg["content"]
    assert "TOTAL ASSETS" in user_msg["content"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/test_audit_flow.py::test_audit_draft_uses_grouped_structure -v
```

Expected: FAIL — `AssertionError: STATEMENT OF FINANCIAL POSITION not in content`

- [ ] **Step 3: Update audit_agent.py**

In `backend/core/agents/audit_agent.py`, add the import at the top:
```python
from core.agents.trial_balance_classifier import group_tb_for_ifrs, format_ifrs_for_llm
```

In the `generate()` method, find where `context_lines` is built and TB rows are added (around line 123):

**Find:**
```python
        if tb_data:
            context_lines.append("\n**Trial Balance Summary:**")
            context_lines.append("| Account | Category | Amount (AED) |")
            context_lines.append("|---------|----------|-------------|")
            for row in tb_data[:30]:  # cap at 30 rows for token efficiency
                context_lines.append(
                    f"| {row.get('account', '')} | {row.get('mappedTo', '')} | "
                    f"{float(row.get('amount', 0)):,.2f} |"
                )
```

**Replace with:**
```python
        if tb_data:
            grouped = group_tb_for_ifrs(tb_data)
            ifrs_text = format_ifrs_for_llm(grouped)
            context_lines.append("\n**Financial Data (IFRS Grouped):**")
            context_lines.append(ifrs_text)
```

Also update the `system_prompt` in `generate()` to include explicit IFRS output instruction. Find:
```python
        base_prompt = (
            "You are a senior UAE-qualified auditor. Generate a professional audit report in Markdown. "
```

Replace the first line inside the string:
```python
        base_prompt = (
            "You are a senior UAE-qualified auditor. Generate a professional audit report in Markdown. "
            "The financial data is pre-grouped into IFRS sections. "
            "Use the grouped totals to produce properly structured IFRS statements with subtotals and totals in bold. "
            "Prior year column: show 'N/A' if no prior year value is given. "
```

- [ ] **Step 4: Run tests**

```bash
cd backend
uv run pytest tests/test_audit_flow.py -v
```

Expected: `test_audit_draft_uses_grouped_structure` passes. Other tests pass or were passing before.

- [ ] **Step 5: Commit**

```bash
git add backend/core/agents/audit_agent.py
git commit -m "feat: use IFRS-grouped trial balance in audit draft generation"
```

---

## Task 6 — Fix analysis-chat SSE error

**Files:**
- Modify: `backend/api/reports.py`
- Modify: `frontend/src/components/studios/FinancialStudio/AuditAnalysisStep.tsx`

**Background:** The `/analysis-chat` endpoint streams raw text chunks (`data: Hello world`). The NVIDIA API crashes when the context (full TB + full draft) exceeds the token limit — this resets the TCP connection. The frontend's `reader.read()` throws and displays "Sorry, I encountered an error." Two fixes: (1) trim context before sending, (2) wrap chunks in JSON so errors can be communicated gracefully.

- [ ] **Step 1: Fix the backend `/analysis-chat` endpoint**

In `backend/api/reports.py`, find the `analysis_chat` function (around line 1905).

Find the `context_block` building section:
```python
    context_block = ""
    if req.trial_balance_summary:
        context_block += f"\n\n### Trial Balance Summary\n{req.trial_balance_summary}"
    if req.prior_year_context:
        context_block += f"\n\n### Prior Year Context\n{req.prior_year_context}"
    if req.draft_content:
        context_block += f"\n\n### Draft Report (excerpt)\n{req.draft_content[:1500]}"
```

Replace with:
```python
    # Trim context to avoid exceeding model token limit (prevents mid-stream TCP reset)
    tb_summary = (req.trial_balance_summary or "")[:2500]
    py_context = (req.prior_year_context or "")[:1000]
    draft_excerpt = (req.draft_content or "")[:2000]

    context_block = ""
    if tb_summary:
        context_block += f"\n\n### Trial Balance Summary\n{tb_summary}"
    if py_context:
        context_block += f"\n\n### Prior Year Context\n{py_context}"
    if draft_excerpt:
        context_block += f"\n\n### Draft Report (excerpt)\n{draft_excerpt}"
```

Then find the `generate()` inner function:
```python
    async def generate():
        try:
            llm = get_llm_provider()
            async for chunk in llm.chat_stream(messages):
                yield f"data: {chunk}\n\n"
        except Exception as e:
            logger.error(f"Analysis chat error: {e}")
            yield f"data: [ERROR] {e}\n\n"
```

Replace with:
```python
    async def generate():
        try:
            llm = get_llm_provider()
            async for chunk in llm.chat_stream(messages, temperature=0.3, max_tokens=2000):
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            logger.error(f"Analysis chat error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
```

Make sure `import json` is at the top of `reports.py` (it should already be there).

- [ ] **Step 2: Fix the frontend to parse JSON events**

In `frontend/src/components/studios/FinancialStudio/AuditAnalysisStep.tsx`, find the SSE reading loop (lines 86–103):

```typescript
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const chunk = line.slice(6);
          if (chunk === '[DONE]') break;
          setMessages(prev => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            updated[updated.length - 1] = { ...last, content: last.content + chunk };
            return updated;
          });
        }
```

Replace with:
```typescript
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;
          
          let event: { type: string; content?: string; message?: string };
          try {
            event = JSON.parse(raw);
          } catch {
            // Fallback: treat as raw text chunk (backward compat)
            setMessages(prev => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = { ...last, content: last.content + raw };
              return updated;
            });
            continue;
          }

          if (event.type === 'chunk' && event.content) {
            setMessages(prev => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = { ...last, content: last.content + event.content };
              return updated;
            });
          } else if (event.type === 'done') {
            break;
          } else if (event.type === 'error') {
            setMessages(prev => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                content: `Error: ${event.message || 'Unknown error'}. Please try again.`,
              };
              return updated;
            });
            break;
          }
        }
```

- [ ] **Step 3: Manual test**

Start the backend and frontend. Go through the audit wizard to step 7 (Analysis & Discussion). Ask "Tell me about 2024 and 2025 revenue." The assistant should respond without error. If the NVIDIA API key is not an OpenAI key, the streaming works the same way through the NVIDIA provider.

- [ ] **Step 4: Commit**

```bash
git add backend/api/reports.py frontend/src/components/studios/FinancialStudio/AuditAnalysisStep.tsx
git commit -m "fix: trim analysis-chat context to prevent token overflow and fix SSE JSON format"
```

---

## Task 7 — Apply template formatting_rules to DOCX output

**Files:**
- Modify: `backend/core/template_report_generator.py`
- Test: `backend/tests/test_template_report_generator.py`

**Background:** When template extraction now works (Tasks 1+2), `formatting_rules` contains real data: `currency_format`, `negative_number_format`, `heading_1_bold`. The DOCX generator must use these to match the prior year report's style. Also: fix table column widths to 60/20/20% so amounts align properly regardless of account name length.

- [ ] **Step 1: Write a failing test**

In `backend/tests/test_template_report_generator.py`, add:

```python
def test_formatting_rules_applied_to_docx():
    """When formatting_rules specify #,##0 (no decimals), generated DOCX amounts must have no decimal places."""
    import re
    from core.template_report_generator import generate_from_template

    template = {
        "document_structure": {"title": "Test", "date_range": "2024", "company_name": "Test Co", "auditor_name": "", "pages": 5, "sections": []},
        "account_grouping": {},
        "terminology": {"currency": "AED", "common_phrases": [], "headings_seen": []},
        "formatting_rules": {
            "table_formatting": {"currency_format": "#,##0", "negative_number_format": "(X,XXX)"},
            "font_hierarchy": {"heading_1_bold": True, "table_header_bold": True},
            "page_break_after_sections": [],
        },
    }

    current_data = {
        "company_name": "Test Co LLC",
        "location": "Dubai, UAE",
        "period_end": "31 December 2024",
        "opinion_type": "unqualified",
        "draft_content": "Draft report narrative here.",
        "rows": [
            {"account": "Cash", "mappedTo": "Current Assets", "amount": 50000.75},
        ],
    }

    docx_bytes = generate_from_template(current_data, template)
    assert isinstance(docx_bytes, bytes)
    assert len(docx_bytes) > 0

    # Open the DOCX and check that "50,000.75" does NOT appear — only "50,001" or "50,000"
    import io
    from docx import Document
    doc = Document(io.BytesIO(docx_bytes))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                full_text += cell.text + "\n"
    assert "50,000.75" not in full_text, "Decimal amount found when currency_format is #,##0"
```

- [ ] **Step 2: Run test to verify it fails (or identify current behavior)**

```bash
cd backend
uv run pytest tests/test_template_report_generator.py::test_formatting_rules_applied_to_docx -v
```

- [ ] **Step 3: Find where amounts are formatted in template_report_generator.py**

Search for where AED amounts are converted to strings:
```bash
grep -n "format\|:,.2f\|:,.0f\|currency" backend/core/template_report_generator.py | head -20
```

- [ ] **Step 4: Add a formatting helper and update amount rendering**

Near the top of `generate_from_template()` in `backend/core/template_report_generator.py` (after the docstring, before any table building), add:

```python
    # Determine amount format from template
    fmt_rules = (template or {}).get("formatting_rules", {})
    table_fmt = fmt_rules.get("table_formatting", {})
    currency_format = table_fmt.get("currency_format", "#,##0")
    negative_format = table_fmt.get("negative_number_format", "(X,XXX)")
    heading_bold = fmt_rules.get("font_hierarchy", {}).get("heading_1_bold", True)

    def fmt_amount(value: float) -> str:
        """Format a numeric amount according to the extracted template rules."""
        if currency_format == "#,##0.00":
            formatted = f"{abs(value):,.2f}"
        else:  # default: whole numbers (#,##0)
            formatted = f"{abs(value):,.0f}"
        if value < 0:
            if "(X,XXX)" in negative_format:
                return f"({formatted})"
            else:
                return f"-{formatted}"
        return formatted
```

Then find every place in the file where amounts are rendered as strings (e.g., `f"{amount:,.2f}"` or `f"{amount:,.0f}"`) and replace with `fmt_amount(amount)`.

Also find where table column widths are set and replace with fixed proportions. Search for `Inches` usage in table cells:
```bash
grep -n "Inches\|column_width\|col_width" backend/core/template_report_generator.py
```

For every financial statement table, set column widths:
```python
# Account name column: 60%, Current year: 20%, Prior year: 20%
# Page width ≈ 6.0 inches (A4 minus margins)
table.columns[0].width = Inches(3.6)   # 60%
table.columns[1].width = Inches(1.2)   # 20%
if len(table.columns) > 2:
    table.columns[2].width = Inches(1.2)  # 20%
```

- [ ] **Step 5: Run tests**

```bash
cd backend
uv run pytest tests/test_template_report_generator.py -v
```

Expected: new test passes, existing tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/core/template_report_generator.py backend/tests/test_template_report_generator.py
git commit -m "fix: apply template formatting_rules (currency format, column widths) to DOCX output"
```

---

## Final Check — Run Full Test Suite

- [ ] **Run all backend tests**

```bash
cd backend
uv run pytest tests/ -v --tb=short
```

All tests should pass. Any failures introduced by this plan should be fixed before moving to Plan B.

- [ ] **Manual smoke test of full audit wizard**

1. Start backend: `cd backend && uv run python main.py`
2. Start frontend: `cd frontend && npm run dev`
3. Go to Financial Studio → Audit Report
4. Upload a trial balance Excel file
5. Upload a **scanned** prior year PDF as company document
6. Proceed through all steps — verify:
   - Step 2: Template confidence > 0%, pages shows real number
   - Step 3: "Could not extract" message gone
   - Step 6: Draft shows grouped IFRS structure (Total Current Assets, etc.), opinion is Unqualified
   - Step 7: Ask a question — no "Sorry, I encountered an error"
   - Step 9: Final DOCX formatting matches prior year style
