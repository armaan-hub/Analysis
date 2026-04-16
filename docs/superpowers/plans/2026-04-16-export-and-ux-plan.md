# Export & UX Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Word/PDF/Excel download buttons to every chat response and add icon action bar (copy, download) matching the style shown in reference images.

**Architecture:** A new backend endpoint `POST /api/chat/export` converts stored message markdown to Word (python-docx), PDF (weasyprint), or Excel (openpyxl). A new `ChatMessageActions` React component renders icon buttons below each assistant message.

**Tech Stack:** Python/FastAPI, python-docx (already installed), weasyprint (needs pip install), openpyxl, markdown, React/TypeScript.

**Prerequisite:** Plans A and B do not need to be complete before starting this plan — it's fully independent.

---

## File Map

| File | What changes |
|------|-------------|
| `backend/api/chat.py` | Add `POST /api/chat/export` endpoint |
| `backend/core/export_converter.py` | New file: markdown → Word/PDF/Excel conversion logic |
| `frontend/src/components/ChatMessageActions.tsx` | New file: Copy/Word/PDF/Excel icon buttons |
| `frontend/src/components/studios/LegalStudio/ChatMessages.tsx` | Mount `ChatMessageActions` below each assistant message |
| `frontend/src/lib/api.ts` | Add `exportMessage(messageId, format)` API call |

---

## Task 1 — Install weasyprint and verify dependencies

**Files:** None (environment setup)

- [ ] **Step 1: Check which packages are already installed**

```bash
cd backend
uv run python -c "import docx; print('python-docx OK')"
uv run python -c "import openpyxl; print('openpyxl OK')"
uv run python -c "import markdown; print('markdown OK')"
uv run python -c "import weasyprint; print('weasyprint OK')"
```

Note which ones fail.

- [ ] **Step 2: Install missing packages**

For each that failed, install:
```bash
# If openpyxl missing:
uv add openpyxl

# If markdown missing:
uv add markdown

# If weasyprint missing:
uv add weasyprint
```

weasyprint has system dependencies (Cairo, Pango). On Windows, install GTK3 runtime from:
https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases

If GTK3 install is complex, use `reportlab` as the PDF alternative:
```bash
uv add reportlab
```

- [ ] **Step 3: Verify after install**

```bash
cd backend
uv run python -c "import weasyprint; print('weasyprint OK')"
# OR
uv run python -c "import reportlab; print('reportlab OK')"
```

- [ ] **Step 4: Update requirements.txt or pyproject.toml**

If using `uv`, the `pyproject.toml` is updated automatically. If a separate `requirements.txt` exists:
```bash
cd backend
uv run pip freeze | grep -E "weasyprint|reportlab|openpyxl|Markdown" >> requirements.txt
```

---

## Task 2 — Create export_converter.py

**Files:**
- Create: `backend/core/export_converter.py`
- Test: `backend/tests/test_export.py` (new file)

- [ ] **Step 1: Create the test file first**

Create `backend/tests/test_export.py`:

```python
"""Tests for markdown → Word/PDF/Excel conversion."""
import pytest
from core.export_converter import to_word, to_pdf, to_excel


SAMPLE_MARKDOWN = """# UAE VAT Summary

This document covers the key points of UAE VAT regulations.

## Key Rates

| Supply Type | Rate |
|-------------|------|
| Standard | 5% |
| Zero-rated | 0% |
| Exempt | N/A |

## Filing Deadlines

Quarterly filers must submit by the **28th day** after the quarter ends.

- Q1: April 28
- Q2: July 28
- Q3: October 28
- Q4: January 28
"""


def test_to_word_returns_bytes():
    result = to_word(SAMPLE_MARKDOWN)
    assert isinstance(result, bytes)
    assert len(result) > 100  # Non-empty DOCX
    # DOCX files start with PK (ZIP magic bytes)
    assert result[:2] == b'PK'


def test_to_word_contains_heading():
    """The generated DOCX must contain the heading text."""
    import io
    from docx import Document
    result = to_word(SAMPLE_MARKDOWN)
    doc = Document(io.BytesIO(result))
    all_text = "\n".join(p.text for p in doc.paragraphs)
    assert "UAE VAT Summary" in all_text
    assert "Key Rates" in all_text


def test_to_excel_returns_bytes_when_table_present():
    result = to_excel(SAMPLE_MARKDOWN)
    assert isinstance(result, bytes)
    assert len(result) > 100
    # XLSX files also start with PK
    assert result[:2] == b'PK'


def test_to_excel_returns_empty_bytes_when_no_table():
    no_table_md = "# Title\n\nJust some text with no table here."
    result = to_excel(no_table_md)
    assert result == b""  # No tables = empty bytes = disable the button


def test_to_pdf_returns_bytes():
    result = to_pdf(SAMPLE_MARKDOWN)
    assert isinstance(result, bytes)
    assert len(result) > 100
    # PDF files start with %PDF
    assert result[:4] == b'%PDF'
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
uv run pytest tests/test_export.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.export_converter'`

- [ ] **Step 3: Create export_converter.py**

Create `backend/core/export_converter.py`:

```python
"""
Export Converter — converts markdown text to Word, PDF, or Excel.
Used by the chat export endpoint to let users download LLM responses.
"""
from __future__ import annotations

import io
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


# ── Markdown parsing helpers ──────────────────────────────────────────────────

def _parse_markdown_tables(text: str) -> list[list[list[str]]]:
    """
    Extract all markdown tables from text.
    Returns a list of tables; each table is a list of rows; each row is a list of cells.
    The first row is always the header.
    """
    tables = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Table header line: starts and ends with |, has multiple |
        if line.startswith("|") and line.count("|") >= 2:
            header_cells = [c.strip() for c in line.split("|") if c.strip()]
            # Next line should be separator: |---|---|
            if i + 1 < len(lines) and re.match(r"^\|[\s\-\|:]+\|$", lines[i + 1].strip()):
                rows = [header_cells]
                j = i + 2
                while j < len(lines):
                    row_line = lines[j].strip()
                    if not row_line.startswith("|"):
                        break
                    row_cells = [c.strip() for c in row_line.split("|") if c.strip()]
                    if row_cells:
                        rows.append(row_cells)
                    j += 1
                if len(rows) > 1:
                    tables.append(rows)
                i = j
                continue
        i += 1
    return tables


def _strip_markdown_for_plain(text: str) -> str:
    """Remove markdown syntax leaving plain text."""
    # Remove code fences
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Remove inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Remove bold/italic
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    return text


# ── Word export ───────────────────────────────────────────────────────────────

def to_word(markdown_text: str) -> bytes:
    """Convert markdown text to a Word DOCX file. Returns bytes."""
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    # Set default font
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(11)

    lines = markdown_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]

        # Heading 1
        if line.startswith("# ") and not line.startswith("## "):
            p = doc.add_heading(line[2:].strip(), level=1)
            i += 1
            continue

        # Heading 2
        if line.startswith("## ") and not line.startswith("### "):
            p = doc.add_heading(line[3:].strip(), level=2)
            i += 1
            continue

        # Heading 3
        if line.startswith("### "):
            p = doc.add_heading(line[4:].strip(), level=3)
            i += 1
            continue

        # Table: detect header row
        stripped = line.strip()
        if stripped.startswith("|") and stripped.count("|") >= 2:
            if i + 1 < len(lines) and re.match(r"^\|[\s\-\|:]+\|$", lines[i + 1].strip()):
                # Collect all table rows
                header_cells = [c.strip() for c in stripped.split("|") if c.strip()]
                table_rows = [header_cells]
                j = i + 2
                while j < len(lines):
                    r_line = lines[j].strip()
                    if not r_line.startswith("|"):
                        break
                    row_cells = [c.strip() for c in r_line.split("|") if c.strip()]
                    if row_cells:
                        table_rows.append(row_cells)
                    j += 1

                max_cols = max(len(r) for r in table_rows)
                table = doc.add_table(rows=len(table_rows), cols=max_cols)
                table.style = "Table Grid"

                for r_idx, row in enumerate(table_rows):
                    for c_idx, cell_text in enumerate(row):
                        if c_idx < max_cols:
                            cell = table.rows[r_idx].cells[c_idx]
                            cell.text = cell_text
                            if r_idx == 0:
                                # Bold header
                                for paragraph in cell.paragraphs:
                                    for run in paragraph.runs:
                                        run.bold = True

                doc.add_paragraph()  # Space after table
                i = j
                continue

        # Bullet point
        if stripped.startswith("- ") or stripped.startswith("* "):
            p = doc.add_paragraph(stripped[2:], style="List Bullet")
            i += 1
            continue

        # Numbered list
        if re.match(r"^\d+\.\s", stripped):
            p = doc.add_paragraph(re.sub(r"^\d+\.\s", "", stripped), style="List Number")
            i += 1
            continue

        # Blank line → paragraph break
        if not stripped:
            i += 1
            continue

        # Normal paragraph — handle inline bold
        p = doc.add_paragraph()
        parts = re.split(r"(\*\*[^*]+\*\*)", stripped)
        for part in parts:
            if part.startswith("**") and part.endswith("**"):
                run = p.add_run(part[2:-2])
                run.bold = True
            else:
                p.add_run(part)

        i += 1

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ── PDF export ────────────────────────────────────────────────────────────────

def to_pdf(markdown_text: str) -> bytes:
    """Convert markdown text to PDF. Returns bytes."""
    # Try weasyprint first, fall back to reportlab
    try:
        return _to_pdf_weasyprint(markdown_text)
    except Exception as exc:
        logger.warning(f"weasyprint PDF failed ({exc}), trying reportlab")
        try:
            return _to_pdf_reportlab(markdown_text)
        except Exception as exc2:
            logger.error(f"Both PDF methods failed: {exc2}")
            raise RuntimeError("PDF export unavailable — install weasyprint or reportlab") from exc2


def _to_pdf_weasyprint(markdown_text: str) -> bytes:
    import markdown as md_lib
    from weasyprint import HTML, CSS

    html_body = md_lib.markdown(markdown_text, extensions=["tables", "fenced_code"])
    css = CSS(string="""
        @page { size: A4; margin: 2cm; }
        body { font-family: "Times New Roman", Times, serif; font-size: 11pt; line-height: 1.6; }
        h1 { font-size: 16pt; margin-top: 20pt; }
        h2 { font-size: 13pt; margin-top: 14pt; }
        h3 { font-size: 11pt; margin-top: 10pt; }
        table { border-collapse: collapse; width: 100%; margin: 10pt 0; }
        th, td { border: 1px solid #ccc; padding: 6pt 8pt; text-align: left; }
        th { background: #f0f0f0; font-weight: bold; }
    """)
    full_html = f"<html><body>{html_body}</body></html>"
    return HTML(string=full_html).write_pdf(stylesheets=[css])


def _to_pdf_reportlab(markdown_text: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors

    buf = io.BytesIO()
    doc_rl = SimpleDocTemplate(buf, pagesize=A4,
                                rightMargin=72, leftMargin=72,
                                topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    story = []

    for line in markdown_text.split("\n"):
        stripped = line.strip()
        if not stripped:
            story.append(Spacer(1, 6))
            continue
        if stripped.startswith("# "):
            story.append(Paragraph(stripped[2:], styles["Heading1"]))
        elif stripped.startswith("## "):
            story.append(Paragraph(stripped[3:], styles["Heading2"]))
        elif stripped.startswith("### "):
            story.append(Paragraph(stripped[4:], styles["Heading3"]))
        elif stripped.startswith("- ") or stripped.startswith("* "):
            story.append(Paragraph(f"• {stripped[2:]}", styles["Normal"]))
        else:
            clean = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", stripped)
            story.append(Paragraph(clean, styles["Normal"]))

    doc_rl.build(story)
    return buf.getvalue()


# ── Excel export ──────────────────────────────────────────────────────────────

def to_excel(markdown_text: str) -> bytes:
    """
    Convert markdown tables to Excel worksheets.
    Returns empty bytes if no tables found (caller should disable the button).
    """
    tables = _parse_markdown_tables(markdown_text)
    if not tables:
        return b""

    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # Remove default empty sheet

    # Find headings above each table to use as sheet names
    lines = markdown_text.split("\n")
    table_line_indices = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("|") and stripped.count("|") >= 2:
            if i + 1 < len(lines) and re.match(r"^\|[\s\-\|:]+\|$", lines[i + 1].strip()):
                table_line_indices.append(i)

    for t_idx, table_rows in enumerate(tables):
        # Find nearest heading above this table
        sheet_name = f"Table {t_idx + 1}"
        if t_idx < len(table_line_indices):
            tli = table_line_indices[t_idx]
            for li in range(tli - 1, max(tli - 10, -1), -1):
                if lines[li].strip().startswith("#"):
                    sheet_name = re.sub(r"^#+\s*", "", lines[li].strip())[:31]
                    break

        ws = wb.create_sheet(title=sheet_name)

        header_fill = PatternFill("solid", fgColor="E0E7FF")
        header_font = Font(bold=True)

        for r_idx, row in enumerate(table_rows):
            for c_idx, cell_value in enumerate(row):
                cell = ws.cell(row=r_idx + 1, column=c_idx + 1, value=cell_value)
                if r_idx == 0:
                    cell.font = header_font
                    cell.fill = header_fill
                cell.alignment = Alignment(wrap_text=True)

                # Try to detect numeric cells (not header) and format them
                if r_idx > 0:
                    try:
                        numeric = float(cell_value.replace(",", "").replace("%", ""))
                        cell.value = numeric
                        if "%" in cell_value:
                            cell.number_format = "0.00%"
                        else:
                            cell.number_format = "#,##0.00"
                    except (ValueError, AttributeError):
                        pass

        # Auto-fit column widths
        for col in ws.columns:
            max_len = max(
                (len(str(c.value)) for c in col if c.value is not None),
                default=10,
            )
            ws.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 4, 40)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
```

- [ ] **Step 4: Run the tests**

```bash
cd backend
uv run pytest tests/test_export.py -v
```

Expected: all 5 tests pass. If `to_pdf` fails due to missing system libraries, it's OK — the test will guide you to install the right package.

- [ ] **Step 5: Commit**

```bash
git add backend/core/export_converter.py backend/tests/test_export.py
git commit -m "feat: add export_converter.py for markdown → Word/PDF/Excel conversion"
```

---

## Task 3 — Add /api/chat/export endpoint

**Files:**
- Modify: `backend/api/chat.py`

- [ ] **Step 1: Add export request schema and endpoint**

In `backend/api/chat.py`, add to the schemas section (near the other Pydantic models):

```python
class ExportRequest(BaseModel):
    message_id: str
    format: str  # "word" | "pdf" | "excel"
```

Then add the endpoint after the existing routes (before or after the `delete_conversation` route):

```python
@router.post("/export")
async def export_message(req: ExportRequest, db: AsyncSession = Depends(get_db)):
    """Export a chat message as Word, PDF, or Excel file."""
    from core.export_converter import to_word, to_pdf, to_excel
    from fastapi.responses import Response

    # Fetch the message
    result = await db.execute(
        select(Message).where(Message.id == req.message_id)
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    content = message.content or ""

    if req.format == "word":
        file_bytes = to_word(content)
        return Response(
            content=file_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": "attachment; filename=response.docx"},
        )
    elif req.format == "pdf":
        file_bytes = to_pdf(content)
        return Response(
            content=file_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=response.pdf"},
        )
    elif req.format == "excel":
        file_bytes = to_excel(content)
        if not file_bytes:
            raise HTTPException(
                status_code=400,
                detail="No tables found in this message. Excel export requires a table.",
            )
        return Response(
            content=file_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=response.xlsx"},
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown format: {req.format}")
```

- [ ] **Step 2: Test the endpoint manually**

Start the backend and test with curl (use a real message_id from your DB):
```bash
# Get a conversation to find a message_id
curl http://localhost:8000/api/chat/conversations | python -m json.tool

# Use a message_id from the response
curl -X POST http://localhost:8000/api/chat/export \
  -H "Content-Type: application/json" \
  -d '{"message_id": "YOUR_MESSAGE_ID_HERE", "format": "word"}' \
  --output test_export.docx

# Verify file was created
ls -la test_export.docx
```

- [ ] **Step 3: Commit**

```bash
git add backend/api/chat.py
git commit -m "feat: add POST /api/chat/export endpoint for Word/PDF/Excel download"
```

---

## Task 4 — Add ChatMessageActions component (Frontend)

**Files:**
- Create: `frontend/src/components/ChatMessageActions.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/studios/LegalStudio/ChatMessages.tsx`

- [ ] **Step 1: Add exportMessage to api.ts**

Open `frontend/src/lib/api.ts`. Add this function at the bottom:

```typescript
export async function exportMessage(
  messageId: string,
  format: 'word' | 'pdf' | 'excel',
  filename: string
): Promise<void> {
  const response = await fetch('/api/chat/export', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message_id: messageId, format }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Export failed' }));
    throw new Error(error.detail || 'Export failed');
  }

  // Trigger browser download
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
```

- [ ] **Step 2: Create ChatMessageActions.tsx**

Create `frontend/src/components/ChatMessageActions.tsx`:

```tsx
import React, { useState } from 'react';
import { exportMessage } from '../lib/api';

interface ChatMessageActionsProps {
  messageId: string;
  content: string;
  hasTable?: boolean;
}

export function ChatMessageActions({ messageId, content, hasTable = false }: ChatMessageActionsProps) {
  const [copied, setCopied] = useState(false);
  const [exporting, setExporting] = useState<string | null>(null);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for browsers that block clipboard
      const textarea = document.createElement('textarea');
      textarea.value = content;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleExport = async (format: 'word' | 'pdf' | 'excel') => {
    const extensions = { word: 'docx', pdf: 'pdf', excel: 'xlsx' };
    setExporting(format);
    try {
      await exportMessage(messageId, format, `response.${extensions[format]}`);
    } catch (err) {
      console.error(`Export failed: ${err}`);
    } finally {
      setExporting(null);
    }
  };

  const btnClass =
    'flex items-center justify-center w-7 h-7 rounded text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors disabled:opacity-40 disabled:cursor-not-allowed';

  return (
    <div className="flex items-center gap-1 mt-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
      {/* Copy */}
      <button
        title={copied ? 'Copied!' : 'Copy to clipboard'}
        onClick={handleCopy}
        className={btnClass}
      >
        {copied ? (
          <svg className="w-3.5 h-3.5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        ) : (
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
          </svg>
        )}
      </button>

      {/* Download Word */}
      <button
        title="Download as Word (.docx)"
        onClick={() => handleExport('word')}
        disabled={exporting === 'word'}
        className={btnClass}
      >
        {exporting === 'word' ? (
          <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
          </svg>
        ) : (
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        )}
      </button>

      {/* Download PDF */}
      <button
        title="Download as PDF"
        onClick={() => handleExport('pdf')}
        disabled={exporting === 'pdf'}
        className={btnClass}
      >
        {exporting === 'pdf' ? (
          <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
          </svg>
        ) : (
          <span className="text-[10px] font-bold leading-none">PDF</span>
        )}
      </button>

      {/* Download Excel — disabled when no table */}
      <button
        title={hasTable ? 'Download as Excel (.xlsx)' : 'No table in this response'}
        onClick={() => hasTable && handleExport('excel')}
        disabled={!hasTable || exporting === 'excel'}
        className={btnClass}
      >
        {exporting === 'excel' ? (
          <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
          </svg>
        ) : (
          <span className="text-[10px] font-bold leading-none">XLS</span>
        )}
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Mount ChatMessageActions in ChatMessages.tsx**

Open `frontend/src/components/studios/LegalStudio/ChatMessages.tsx`.

Add the import at the top:
```tsx
import { ChatMessageActions } from '../../ChatMessageActions';
```

Find where each assistant message is rendered (the map over messages). Wrap the message container in a `group` class div (for the hover-to-show effect) and add `ChatMessageActions` after the message content:

```tsx
{/* Wrap each assistant message in a group div */}
<div key={msg.id} className="group">
  {/* ... existing message bubble rendering ... */}

  {msg.role === 'assistant' && msg.id && (
    <ChatMessageActions
      messageId={msg.id}
      content={msg.content}
      hasTable={msg.content.includes('|---|') || msg.content.includes('| ---')}
    />
  )}
</div>
```

The `hasTable` check uses a simple heuristic: if the markdown content contains a separator row (`|---|`), it has a table.

- [ ] **Step 4: Test in browser**

1. Start backend and frontend.
2. Ask the chatbot any question that produces a table (e.g., "compare UAE VAT rates for standard, zero-rated, and exempt supplies in a table").
3. Hover over the assistant message — the action bar should appear.
4. Click the Copy button — verify content is copied.
5. Click the Word button — verify a `.docx` file downloads.
6. Click the Excel button — verify it's enabled (message has a table) and downloads `.xlsx`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ChatMessageActions.tsx frontend/src/lib/api.ts frontend/src/components/studios/LegalStudio/ChatMessages.tsx
git commit -m "feat: add copy/download action bar (Word/PDF/Excel) to chat messages"
```

---

## Final Verification

- [ ] **Run full backend test suite**

```bash
cd backend
uv run pytest tests/ -v --tb=short
```

All tests pass.

- [ ] **Manual end-to-end test of export**

1. Ask the chatbot a question about UAE IFRS financial reporting that includes tables.
2. Hover over the response — action bar appears.
3. Download Word → open in Microsoft Word → verify formatting looks professional.
4. Download PDF → verify A4 layout with proper headings and tables.
5. Download Excel → open in Excel → verify each table is on its own worksheet with formatted numbers.

- [ ] **Final commit tag**

```bash
git tag export-feature-complete
```
