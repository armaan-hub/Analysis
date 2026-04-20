# Bug Fix Bundle — April 20 2026 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 7 bugs + enhancements across 5 surfaces: Deep Research, Analyst Mode, Audit Flow, Financial Reports, and Notebook List.

**Architecture:** Frontend is React+Vite+TS in `frontend/src/`. Backend is Python FastAPI in `backend/`. Chat uses SSE streaming via `fetch()` + ReadableStream. Notebooks are conversations stored in SQLite via SQLAlchemy. All styling is glassmorphism dark theme using CSS variables (`--s-text-1`, `--s-accent`, etc.).

**Tech Stack:** React 18, TypeScript, Vite, react-markdown, react-router-dom, Axios, FastAPI, SQLAlchemy (async), openpyxl, python-docx, WeasyPrint/ReportLab, pandas

---

## File Map

### Frontend Files (Create / Modify)

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `frontend/src/components/studios/LegalStudio/SourcesChip.tsx` | Deduped sources chip: "Sources (N files, M citations)" + expandable panel |
| Create | `frontend/src/components/studios/LegalStudio/InlineResultCard.tsx` | Shared inline card for audit + financial report results in chat |
| Create | `frontend/src/components/studios/LegalStudio/QuestionnaireMessage.tsx` | Chat-redirect questionnaire: AI pre-fills, user confirms, generate button |
| Create | `frontend/src/components/studios/LegalStudio/CustomTemplatePicker.tsx` | Modal to pick user's saved templates from Template Learning Studio |
| Modify | `frontend/src/components/studios/LegalStudio/ResearchBubble.tsx` | Add sources chip + export buttons (PDF/Word/Excel) |
| Modify | `frontend/src/components/studios/LegalStudio/ChatMessages.tsx` | Replace raw source count with `SourcesChip`, render `InlineResultCard` and `QuestionnaireMessage` |
| Modify | `frontend/src/components/studios/LegalStudio/AuditorFormatGrid.tsx` | Add 5th "Custom Template" option |
| Modify | `frontend/src/components/studios/LegalStudio/AuditorResultBubble.tsx` | Add export buttons (PDF/Word/Excel) to audit result |
| Modify | `frontend/src/components/studios/LegalStudio/DomainChip.tsx` | Add Audit, Finance, General domains + lock icon for manual override |
| Modify | `frontend/src/components/studios/LegalStudio/LegalStudio.tsx` | Wire questionnaire flow for audit + financial reports, persist sources to DB, error handling |
| Modify | `frontend/src/components/studios/LegalStudio/StudioPanel.tsx` | Report buttons → chat questionnaire redirect instead of direct generation |
| Modify | `frontend/src/components/studios/LegalStudio/StudioCards.tsx` | Add all 11 financial report types |
| Modify | `frontend/src/components/common/NotebookCard.tsx` | Gradient thumbnail, delete button with hover |
| Modify | `frontend/src/pages/HomePage.tsx` | Search, grid/list toggle, Create New first, delete with confirm |
| Modify | `frontend/src/lib/api.ts` | Add `exportDeepResearch()`, `exportInlineReport()` API helpers |

### Backend Files (Create / Modify)

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `backend/core/deep_research_export.py` | Generate branded PDF/DOCX/XLSX from deep research content+sources |
| Create | `backend/core/documents/xlsx_injector.py` | Parse xlsx/csv < 100KB → structured text for LLM context injection |
| Modify | `backend/api/chat.py` | Add `POST /api/chat/export-deep-research` endpoint |
| Modify | `backend/api/documents.py` | On upload of xlsx/csv < 100KB, store `structured_text` in document metadata |
| Modify | `backend/api/legal_studio.py` | Add notebook delete, audit error handling, source persist endpoints |
| Modify | `backend/core/export_converter.py` | Add branded cover page + TOC + sources appendix to PDF/DOCX |
| Modify | `backend/db/models.py` | Add `checked_source_ids` to Conversation, add `structured_text` to Document metadata |

---

## Phase 1: Deep Research — Full Answer + Sources + Export

### Task 1: Backend — Deep Research Export Endpoint

**Files:**
- Create: `backend/core/deep_research_export.py`
- Modify: `backend/api/chat.py`

- [ ] **Step 1: Create `deep_research_export.py`**

```python
# backend/core/deep_research_export.py
"""Generate branded exports from Deep Research content + sources."""
from __future__ import annotations

import io
import logging
import re
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def _parse_markdown_tables(text: str) -> list[list[list[str]]]:
    """Extract markdown tables as list of rows of cells."""
    tables = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("|") and line.count("|") >= 2:
            header_cells = [c.strip() for c in line.split("|") if c.strip()]
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


def to_branded_pdf(content: str, sources: list[dict], query: str = "") -> bytes:
    """Convert deep research markdown + sources to branded PDF with cover page, TOC, body, sources appendix."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.enums import TA_CENTER

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm,
                            leftMargin=2.5*cm, rightMargin=2.5*cm)
    styles = getSampleStyleSheet()
    story = []

    # -- Cover Page --
    story.append(Spacer(1, 6*cm))
    cover_title = ParagraphStyle('CoverTitle', parent=styles['Title'], fontSize=24,
                                  textColor=HexColor('#1a1a2e'), alignment=TA_CENTER)
    story.append(Paragraph(query or "Deep Research Report", cover_title))
    story.append(Spacer(1, 1*cm))
    cover_sub = ParagraphStyle('CoverSub', parent=styles['Normal'], fontSize=12,
                                textColor=HexColor('#666'), alignment=TA_CENTER)
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y')}", cover_sub))
    story.append(Paragraph("Deep Research Report", cover_sub))
    story.append(PageBreak())

    # -- Body --
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("### "):
            story.append(Paragraph(stripped[4:], styles['Heading3']))
        elif stripped.startswith("## "):
            story.append(Paragraph(stripped[3:], styles['Heading2']))
        elif stripped.startswith("# "):
            story.append(Paragraph(stripped[2:], styles['Heading1']))
        elif stripped.startswith("---"):
            story.append(Spacer(1, 0.3*cm))
        elif stripped:
            # Bold handling
            text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', stripped)
            story.append(Paragraph(text, styles['Normal']))
        else:
            story.append(Spacer(1, 0.2*cm))

    # -- Sources Appendix --
    if sources:
        story.append(PageBreak())
        story.append(Paragraph("Sources", styles['Heading1']))
        story.append(Spacer(1, 0.5*cm))
        for i, src in enumerate(sources, 1):
            filename = src.get("source", src.get("source_file", f"Source {i}"))
            excerpt = src.get("excerpt", src.get("passage", ""))
            story.append(Paragraph(f"<b>{i}. {filename}</b>", styles['Normal']))
            if excerpt:
                story.append(Paragraph(f"<i>{excerpt[:300]}</i>", styles['Normal']))
            story.append(Spacer(1, 0.3*cm))

    doc.build(story)
    return buf.getvalue()


def to_branded_docx(content: str, sources: list[dict], query: str = "") -> bytes:
    """Convert deep research markdown + sources to branded DOCX."""
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    # -- Cover Page --
    for _ in range(6):
        doc.add_paragraph("")
    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_para.add_run(query or "Deep Research Report")
    run.font.size = Pt(24)
    run.bold = True

    date_para = doc.add_paragraph()
    date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = date_para.add_run(f"Generated: {datetime.now().strftime('%B %d, %Y')}")
    run.font.size = Pt(12)
    run.font.color.rgb = RGBColor(102, 102, 102)

    label_para = doc.add_paragraph()
    label_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = label_para.add_run("Deep Research Report")
    run.font.size = Pt(12)
    run.font.color.rgb = RGBColor(102, 102, 102)

    doc.add_page_break()

    # -- Body --
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("### "):
            doc.add_heading(stripped[4:], level=3)
        elif stripped.startswith("## "):
            doc.add_heading(stripped[3:], level=2)
        elif stripped.startswith("# "):
            doc.add_heading(stripped[2:], level=1)
        elif stripped.startswith("|") and stripped.count("|") >= 2:
            # Skip table separator rows
            if re.match(r"^\|[\s\-\|:]+\|$", stripped):
                continue
            cells = [c.strip() for c in stripped.split("|") if c.strip()]
            if cells:
                para = doc.add_paragraph()
                para.add_run("  |  ".join(cells)).font.size = Pt(10)
        elif stripped:
            doc.add_paragraph(stripped)

    # -- Sources Appendix --
    if sources:
        doc.add_page_break()
        doc.add_heading("Sources", level=1)
        for i, src in enumerate(sources, 1):
            filename = src.get("source", src.get("source_file", f"Source {i}"))
            excerpt = src.get("excerpt", src.get("passage", ""))
            para = doc.add_paragraph()
            run = para.add_run(f"{i}. {filename}")
            run.bold = True
            if excerpt:
                doc.add_paragraph(excerpt[:300]).style = doc.styles["Normal"]

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def to_branded_xlsx(content: str, sources: list[dict], query: str = "") -> bytes:
    """Convert deep research content to XLSX. Tables → separate sheets. Sources → final sheet."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    header_font = Font(bold=True, size=11)
    header_fill = PatternFill(start_color="1a1a2e", end_color="1a1a2e", fill_type="solid")
    header_font_white = Font(bold=True, size=11, color="FFFFFF")

    tables = _parse_markdown_tables(content)

    if tables:
        # Remove default sheet, create one per table
        wb.remove(wb.active)
        for idx, table_data in enumerate(tables):
            ws = wb.create_sheet(title=f"Table {idx + 1}")
            for row_idx, row in enumerate(table_data):
                for col_idx, cell_val in enumerate(row):
                    cell = ws.cell(row=row_idx + 1, column=col_idx + 1, value=cell_val)
                    if row_idx == 0:
                        cell.font = header_font_white
                        cell.fill = header_fill
            # Auto-width
            for col in ws.columns:
                max_len = max((len(str(cell.value or "")) for cell in col), default=10)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)
    else:
        # No tables: full text in column A
        ws = wb.active
        ws.title = "Report"
        ws.cell(row=1, column=1, value="Deep Research Report").font = header_font
        ws.cell(row=2, column=1, value=f"Query: {query}")
        ws.cell(row=3, column=1, value=f"Date: {datetime.now().strftime('%Y-%m-%d')}")
        for i, line in enumerate(content.split("\n"), start=5):
            ws.cell(row=i, column=1, value=line)
        ws.column_dimensions["A"].width = 100

    # Sources sheet
    if sources:
        ws_src = wb.create_sheet(title="Sources")
        ws_src.cell(row=1, column=1, value="Source File").font = header_font_white
        ws_src.cell(row=1, column=1).fill = header_fill
        ws_src.cell(row=1, column=2, value="Excerpt").font = header_font_white
        ws_src.cell(row=1, column=2).fill = header_fill
        for i, src in enumerate(sources, start=2):
            ws_src.cell(row=i, column=1, value=src.get("source", src.get("source_file", "")))
            ws_src.cell(row=i, column=2, value=src.get("excerpt", src.get("passage", ""))[:500])
        ws_src.column_dimensions["A"].width = 40
        ws_src.column_dimensions["B"].width = 80

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
```

- [ ] **Step 2: Add export endpoint to `backend/api/chat.py`**

At the end of the file (before the closing), add:

```python
# --- Deep Research Export ---

class DeepResearchExportRequest(BaseModel):
    content: str
    sources: list[dict] = []
    format: Literal["pdf", "docx", "xlsx"] = "pdf"
    query: str = ""

@router.post("/export-deep-research")
async def export_deep_research(req: DeepResearchExportRequest):
    """Export deep research results as branded PDF/DOCX/XLSX."""
    from core.deep_research_export import to_branded_pdf, to_branded_docx, to_branded_xlsx

    if req.format == "pdf":
        data = to_branded_pdf(req.content, req.sources, req.query)
        media_type = "application/pdf"
        filename = f"DeepResearch-{datetime.now().strftime('%Y-%m-%d')}.pdf"
    elif req.format == "docx":
        data = to_branded_docx(req.content, req.sources, req.query)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"DeepResearch-{datetime.now().strftime('%Y-%m-%d')}.docx"
    else:
        data = to_branded_xlsx(req.content, req.sources, req.query)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"DeepResearch-{datetime.now().strftime('%Y-%m-%d')}.xlsx"

    return StreamingResponse(
        io.BytesIO(data),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

Also add `import io` at the top if not already present (it is not — add it next to the existing imports).

- [ ] **Step 3: Run backend to verify no import errors**

Run: `cd backend && python -c "from core.deep_research_export import to_branded_pdf, to_branded_docx, to_branded_xlsx; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/core/deep_research_export.py backend/api/chat.py
git commit -m "feat(backend): add deep research branded export endpoint (PDF/DOCX/XLSX)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Frontend — Sources Chip Component

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/SourcesChip.tsx`

- [ ] **Step 1: Create SourcesChip component**

```tsx
// frontend/src/components/studios/LegalStudio/SourcesChip.tsx
import { useState } from 'react';
import type { Source } from '../../../lib/api';

interface Props {
  sources: Source[];
  onSourceClick: (source: Source) => void;
}

export function SourcesChip({ sources, onSourceClick }: Props) {
  const [expanded, setExpanded] = useState(false);

  if (!sources || sources.length === 0) return null;

  // Deduplicate by source file for file count
  const uniqueFiles = new Map<string, Source[]>();
  for (const src of sources) {
    const key = src.source || 'unknown';
    if (!uniqueFiles.has(key)) uniqueFiles.set(key, []);
    uniqueFiles.get(key)!.push(src);
  }
  const fileCount = uniqueFiles.size;
  const citationCount = sources.length;

  return (
    <div style={{ marginTop: 6 }}>
      <button
        type="button"
        onClick={() => setExpanded(e => !e)}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
          padding: '4px 10px',
          borderRadius: 12,
          fontSize: 11,
          fontWeight: 500,
          background: 'rgba(59,130,246,0.08)',
          color: 'var(--s-accent, #3b82f6)',
          border: '1px solid rgba(59,130,246,0.2)',
          cursor: 'pointer',
          transition: 'background 0.15s',
        }}
      >
        🔗 Sources ({fileCount} {fileCount === 1 ? 'file' : 'files'}, {citationCount} {citationCount === 1 ? 'citation' : 'citations'})
        {expanded ? ' ▲' : ' ▸'}
      </button>

      {expanded && (
        <div style={{
          marginTop: 6,
          padding: 8,
          borderRadius: 'var(--s-r-sm, 8px)',
          background: 'rgba(255,255,255,0.03)',
          border: '1px solid var(--s-border, rgba(255,255,255,0.08))',
          maxHeight: 240,
          overflowY: 'auto',
        }}>
          {Array.from(uniqueFiles.entries()).map(([filename, citations]) => (
            <div key={filename} style={{ marginBottom: 8 }}>
              <button
                type="button"
                onClick={() => onSourceClick(citations[0])}
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: 'var(--s-text-1)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 0,
                  textDecoration: 'underline',
                  textDecorationColor: 'rgba(59,130,246,0.3)',
                }}
              >
                📄 {filename}
              </button>
              <div style={{ paddingLeft: 16, marginTop: 2 }}>
                {citations.map((c, i) => (
                  <div key={i} style={{
                    fontSize: 11,
                    color: 'var(--s-text-2)',
                    padding: '2px 0',
                    borderLeft: '2px solid rgba(59,130,246,0.2)',
                    paddingLeft: 8,
                    marginBottom: 2,
                  }}>
                    {c.excerpt ? (c.excerpt.length > 120 ? c.excerpt.slice(0, 120) + '…' : c.excerpt) : `Page ${c.page}`}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/SourcesChip.tsx
git commit -m "feat(frontend): add SourcesChip with file dedup + expandable panel

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Frontend — ResearchBubble Sources + Export

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/ResearchBubble.tsx`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add `exportDeepResearch` to `lib/api.ts`**

Append after the existing `exportMessage` function:

```typescript
export async function exportDeepResearch(
  content: string,
  sources: Source[],
  format: 'pdf' | 'docx' | 'xlsx',
  query: string = ''
): Promise<void> {
  const extensions = { pdf: 'pdf', docx: 'docx', xlsx: 'xlsx' };
  const response = await fetch(`${API_BASE}/api/chat/export-deep-research`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, sources, format, query }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Export failed' }));
    throw new Error(error.detail || 'Export failed');
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `DeepResearch-${new Date().toISOString().slice(0, 10)}.${extensions[format]}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
```

- [ ] **Step 2: Update ResearchBubble to show sources + export buttons**

Replace the entire `ResearchBubble.tsx` with:

```tsx
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { SourcesChip } from './SourcesChip';
import { exportDeepResearch, type Source } from '../../../lib/api';

interface ResearchPhase {
  phase: string;
  message: string;
  sub_questions?: string[];
  progress?: number;
  total?: number;
  report?: string;
}

interface Props {
  phases: ResearchPhase[];
  report: string | null;
  sources?: Source[];
  query?: string;
  onSourceClick?: (source: Source) => void;
}

export function ResearchBubble({ phases, report, sources = [], query = '', onSourceClick }: Props) {
  const [exporting, setExporting] = useState<string | null>(null);
  const currentPhase = phases[phases.length - 1];

  const handleExport = async (format: 'pdf' | 'docx' | 'xlsx') => {
    if (!report) return;
    setExporting(format);
    try {
      await exportDeepResearch(report, sources, format, query);
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      setExporting(null);
    }
  };

  return (
    <div style={{
      borderRadius: 'var(--s-r-sm)',
      background: 'rgba(59,130,246,0.06)',
      border: '1px solid rgba(59,130,246,0.15)',
      padding: 12,
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
    }}>
      <div style={{ fontSize: 11, color: 'var(--s-accent, var(--teal))' }}>🔬 Deep Research</div>

      {phases.map((p, i) => (
        <div key={i} style={{ fontSize: 12, color: 'var(--s-text-2)' }}>
          {p.phase === 'planned' && p.sub_questions ? (
            <div>
              <div style={{ fontWeight: 500 }}>Research plan:</div>
              <ol style={{ margin: '4px 0', paddingLeft: 20 }}>
                {p.sub_questions.map((q, j) => (
                  <li key={j} style={{ marginBottom: 2 }}>{q}</li>
                ))}
              </ol>
            </div>
          ) : p.phase === 'gathering' && p.progress ? (
            <div>⏳ {p.message} ({p.progress}/{p.total})</div>
          ) : p.phase === 'completed' ? null : (
            <div>{p.message}</div>
          )}
        </div>
      ))}

      {currentPhase && currentPhase.phase !== 'completed' && currentPhase.phase !== 'failed' && (
        <div style={{ fontSize: 12, color: 'var(--s-accent, var(--teal))', opacity: 0.7 }}>
          ⏳ {currentPhase.message}
        </div>
      )}

      {report && (
        <>
          <div className="report-markdown" style={{ marginTop: 8 }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
          </div>

          {sources.length > 0 && onSourceClick && (
            <SourcesChip sources={sources} onSourceClick={onSourceClick} />
          )}

          <div style={{
            display: 'flex',
            gap: 6,
            marginTop: 8,
            paddingTop: 8,
            borderTop: '1px solid rgba(59,130,246,0.15)',
          }}>
            {(['pdf', 'docx', 'xlsx'] as const).map(fmt => (
              <button
                key={fmt}
                type="button"
                disabled={exporting === fmt}
                onClick={() => handleExport(fmt)}
                style={{
                  padding: '4px 10px',
                  borderRadius: 6,
                  fontSize: 11,
                  fontWeight: 600,
                  border: '1px solid rgba(59,130,246,0.2)',
                  background: 'rgba(59,130,246,0.08)',
                  color: 'var(--s-accent, #3b82f6)',
                  cursor: exporting === fmt ? 'wait' : 'pointer',
                  opacity: exporting === fmt ? 0.5 : 1,
                }}
              >
                {exporting === fmt ? '⏳' : `📥 ${fmt.toUpperCase()}`}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Update LegalStudio to pass sources + query to ResearchBubble**

In `LegalStudio.tsx`, add a new state for research sources and wire it:

Find:
```tsx
const [researchReport, setResearchReport] = useState<string | null>(null);
```
After it, add:
```tsx
const [researchSources, setResearchSources] = useState<Source[]>([]);
const [researchQuery, setResearchQuery] = useState('');
```

In the SSE `onmessage` handler for deep research, find:
```tsx
if (data.phase === 'completed') {
  setResearchReport(data.report ?? '');
```
Replace with:
```tsx
if (data.phase === 'completed') {
  setResearchReport(data.report ?? '');
  setResearchSources(data.sources ?? []);
```

Before `setResearching(true)`, add:
```tsx
setResearchQuery(text);
```

Where `ResearchBubble` is rendered, change from:
```tsx
<ResearchBubble phases={researchPhases} report={researchReport} />
```
To:
```tsx
<ResearchBubble
  phases={researchPhases}
  report={researchReport}
  sources={researchSources}
  query={researchQuery}
  onSourceClick={handleSourceClick}
/>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/components/studios/LegalStudio/ResearchBubble.tsx frontend/src/components/studios/LegalStudio/LegalStudio.tsx
git commit -m "feat(frontend): deep research sources chip + branded PDF/Word/Excel export

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: Frontend — ChatMessages Source Count Fix

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/ChatMessages.tsx`

- [ ] **Step 1: Import and use SourcesChip**

At the top of `ChatMessages.tsx`, add import:
```tsx
import { SourcesChip } from './SourcesChip';
```

In the `AIMessage` component, replace the existing source display block (lines ~95-136):
```tsx
        {msg.sources && msg.sources.length > 0 && (
          <button
            type="button"
            className="chat-sources-btn"
            onClick={() => onSourceClick(msg.sources![0])}
          >
            🔗 Sources ({msg.sources.length})
          </button>
        )}
        {msg.sources && msg.sources.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '6px' }}>
            {msg.sources.filter(s => s.source && s.source.startsWith('http')).map((s, i) => {
```

Replace with:
```tsx
        {msg.sources && msg.sources.length > 0 && (
          <SourcesChip sources={msg.sources} onSourceClick={onSourceClick} />
        )}
        {msg.sources && msg.sources.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '6px' }}>
            {msg.sources.filter(s => s.source && s.source.startsWith('http')).map((s, i) => {
```

This replaces the raw count button with `SourcesChip` while keeping web URL pills below.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/ChatMessages.tsx
git commit -m "fix(frontend): use SourcesChip with deduped file count + citation count

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 2: Analyst Mode — xlsx Injection + Domain Override + Source Count

### Task 5: Backend — xlsx/csv Full Injection for Small Files

**Files:**
- Create: `backend/core/documents/xlsx_injector.py`
- Modify: `backend/api/documents.py`

- [ ] **Step 1: Create xlsx_injector.py**

```python
# backend/core/documents/xlsx_injector.py
"""Parse small xlsx/csv files into structured text for full LLM context injection."""
from __future__ import annotations

import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_INJECT_SIZE = 100 * 1024  # 100 KB
HEADER_REPEAT_INTERVAL = 20


def should_inject(file_path: str, file_size: int) -> bool:
    """Return True if the file is a small xlsx/csv that should be fully injected."""
    suffix = Path(file_path).suffix.lower()
    return suffix in (".xlsx", ".xls", ".csv") and file_size < MAX_INJECT_SIZE


def parse_to_structured_text(file_path: str) -> str:
    """Parse xlsx/csv to structured row-by-row text with headers repeated every 20 rows."""
    import pandas as pd

    suffix = Path(file_path).suffix.lower()
    sheets_text = []

    try:
        if suffix == ".csv":
            df = pd.read_csv(file_path)
            sheets_text.append(_dataframe_to_text("Sheet1", df))
        else:
            xls = pd.ExcelFile(file_path)
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                sheets_text.append(_dataframe_to_text(sheet_name, df))
    except Exception as e:
        logger.warning(f"Failed to parse {file_path} for injection: {e}")
        return ""

    return "\n\n".join(sheets_text)


def _dataframe_to_text(sheet_name: str, df) -> str:
    """Convert a DataFrame to structured text with header repetition."""
    if df.empty:
        return f"Sheet: {sheet_name}\n(empty)"

    headers = list(df.columns)
    lines = [f"Sheet: {sheet_name}"]

    for row_idx, (_, row) in enumerate(df.iterrows()):
        if row_idx > 0 and row_idx % HEADER_REPEAT_INTERVAL == 0:
            lines.append(f"--- Headers: {', '.join(str(h) for h in headers)} ---")

        parts = []
        for col in headers:
            val = row[col]
            if pd.notna(val):
                parts.append(f"{col}={val}")
        lines.append(f"Row {row_idx + 1}: {', '.join(parts)}")

    return "\n".join(lines)
```

- [ ] **Step 2: Modify document upload in `backend/api/documents.py`**

After the document is processed and indexed, add structured text injection. Find the section after `await db.commit()` (around line 130) where the upload response is built. Before the response, add:

```python
    # --- Small xlsx/csv: full injection ---
    from core.documents.xlsx_injector import should_inject, parse_to_structured_text

    if should_inject(str(saved_path), file_size):
        try:
            structured = parse_to_structured_text(str(saved_path))
            if structured:
                doc_record.metadata_json = doc_record.metadata_json or {}
                doc_record.metadata_json["structured_text"] = structured
                await db.commit()
                logger.info(f"Injected structured text for small file: {original_name} ({len(structured)} chars)")
        except Exception as e:
            logger.warning(f"Structured text injection failed for {original_name}: {e}")
```

- [ ] **Step 3: Modify chat send to include structured text in context**

In `backend/api/chat.py`, in the `send_message` function or `chat_stream` generator, where RAG results are built into the system prompt, add structured text from small files. Find where `rag_results` are formatted into context. After the RAG context block, add:

```python
    # Inject full structured text from small xlsx/csv documents
    if req.use_rag:
        try:
            result = await db.execute(
                select(Document).where(
                    Document.status == "indexed",
                    Document.metadata_json.isnot(None),
                )
            )
            for doc in result.scalars():
                meta = doc.metadata_json or {}
                if "structured_text" in meta:
                    rag_context += f"\n\n--- Full data from {doc.original_name} ---\n{meta['structured_text']}\n"
        except Exception:
            pass
```

- [ ] **Step 4: Commit**

```bash
git add backend/core/documents/xlsx_injector.py backend/api/documents.py backend/api/chat.py
git commit -m "feat(backend): xlsx/csv full injection for files < 100KB

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 6: Frontend — Domain Override Dropdown Enhancement

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/DomainChip.tsx`

- [ ] **Step 1: Add missing domains + lock icon for manual override**

Replace entire `DomainChip.tsx`:

```tsx
import { useState, useEffect } from "react";

export type DomainLabel =
  | "vat"
  | "corporate_tax"
  | "peppol"
  | "e_invoicing"
  | "labour"
  | "commercial"
  | "ifrs"
  | "general_law"
  | "audit"
  | "finance"
  | "general";

const ALL: DomainLabel[] = [
  "audit",
  "vat",
  "corporate_tax",
  "finance",
  "ifrs",
  "peppol",
  "e_invoicing",
  "labour",
  "commercial",
  "general_law",
  "general",
];

const LABELS: Record<DomainLabel, string> = {
  vat: "VAT",
  corporate_tax: "Corporate Tax",
  peppol: "Peppol",
  e_invoicing: "E-Invoicing",
  labour: "Labour",
  commercial: "Commercial",
  ifrs: "IFRS",
  general_law: "General Law",
  audit: "Audit",
  finance: "Finance",
  general: "General",
};

interface Props {
  value: DomainLabel;
  editable: boolean;
  onChange?: (v: DomainLabel) => void;
  locked?: boolean;
}

export function DomainChip({ value, editable, onChange, locked = false }: Props) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (!(e.target as Element).closest('.domain-chip-wrapper')) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  if (!editable) {
    return (
      <span className="domain-chip">
        {locked && '🔒 '}{LABELS[value] ?? value}
      </span>
    );
  }

  return (
    <div className="domain-chip-wrapper">
      <button
        type="button"
        className="domain-chip domain-chip--editable"
        onClick={() => setOpen(!open)}
      >
        {locked && '🔒 '}Domain: {LABELS[value] ?? value} ✎
      </button>
      {open && (
        <ul className="domain-chip-dropdown">
          {ALL.map((d) => (
            <li key={d}>
              <button
                type="button"
                data-active={d === value ? "true" : undefined}
                onClick={() => {
                  onChange?.(d);
                  setOpen(false);
                }}
              >
                {LABELS[d]}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add lock state to LegalStudio**

In `LegalStudio.tsx`, add state:

Find:
```tsx
const [detectedDomain, setDetectedDomain] = useState<DomainLabel | null>(null);
```
After it, add:
```tsx
const [domainLocked, setDomainLocked] = useState(false);
```

Where `DomainChip` is rendered, update:
```tsx
<DomainChip
  value={detectedDomain}
  editable
  locked={domainLocked}
  onChange={(d) => {
    setDetectedDomain(d);
    setDomain(d as Domain);
    setDomainLocked(true);
  }}
/>
```

In the `sendMessage` function, skip auto-detect when locked:
Find:
```tsx
    const userDomain = detectDomain(text);
    if (userDomain) {
      setDomain(userDomain);
      setDetectedDomain(userDomain as DomainLabel);
    }
```
Replace with:
```tsx
    if (!domainLocked) {
      const userDomain = detectDomain(text);
      if (userDomain) {
        setDomain(userDomain);
        setDetectedDomain(userDomain as DomainLabel);
      }
    }
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/DomainChip.tsx frontend/src/components/studios/LegalStudio/LegalStudio.tsx
git commit -m "feat(frontend): domain override dropdown with lock icon + missing domains

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 3: Audit Flow Rework

### Task 7: Frontend — Inline Result Card Component

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/InlineResultCard.tsx`

- [ ] **Step 1: Create InlineResultCard**

```tsx
// frontend/src/components/studios/LegalStudio/InlineResultCard.tsx
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { API_BASE } from '../../../lib/api';

interface Finding {
  severity: 'low' | 'medium' | 'high';
  document: string;
  finding: string;
}

interface AuditData {
  risk_flags: Finding[];
  anomalies: Finding[];
  compliance_gaps: Finding[];
  summary: string;
}

interface Props {
  reportType: string;
  date: string;
  format?: string;
  content?: string;
  auditData?: AuditData;
  error?: string;
  onRetry?: () => void;
}

const SEVERITY_COLORS: Record<string, string> = {
  high: 'var(--red, #ef4444)',
  medium: 'var(--amber, #f59e0b)',
  low: 'var(--text-2, #6b7280)',
};

function FindingSection({ title, rows, color }: { title: string; rows: Finding[]; color: string }) {
  if (!rows.length) return null;
  return (
    <details open>
      <summary style={{ fontSize: 13, fontWeight: 500, color, cursor: 'pointer', marginBottom: 4 }}>
        {title} ({rows.length})
      </summary>
      <ul style={{ listStyle: 'disc', paddingLeft: 20, margin: '4px 0' }}>
        {rows.map((r, i) => (
          <li key={i} style={{ fontSize: 12, color: 'var(--s-text-2)', marginBottom: 4 }}>
            <span style={{ textTransform: 'uppercase', fontSize: 10, color: SEVERITY_COLORS[r.severity] || '#6b7280' }}>
              {r.severity}
            </span>
            {' — '}
            <span style={{ color: 'var(--s-text-2)' }}>{r.document}:</span> {r.finding}
          </li>
        ))}
      </ul>
    </details>
  );
}

export function InlineResultCard({ reportType, date, format, content, auditData, error, onRetry }: Props) {
  const [exporting, setExporting] = useState<string | null>(null);

  const handleExport = async (fmt: 'pdf' | 'docx' | 'xlsx') => {
    if (!content) return;
    setExporting(fmt);
    try {
      const response = await fetch(`${API_BASE}/api/chat/export-deep-research`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, sources: [], format: fmt, query: reportType }),
      });
      if (!response.ok) throw new Error('Export failed');
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${reportType.replace(/\s+/g, '-')}-${date}.${fmt}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      setExporting(null);
    }
  };

  if (error) {
    return (
      <div style={{
        borderRadius: 'var(--s-r-sm, 8px)',
        background: 'rgba(239,68,68,0.08)',
        border: '1px solid rgba(239,68,68,0.2)',
        padding: 12,
      }}>
        <div style={{ fontSize: 12, color: 'var(--red, #ef4444)', fontWeight: 500 }}>
          ❌ Error generating {reportType}
        </div>
        <div style={{ fontSize: 12, color: 'var(--s-text-2)', marginTop: 4 }}>{error}</div>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            style={{
              marginTop: 8,
              padding: '4px 12px',
              borderRadius: 6,
              fontSize: 11,
              fontWeight: 600,
              border: '1px solid rgba(239,68,68,0.3)',
              background: 'rgba(239,68,68,0.1)',
              color: 'var(--red, #ef4444)',
              cursor: 'pointer',
            }}
          >
            🔄 Retry
          </button>
        )}
      </div>
    );
  }

  return (
    <div style={{
      borderRadius: 'var(--s-r-sm, 8px)',
      background: 'rgba(255,255,255,0.04)',
      border: '1px solid var(--s-border, rgba(255,255,255,0.08))',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '10px 12px',
        borderBottom: '1px solid var(--s-border, rgba(255,255,255,0.08))',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--s-text-1)' }}>
            📊 {reportType}
          </span>
          <span style={{
            fontSize: 10,
            padding: '2px 6px',
            borderRadius: 4,
            background: 'rgba(59,130,246,0.1)',
            color: 'var(--s-accent)',
          }}>
            {date}
          </span>
          {format && (
            <span style={{
              fontSize: 10,
              padding: '2px 6px',
              borderRadius: 4,
              background: 'rgba(139,92,246,0.1)',
              color: 'var(--purple, #a78bfa)',
            }}>
              {format}
            </span>
          )}
        </div>
      </div>

      {/* Body */}
      <div style={{ padding: 12, maxHeight: 400, overflowY: 'auto' }}>
        {auditData ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ fontSize: 13, color: 'var(--s-text-1)' }}>{auditData.summary}</div>
            <FindingSection title="Risk Flags" rows={auditData.risk_flags} color="var(--red, #ef4444)" />
            <FindingSection title="Anomalies" rows={auditData.anomalies} color="var(--amber, #f59e0b)" />
            <FindingSection title="Compliance Gaps" rows={auditData.compliance_gaps} color="var(--teal, #a78bfa)" />
          </div>
        ) : content ? (
          <div className="report-markdown">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </div>
        ) : null}
      </div>

      {/* Footer — Export buttons */}
      <div style={{
        padding: '8px 12px',
        borderTop: '1px solid var(--s-border, rgba(255,255,255,0.08))',
        display: 'flex',
        gap: 6,
      }}>
        {(['pdf', 'docx', 'xlsx'] as const).map(fmt => (
          <button
            key={fmt}
            type="button"
            disabled={exporting === fmt || (!content && !auditData)}
            onClick={() => handleExport(fmt)}
            style={{
              padding: '4px 10px',
              borderRadius: 6,
              fontSize: 11,
              fontWeight: 600,
              border: '1px solid var(--s-border, rgba(255,255,255,0.12))',
              background: 'rgba(255,255,255,0.04)',
              color: 'var(--s-text-1)',
              cursor: 'pointer',
              opacity: exporting === fmt ? 0.5 : 1,
            }}
          >
            {exporting === fmt ? '⏳' : `Export ${fmt.toUpperCase()}`}
          </button>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/InlineResultCard.tsx
git commit -m "feat(frontend): InlineResultCard for audit + financial report inline display

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 8: Frontend — Questionnaire Message Component

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/QuestionnaireMessage.tsx`

- [ ] **Step 1: Create QuestionnaireMessage**

```tsx
// frontend/src/components/studios/LegalStudio/QuestionnaireMessage.tsx
import { useState } from 'react';

interface PrefilledField {
  key: string;
  label: string;
  value: string;
  editable: boolean;
}

interface Props {
  reportType: string;
  fields: PrefilledField[];
  onConfirm: (confirmedFields: Record<string, string>) => void;
  onCancel: () => void;
  generating?: boolean;
}

export function QuestionnaireMessage({ reportType, fields, onConfirm, onCancel, generating = false }: Props) {
  const [values, setValues] = useState<Record<string, string>>(
    Object.fromEntries(fields.map(f => [f.key, f.value]))
  );

  const handleChange = (key: string, val: string) => {
    setValues(prev => ({ ...prev, [key]: val }));
  };

  return (
    <div style={{
      borderRadius: 'var(--s-r-sm, 8px)',
      background: 'rgba(59,130,246,0.04)',
      border: '1px solid rgba(59,130,246,0.15)',
      padding: 12,
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
    }}>
      <div style={{ fontSize: 11, color: 'var(--s-accent, var(--teal))' }}>
        ◆ AI Assistant
      </div>
      <div style={{ fontSize: 13, color: 'var(--s-text-1)', fontWeight: 500 }}>
        Generating <strong>{reportType}</strong>. Let me confirm a few details first...
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {fields.map(field => (
          <div key={field.key} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <label style={{
              fontSize: 12,
              color: 'var(--s-text-2)',
              minWidth: 140,
              fontWeight: 500,
            }}>
              {field.label}:
            </label>
            {field.editable ? (
              <input
                type="text"
                value={values[field.key] || ''}
                onChange={e => handleChange(field.key, e.target.value)}
                style={{
                  flex: 1,
                  padding: '4px 8px',
                  borderRadius: 4,
                  border: '1px solid var(--s-border, rgba(255,255,255,0.12))',
                  background: 'rgba(255,255,255,0.04)',
                  color: 'var(--s-text-1)',
                  fontSize: 12,
                  outline: 'none',
                }}
              />
            ) : (
              <span style={{ fontSize: 12, color: 'var(--s-text-1)' }}>
                {values[field.key] || '—'}
              </span>
            )}
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
        <button
          type="button"
          disabled={generating}
          onClick={() => onConfirm(values)}
          style={{
            padding: '6px 16px',
            borderRadius: 6,
            fontSize: 12,
            fontWeight: 600,
            border: 'none',
            background: 'var(--s-accent, #3b82f6)',
            color: '#fff',
            cursor: generating ? 'wait' : 'pointer',
            opacity: generating ? 0.6 : 1,
          }}
        >
          {generating ? '⏳ Generating...' : `✨ Generate ${reportType}`}
        </button>
        <button
          type="button"
          onClick={onCancel}
          style={{
            padding: '6px 12px',
            borderRadius: 6,
            fontSize: 12,
            border: '1px solid var(--s-border)',
            background: 'transparent',
            color: 'var(--s-text-2)',
            cursor: 'pointer',
          }}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

export type { PrefilledField };
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/QuestionnaireMessage.tsx
git commit -m "feat(frontend): QuestionnaireMessage for chat-redirect questionnaire pattern

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 9: Frontend — Custom Template Picker + AuditorFormatGrid Update

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/CustomTemplatePicker.tsx`
- Modify: `frontend/src/components/studios/LegalStudio/AuditorFormatGrid.tsx`

- [ ] **Step 1: Create CustomTemplatePicker**

```tsx
// frontend/src/components/studios/LegalStudio/CustomTemplatePicker.tsx
import { useState, useEffect } from 'react';
import { API } from '../../../lib/api';

interface Template {
  id: string;
  name: string;
  format_family: string;
  confidence_score: number;
}

interface Props {
  isOpen: boolean;
  onSelect: (templateId: string, templateName: string) => void;
  onClose: () => void;
}

export function CustomTemplatePicker({ isOpen, onSelect, onClose }: Props) {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    API.get('/api/templates/')
      .then(r => setTemplates(r.data ?? []))
      .catch(() => setTemplates([]))
      .finally(() => setLoading(false));
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'rgba(0,0,0,0.5)',
      zIndex: 1000,
    }}
    onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        background: 'var(--s-bg, #1a1a2e)',
        borderRadius: 'var(--s-r-md, 12px)',
        border: '1px solid var(--s-border)',
        padding: 20,
        minWidth: 360,
        maxWidth: 480,
        maxHeight: '70vh',
        overflowY: 'auto',
      }}>
        <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--s-text-1)', marginBottom: 12 }}>
          Select Custom Template
        </div>

        {loading ? (
          <div style={{ fontSize: 12, color: 'var(--s-text-2)', padding: 20, textAlign: 'center' }}>
            Loading templates...
          </div>
        ) : templates.length === 0 ? (
          <div style={{ fontSize: 12, color: 'var(--s-text-2)', padding: 20, textAlign: 'center' }}>
            No saved templates. Upload one in Template Learning Studio first.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {templates.map(t => (
              <button
                key={t.id}
                type="button"
                onClick={() => onSelect(t.id, t.name)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 12px',
                  borderRadius: 8,
                  border: '1px solid var(--s-border)',
                  background: 'rgba(255,255,255,0.03)',
                  color: 'var(--s-text-1)',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'background 0.15s',
                }}
                onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.06)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.03)')}
              >
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{t.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--s-text-2)' }}>{t.format_family}</div>
                </div>
                <span style={{ fontSize: 11, color: 'var(--s-accent)' }}>
                  {Math.round(t.confidence_score * 100)}% match
                </span>
              </button>
            ))}
          </div>
        )}

        <button
          type="button"
          onClick={onClose}
          style={{
            marginTop: 12,
            padding: '6px 12px',
            borderRadius: 6,
            fontSize: 12,
            border: '1px solid var(--s-border)',
            background: 'transparent',
            color: 'var(--s-text-2)',
            cursor: 'pointer',
            width: '100%',
          }}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add Custom Template to AuditorFormatGrid**

Replace `AuditorFormatGrid.tsx`:

```tsx
import React from 'react';
import { FileText, Building2, Scale, ShieldCheck, Palette } from 'lucide-react';

export type AuditorFormat = 'standard' | 'big4' | 'legal' | 'compliance' | 'custom';

const FORMAT_OPTIONS: { value: AuditorFormat; label: string; icon: React.ReactNode; desc: string }[] = [
  { value: 'standard', icon: <FileText size={16} />, label: 'Standard', desc: 'Default format' },
  { value: 'big4', icon: <Building2 size={16} />, label: 'Big 4', desc: 'Deloitte/PwC style' },
  { value: 'legal', icon: <Scale size={16} />, label: 'Legal Brief', desc: 'Court format' },
  { value: 'compliance', icon: <ShieldCheck size={16} />, label: 'Compliance', desc: 'SOX/GDPR' },
  { value: 'custom', icon: <Palette size={16} />, label: 'Custom Template', desc: 'Your saved templates' },
];

interface Props {
  value: AuditorFormat;
  onChange: (format: AuditorFormat) => void;
}

export function AuditorFormatGrid({ value, onChange }: Props) {
  return (
    <div>
      <div style={{
        fontSize: 13,
        fontWeight: 600,
        color: 'var(--s-text-1)',
        marginBottom: 8,
        fontFamily: 'var(--s-font-ui)',
        display: 'flex',
        alignItems: 'center',
        gap: 6,
      }}>
        Auditor Format
      </div>
      <div className="format-grid">
        {FORMAT_OPTIONS.map(opt => (
          <button
            key={opt.value}
            type="button"
            className={`format-option${opt.value === value ? ' format-option--selected' : ''}`}
            onClick={() => onChange(opt.value)}
            aria-pressed={opt.value === value}
          >
            <div className="format-option__icon">{opt.icon}</div>
            <div className="format-option__name">{opt.label}</div>
            <div className="format-option__desc">{opt.desc}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/CustomTemplatePicker.tsx frontend/src/components/studios/LegalStudio/AuditorFormatGrid.tsx
git commit -m "feat(frontend): custom template picker modal + 5th auditor format option

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 10: Audit Flow — Error Handling + Chat Questionnaire + Inline Card in LegalStudio

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`

- [ ] **Step 1: Add questionnaire and inline card state**

At the top of `LegalStudio.tsx`, add imports:
```tsx
import { InlineResultCard } from './InlineResultCard';
import { QuestionnaireMessage, type PrefilledField } from './QuestionnaireMessage';
import { CustomTemplatePicker } from './CustomTemplatePicker';
import { type AuditorFormat } from './AuditorFormatGrid';
```

Add new state variables after existing state:
```tsx
  const [auditError, setAuditError] = useState<string | null>(null);
  const [questionnaireActive, setQuestionnaireActive] = useState(false);
  const [questionnaireType, setQuestionnaireType] = useState('');
  const [questionnaireFields, setQuestionnaireFields] = useState<PrefilledField[]>([]);
  const [reportGenerating, setReportGenerating] = useState(false);
  const [inlineCards, setInlineCards] = useState<Array<{
    id: string;
    reportType: string;
    content?: string;
    auditData?: any;
    error?: string;
    date: string;
    format?: string;
  }>>([]);
  const [templatePickerOpen, setTemplatePickerOpen] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [selectedTemplateName, setSelectedTemplateName] = useState<string | null>(null);
  const [auditorFormat, setAuditorFormat] = useState<AuditorFormat>('standard');
```

- [ ] **Step 2: Replace handleRunAudit with questionnaire flow**

Replace the existing `handleRunAudit`:
```tsx
  const handleRunAudit = useCallback(async () => {
    if (selectedDocIds.length === 0) return;
    setAuditing(true);
    setAuditResult(null);
    try {
      const res = await API.post('/api/legal-studio/auditor', { document_ids: selectedDocIds });
      setAuditResult(res.data);
    } catch { /* ignore */ }
    setAuditing(false);
  }, [selectedDocIds]);
```

With:
```tsx
  const handleAuditFormatSelect = useCallback((format: AuditorFormat) => {
    setAuditorFormat(format);
    if (format === 'custom') {
      setTemplatePickerOpen(true);
      return;
    }
    // Launch questionnaire
    const formatLabels: Record<string, string> = {
      standard: 'Standard Audit Report',
      big4: 'Big 4 Audit Report',
      legal: 'Legal Brief Audit',
      compliance: 'Compliance Audit Report',
    };
    startAuditQuestionnaire(formatLabels[format] || 'Audit Report', format);
  }, []);

  const startAuditQuestionnaire = useCallback((reportType: string, format: string) => {
    const fields: PrefilledField[] = [
      { key: 'period', label: 'Period', value: '', editable: true },
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'entity_type', label: 'Entity Type', value: 'LLC', editable: true },
      { key: 'currency', label: 'Currency', value: 'AED', editable: true },
      { key: 'framework', label: 'Reporting Framework', value: 'IFRS', editable: true },
      { key: 'comparative', label: 'Standalone vs Comparative', value: 'Standalone', editable: true },
      { key: 'materiality', label: 'Materiality Threshold', value: '2% of revenue', editable: true },
      { key: 'engagement_type', label: 'Engagement Type', value: 'Statutory', editable: true },
    ];
    setQuestionnaireType(reportType);
    setQuestionnaireFields(fields);
    setQuestionnaireActive(true);
  }, []);

  const handleTemplateSelect = useCallback((templateId: string, templateName: string) => {
    setSelectedTemplateId(templateId);
    setSelectedTemplateName(templateName);
    setTemplatePickerOpen(false);
    startAuditQuestionnaire(`Custom Template: ${templateName}`, 'custom');
  }, [startAuditQuestionnaire]);

  const handleQuestionnaireConfirm = useCallback(async (fields: Record<string, string>) => {
    setReportGenerating(true);
    setQuestionnaireActive(false);

    try {
      const res = await API.post('/api/legal-studio/auditor', {
        document_ids: selectedDocIds,
        format: auditorFormat,
        template_id: selectedTemplateId,
        fields,
      });

      const cardId = crypto.randomUUID();
      setInlineCards(prev => [...prev, {
        id: cardId,
        reportType: questionnaireType,
        auditData: res.data,
        date: new Date().toISOString().slice(0, 10),
        format: auditorFormat,
      }]);
    } catch (err: any) {
      const errorMsg = err?.response?.data?.detail || err?.message || 'Audit generation failed';
      setAuditError(errorMsg);
      const cardId = crypto.randomUUID();
      setInlineCards(prev => [...prev, {
        id: cardId,
        reportType: questionnaireType,
        error: errorMsg,
        date: new Date().toISOString().slice(0, 10),
      }]);
    } finally {
      setReportGenerating(false);
    }
  }, [selectedDocIds, auditorFormat, selectedTemplateId, questionnaireType]);

  const handleRetryAudit = useCallback(() => {
    setAuditError(null);
    setInlineCards(prev => prev.filter(c => !c.error));
    if (questionnaireFields.length > 0) {
      setQuestionnaireActive(true);
    }
  }, [questionnaireFields]);
```

- [ ] **Step 3: Update the render section to include questionnaire + inline cards**

In the `centerContent` JSX, after the `ChatMessages` component and before the research bubble, add:

```tsx
        {/* Questionnaire */}
        {questionnaireActive && (
          <div className="legal-section-pad">
            <QuestionnaireMessage
              reportType={questionnaireType}
              fields={questionnaireFields}
              onConfirm={handleQuestionnaireConfirm}
              onCancel={() => setQuestionnaireActive(false)}
              generating={reportGenerating}
            />
          </div>
        )}

        {/* Inline result cards */}
        {inlineCards.map(card => (
          <div key={card.id} className="legal-section-pad">
            <InlineResultCard
              reportType={card.reportType}
              date={card.date}
              format={card.format}
              content={card.content}
              auditData={card.auditData}
              error={card.error}
              onRetry={card.error ? handleRetryAudit : undefined}
            />
          </div>
        ))}
```

Remove the old `AuditorResultBubble` render block:
```tsx
        {auditResult && (
          <div className="legal-section-pad">
            <AuditorResultBubble
              ...
            />
          </div>
        )}
```

And add the `CustomTemplatePicker` modal before the closing of `centerContent`:
```tsx
      <CustomTemplatePicker
        isOpen={templatePickerOpen}
        onSelect={handleTemplateSelect}
        onClose={() => setTemplatePickerOpen(false)}
      />
```

- [ ] **Step 4: Update toolbar to use format selector + questionnaire flow**

Replace the audit button in the toolbar:
```tsx
        {(mode === 'analyst' || domain === 'audit') && (
          <button
            type="button"
            className="legal-toolbar__btn legal-toolbar__btn--audit"
            onClick={handleRunAudit}
            disabled={selectedDocIds.length === 0 || auditing}
            ...
          >
```

With:
```tsx
        {(mode === 'analyst' || domain === 'audit') && (
          <button
            type="button"
            className="legal-toolbar__btn legal-toolbar__btn--audit"
            onClick={() => startAuditQuestionnaire('Standard Audit Report', 'standard')}
            disabled={selectedDocIds.length === 0 || reportGenerating}
            aria-label={`Run audit on ${selectedDocIds.length} selected documents`}
          >
            {reportGenerating
              ? <><Loader2 size={14} className="spin" style={{ verticalAlign: 'middle', marginRight: 4 }} />Generating…</>
              : <><ScanSearch size={14} style={{ verticalAlign: 'middle', marginRight: 4 }} />Run Audit ({selectedDocIds.length})</>
            }
          </button>
        )}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/LegalStudio.tsx
git commit -m "feat(frontend): audit chat questionnaire + inline result cards + error handling

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 11: Backend — Notebook Source Persist + Delete

**Files:**
- Modify: `backend/api/legal_studio.py`
- Modify: `backend/db/models.py`

- [ ] **Step 1: Add checked_source_ids to Conversation model**

In `backend/db/models.py`, in the `Conversation` class, add after `llm_model`:

```python
    checked_source_ids = Column(JSON, nullable=True)  # list of document IDs currently checked
```

- [ ] **Step 2: Add notebook endpoints to legal_studio.py**

Append to `backend/api/legal_studio.py`:

```python
# ── Notebook Source Persist ───────────────────────────────────────

class SaveSourcesRequest(BaseModel):
    conversation_id: str
    source_ids: list[str]


@router.post("/save-sources")
async def save_checked_sources(req: SaveSourcesRequest, db: AsyncSession = Depends(get_db)):
    """Persist which source document IDs are checked for a notebook."""
    from sqlalchemy import update
    await db.execute(
        update(Conversation)
        .where(Conversation.id == req.conversation_id)
        .values(checked_source_ids=req.source_ids)
    )
    await db.commit()
    return {"status": "ok"}


@router.get("/notebook/{conversation_id}/sources")
async def get_notebook_sources(conversation_id: str, db: AsyncSession = Depends(get_db)):
    """Get persisted checked source IDs for a notebook."""
    from sqlalchemy import select as sa_select
    result = await db.execute(
        sa_select(Conversation.checked_source_ids).where(Conversation.id == conversation_id)
    )
    row = result.scalar_one_or_none()
    return {"source_ids": row or []}


# ── Notebook Delete ───────────────────────────────────────────────

@router.delete("/notebook/{conversation_id}")
async def delete_notebook(conversation_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a notebook (conversation) and all its messages."""
    from sqlalchemy import select as sa_select, delete as sa_delete
    from db.models import Message

    conv = await db.execute(
        sa_select(Conversation).where(Conversation.id == conversation_id)
    )
    conv_obj = conv.scalar_one_or_none()
    if not conv_obj:
        raise HTTPException(status_code=404, detail="Notebook not found")

    await db.execute(sa_delete(Message).where(Message.conversation_id == conversation_id))
    await db.delete(conv_obj)
    await db.commit()
    return {"status": "deleted"}
```

- [ ] **Step 3: Run migration to add column**

```bash
cd backend && python -c "
import asyncio
from db.database import engine, Base
from db import models
asyncio.run(Base.metadata.create_all(engine))
print('Schema updated')
"
```

Note: Since we use SQLAlchemy create_all, new columns on existing tables may need `ALTER TABLE`. For SQLite, the simplest approach is to recreate. The app already does `create_all` on startup in `main.py`, so just restart the backend.

- [ ] **Step 4: Commit**

```bash
git add backend/db/models.py backend/api/legal_studio.py
git commit -m "feat(backend): notebook source persist + delete endpoint

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 4: Financial Reports — Chat-Redirect Pattern

### Task 12: Frontend — StudioPanel + StudioCards Chat-Redirect

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/StudioCards.tsx`
- Modify: `frontend/src/components/studios/LegalStudio/StudioPanel.tsx`
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`

- [ ] **Step 1: Add all financial report types to StudioCards**

In `StudioCards.tsx`, update the `ANALYST_CARDS` array to include all 11 report types from the spec. Find the existing `ANALYST_CARDS` definition and replace with:

```tsx
export type ReportType =
  | 'audit' | 'profit_loss' | 'balance_sheet' | 'cash_flow'
  | 'mis' | 'vat_return' | 'corporate_tax' | 'budget_vs_actual'
  | 'forecast' | 'ifrs_statements' | 'board_report' | 'custom_report';

const ANALYST_CARDS: { type: ReportType; label: string; icon: React.ReactNode; desc: string }[] = [
  { type: 'profit_loss', label: 'P&L Statement', icon: <TrendingUp size={16} />, desc: 'Income statement' },
  { type: 'balance_sheet', label: 'Balance Sheet', icon: <BarChart3 size={16} />, desc: 'Financial position' },
  { type: 'cash_flow', label: 'Cash Flow', icon: <ArrowDownUp size={16} />, desc: 'Cash movements' },
  { type: 'mis', label: 'MIS Report', icon: <LayoutDashboard size={16} />, desc: 'Management info' },
  { type: 'vat_return', label: 'VAT Return', icon: <Receipt size={16} />, desc: 'FTA VAT filing' },
  { type: 'corporate_tax', label: 'Corporate Tax', icon: <Landmark size={16} />, desc: 'CT computation' },
  { type: 'budget_vs_actual', label: 'Budget vs Actual', icon: <GitCompare size={16} />, desc: 'Variance analysis' },
  { type: 'forecast', label: 'Forecasting', icon: <TrendingUp size={16} />, desc: 'Financial projections' },
  { type: 'ifrs_statements', label: 'IFRS Statements', icon: <FileText size={16} />, desc: 'Full IFRS set' },
  { type: 'board_report', label: 'Board Report', icon: <Users size={16} />, desc: 'Board presentation' },
  { type: 'custom_report', label: 'Custom Report', icon: <FileEdit size={16} />, desc: 'Describe what to generate' },
];
```

Add the necessary lucide-react imports at the top:
```tsx
import { FileText, TrendingUp, BarChart3, ArrowDownUp, LayoutDashboard, Receipt, Landmark, GitCompare, Users, FileEdit, Scale, ShieldCheck, Search } from 'lucide-react';
```

- [ ] **Step 2: Update StudioPanel to redirect to chat questionnaire**

Replace `StudioPanel.tsx` entirely:

```tsx
import { useState } from 'react';
import { StudioCards, type ReportType } from './StudioCards';
import { AuditorFormatGrid, type AuditorFormat } from './AuditorFormatGrid';
import { type ChatMode } from './ModePills';

interface Props {
  sourceIds: string[];
  companyName?: string;
  mode?: ChatMode;
  onReportSelect?: (type: ReportType) => void;
  onAuditFormatSelect?: (format: AuditorFormat) => void;
}

export function StudioPanel({ sourceIds, mode, onReportSelect, onAuditFormatSelect }: Props) {
  const [format, setFormat] = useState<AuditorFormat>('standard');

  const handleFormatChange = (f: AuditorFormat) => {
    setFormat(f);
    onAuditFormatSelect?.(f);
  };

  const handleReportSelect = (type: ReportType) => {
    onReportSelect?.(type);
  };

  return (
    <aside className="studio-panel">
      <div className="studio-panel__title">
        {mode === 'analyst' ? 'Financial Reports' : 'Studio'}
      </div>
      <StudioCards onSelect={handleReportSelect} disabled={sourceIds.length === 0} mode={mode} />
      <hr className="studio-divider" />
      <AuditorFormatGrid value={format} onChange={handleFormatChange} />
    </aside>
  );
}
```

- [ ] **Step 3: Wire financial report questionnaire in LegalStudio**

In `LegalStudio.tsx`, add a handler for financial report selection that creates the chat questionnaire:

```tsx
  const REPORT_FIELDS: Record<string, PrefilledField[]> = {
    profit_loss: [
      { key: 'period', label: 'Period', value: '', editable: true },
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'currency', label: 'Currency', value: 'AED', editable: true },
      { key: 'framework', label: 'Framework', value: 'IFRS', editable: true },
      { key: 'comparative', label: 'Standalone vs Comparative', value: 'Standalone', editable: true },
    ],
    balance_sheet: [
      { key: 'period', label: 'Period', value: '', editable: true },
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'currency', label: 'Currency', value: 'AED', editable: true },
      { key: 'framework', label: 'Framework', value: 'IFRS', editable: true },
      { key: 'comparative', label: 'Standalone vs Comparative', value: 'Standalone', editable: true },
    ],
    cash_flow: [
      { key: 'period', label: 'Period', value: '', editable: true },
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'currency', label: 'Currency', value: 'AED', editable: true },
      { key: 'method', label: 'Direct vs Indirect', value: 'Indirect', editable: true },
    ],
    mis: [
      { key: 'period', label: 'Period', value: '', editable: true },
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'department', label: 'Department Filter', value: 'All', editable: true },
      { key: 'kpis', label: 'KPI Selection', value: 'Revenue, EBITDA, Net Profit', editable: true },
    ],
    vat_return: [
      { key: 'period', label: 'Period', value: '', editable: true },
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'quarter', label: 'Quarter', value: '', editable: true },
      { key: 'input_output', label: 'Input/Output Split', value: '', editable: true },
    ],
    corporate_tax: [
      { key: 'period', label: 'Fiscal Year', value: '', editable: true },
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'free_zone', label: 'Free Zone Status', value: 'No', editable: true },
      { key: 'related_party', label: 'Related Party Flag', value: 'No', editable: true },
    ],
    budget_vs_actual: [
      { key: 'period', label: 'Period', value: '', editable: true },
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'budget_source', label: 'Budget Source', value: 'Upload', editable: true },
      { key: 'variance_threshold', label: 'Variance Threshold %', value: '10', editable: true },
    ],
    forecast: [
      { key: 'period', label: 'Period', value: '', editable: true },
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'horizon', label: 'Horizon (months)', value: '12', editable: true },
      { key: 'scenarios', label: 'Scenario Count', value: '3', editable: true },
    ],
    ifrs_statements: [
      { key: 'period', label: 'Period', value: '', editable: true },
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'full_or_partial', label: 'Full Set vs Partial', value: 'Full', editable: true },
      { key: 'comparative', label: 'Comparative Period', value: '', editable: true },
    ],
    board_report: [
      { key: 'period', label: 'Period', value: '', editable: true },
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'audience', label: 'Audience', value: 'Internal', editable: true },
      { key: 'risk_appetite', label: 'Risk Appetite', value: 'Moderate', editable: true },
    ],
    custom_report: [
      { key: 'period', label: 'Period', value: '', editable: true },
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'description', label: 'Describe Report', value: '', editable: true },
    ],
  };

  const REPORT_LABELS: Record<string, string> = {
    profit_loss: 'P&L Statement',
    balance_sheet: 'Balance Sheet',
    cash_flow: 'Cash Flow Statement',
    mis: 'MIS Report',
    vat_return: 'VAT Return',
    corporate_tax: 'Corporate Tax Computation',
    budget_vs_actual: 'Budget vs Actual',
    forecast: 'Financial Forecast',
    ifrs_statements: 'IFRS Statements',
    board_report: 'Board Report',
    custom_report: 'Custom Report',
    audit: 'Audit Report',
  };

  const handleFinancialReportSelect = useCallback((type: string) => {
    const fields = REPORT_FIELDS[type] || [
      { key: 'period', label: 'Period', value: '', editable: true },
      { key: 'entity_name', label: 'Entity Name', value: '', editable: true },
      { key: 'currency', label: 'Currency', value: 'AED', editable: true },
    ];
    const label = REPORT_LABELS[type] || type;

    if (type === 'audit') {
      startAuditQuestionnaire('Standard Audit Report', 'standard');
      return;
    }

    setQuestionnaireType(label);
    setQuestionnaireFields(fields);
    setQuestionnaireActive(true);
  }, [startAuditQuestionnaire]);

  const handleFinancialConfirm = useCallback(async (fields: Record<string, string>) => {
    setReportGenerating(true);
    setQuestionnaireActive(false);

    try {
      const backendType = questionnaireType.toLowerCase().replace(/\s+/g, '_');
      const res = await API.post(`/api/reports/generate/${backendType}`, {
        mapped_data: [],
        requirements: fields,
        source_ids: selectedDocIds,
        auditor_format: auditorFormat,
        company_name: fields.entity_name || 'Analysis',
      });

      const cardId = crypto.randomUUID();
      setInlineCards(prev => [...prev, {
        id: cardId,
        reportType: questionnaireType,
        content: res.data.report_text ?? res.data.draft ?? 'Report generated.',
        date: new Date().toISOString().slice(0, 10),
        format: auditorFormat,
      }]);
    } catch (err: any) {
      const errorMsg = err?.response?.data?.detail || err?.message || 'Report generation failed';
      const cardId = crypto.randomUUID();
      setInlineCards(prev => [...prev, {
        id: cardId,
        reportType: questionnaireType,
        error: errorMsg,
        date: new Date().toISOString().slice(0, 10),
      }]);
    } finally {
      setReportGenerating(false);
    }
  }, [questionnaireType, selectedDocIds, auditorFormat]);
```

Update the `StudioPanel` render to pass callbacks:
```tsx
      right={
        <StudioPanel
          sourceIds={selectedDocIds}
          mode={mode}
          onReportSelect={handleFinancialReportSelect}
          onAuditFormatSelect={handleAuditFormatSelect}
        />
      }
```

Update the questionnaire `onConfirm` to use the appropriate handler based on type:
```tsx
<QuestionnaireMessage
  reportType={questionnaireType}
  fields={questionnaireFields}
  onConfirm={questionnaireType.includes('Audit') ? handleQuestionnaireConfirm : handleFinancialConfirm}
  onCancel={() => setQuestionnaireActive(false)}
  generating={reportGenerating}
/>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/StudioCards.tsx frontend/src/components/studios/LegalStudio/StudioPanel.tsx frontend/src/components/studios/LegalStudio/LegalStudio.tsx
git commit -m "feat(frontend): financial reports chat-redirect questionnaire for all 11 types

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 5: Notebook List UX

### Task 13: Frontend — NotebookCard Gradient Thumbnails + Delete

**Files:**
- Modify: `frontend/src/components/common/NotebookCard.tsx`

- [ ] **Step 1: Replace NotebookCard with gradient thumbnails + delete button**

```tsx
import { useState } from 'react';
import { Trash2 } from 'lucide-react';

interface Notebook {
  id: string;
  title: string;
  updated_at: string;
  source_count?: number;
  thumbnail_icon?: string;
}

interface Props {
  notebook: Notebook;
  onClick: (id: string) => void;
  onDelete?: (id: string) => void;
  view?: 'grid' | 'list';
}

function titleToGradient(title: string): string {
  let hash = 0;
  for (let i = 0; i < title.length; i++) {
    hash = title.charCodeAt(i) + ((hash << 5) - hash);
  }
  const h1 = Math.abs(hash % 360);
  const h2 = (h1 + 40 + Math.abs((hash >> 8) % 40)) % 360;
  return `linear-gradient(135deg, hsl(${h1}, 60%, 35%), hsl(${h2}, 50%, 25%))`;
}

export function NotebookCard({ notebook, onClick, onDelete, view = 'grid' }: Props) {
  const [hovered, setHovered] = useState(false);
  const dateStr = new Date(notebook.updated_at).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  });
  const gradient = titleToGradient(notebook.title);

  if (view === 'list') {
    return (
      <div
        className="notebook-card notebook-card--list"
        onClick={() => onClick(notebook.id)}
        role="button"
        tabIndex={0}
        onKeyDown={e => { if (e.key === 'Enter') onClick(notebook.id); }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '8px 12px',
          borderRadius: 8,
          cursor: 'pointer',
          background: hovered ? 'rgba(255,255,255,0.04)' : 'transparent',
          transition: 'background 0.15s',
        }}
      >
        <div style={{
          width: 32, height: 32, borderRadius: 6,
          background: gradient,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 14, color: '#fff', fontWeight: 700, flexShrink: 0,
        }}>
          {notebook.title.charAt(0).toUpperCase()}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--s-text-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {notebook.title}
          </div>
        </div>
        <div style={{ fontSize: 11, color: 'var(--s-text-2)', whiteSpace: 'nowrap' }}>
          {dateStr}
        </div>
        <div style={{ fontSize: 11, color: 'var(--s-text-2)', whiteSpace: 'nowrap', minWidth: 60 }}>
          {notebook.source_count != null ? `${notebook.source_count} sources` : ''}
        </div>
        {hovered && onDelete && (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onDelete(notebook.id); }}
            style={{
              background: 'rgba(239,68,68,0.1)',
              border: 'none',
              borderRadius: 4,
              padding: 4,
              cursor: 'pointer',
              color: 'var(--red, #ef4444)',
              display: 'flex',
            }}
            title="Delete notebook"
          >
            <Trash2 size={14} />
          </button>
        )}
      </div>
    );
  }

  return (
    <div
      className="notebook-card"
      onClick={() => onClick(notebook.id)}
      role="button"
      tabIndex={0}
      onKeyDown={e => { if (e.key === 'Enter') onClick(notebook.id); }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{ position: 'relative' }}
    >
      {hovered && onDelete && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onDelete(notebook.id); }}
          style={{
            position: 'absolute',
            top: 8,
            right: 8,
            background: 'rgba(239,68,68,0.15)',
            border: 'none',
            borderRadius: 6,
            padding: 4,
            cursor: 'pointer',
            color: 'var(--red, #ef4444)',
            display: 'flex',
            zIndex: 2,
          }}
          title="Delete notebook"
        >
          <Trash2 size={14} />
        </button>
      )}
      <div className="notebook-card__thumb" style={{
        background: gradient,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#fff',
        fontWeight: 700,
        fontSize: 18,
        minHeight: 60,
        borderRadius: '8px 8px 0 0',
      }}>
        {notebook.title.slice(0, 2).toUpperCase()}
      </div>
      <div className="notebook-card__info">
        <div className="notebook-card__title">{notebook.title}</div>
        <div className="notebook-card__meta">
          {dateStr}{notebook.source_count != null ? ` · ${notebook.source_count} sources` : ''}
        </div>
      </div>
    </div>
  );
}

interface CreateCardProps {
  onClick: () => void;
}

export function CreateNotebookCard({ onClick }: CreateCardProps) {
  return (
    <div
      className="notebook-card notebook-card--create"
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={e => { if (e.key === 'Enter') onClick(); }}
    >
      <div className="notebook-card__thumb" style={{
        background: 'linear-gradient(135deg, rgba(59,130,246,0.2), rgba(139,92,246,0.2))',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--s-accent)',
        fontSize: 24,
        minHeight: 60,
        borderRadius: '8px 8px 0 0',
      }}>
        +
      </div>
      <div className="notebook-card__info">
        <div className="notebook-card__title" style={{ color: 'var(--s-accent)' }}>
          Create New Notebook
        </div>
        <div className="notebook-card__meta">Start from scratch</div>
      </div>
    </div>
  );
}

export type { Notebook };
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/common/NotebookCard.tsx
git commit -m "feat(frontend): notebook gradient thumbnails + delete button on hover

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 14: Frontend — HomePage Search + Grid/List Toggle + Create First + Delete

**Files:**
- Modify: `frontend/src/pages/HomePage.tsx`

- [ ] **Step 1: Replace HomePage with full notebook list UX**

```tsx
import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, LayoutGrid, List } from 'lucide-react';
import { API } from '../lib/api';
import { NotebookCard, CreateNotebookCard, type Notebook } from '../components/common/NotebookCard';

interface HomePageProps {
  onNewChat?: () => void;
}

export default function HomePage({ onNewChat }: HomePageProps) {
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [search, setSearch] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    API.get('/api/chat/conversations')
      .then(r => {
        const convos = r.data ?? [];
        setNotebooks(convos.map((c: any) => ({
          id: c.id,
          title: c.title || 'Untitled Notebook',
          updated_at: c.updated_at || new Date().toISOString(),
          source_count: c.source_count,
        })));
      })
      .catch(() => {});
  }, []);

  const filtered = useMemo(() => {
    if (!search.trim()) return notebooks;
    const q = search.toLowerCase();
    return notebooks.filter(nb => nb.title.toLowerCase().includes(q));
  }, [notebooks, search]);

  const handleOpen = (id: string) => {
    navigate(`/notebook/${id}`);
  };

  const handleCreate = () => {
    if (onNewChat) onNewChat();
    else navigate('/notebook/new');
  };

  const handleDeleteRequest = (id: string) => {
    setDeleteConfirm(id);
  };

  const handleDeleteConfirm = async () => {
    if (!deleteConfirm) return;
    const id = deleteConfirm;
    setDeleteConfirm(null);
    setNotebooks(prev => prev.filter(nb => nb.id !== id));
    try {
      await API.delete(`/api/legal-studio/notebook/${id}`);
    } catch (err) {
      console.error('Failed to delete notebook:', err);
      // Reload on failure
      API.get('/api/chat/conversations')
        .then(r => {
          const convos = r.data ?? [];
          setNotebooks(convos.map((c: any) => ({
            id: c.id,
            title: c.title || 'Untitled Notebook',
            updated_at: c.updated_at || new Date().toISOString(),
            source_count: c.source_count,
          })));
        })
        .catch(() => {});
    }
  };

  const deletingNotebook = notebooks.find(nb => nb.id === deleteConfirm);

  return (
    <div className="home-page">
      <div className="home-page__header">
        <h1 className="home-page__title">📚 Legal Studio</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* Search */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '6px 10px',
            borderRadius: 8,
            border: '1px solid var(--s-border, rgba(255,255,255,0.1))',
            background: 'rgba(255,255,255,0.04)',
          }}>
            <Search size={14} style={{ color: 'var(--s-text-2)' }} />
            <input
              type="text"
              placeholder="Search notebooks..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{
                border: 'none',
                background: 'transparent',
                color: 'var(--s-text-1)',
                fontSize: 13,
                outline: 'none',
                width: 180,
              }}
            />
          </div>

          {/* View toggle */}
          <div style={{
            display: 'flex',
            borderRadius: 6,
            border: '1px solid var(--s-border, rgba(255,255,255,0.1))',
            overflow: 'hidden',
          }}>
            <button
              type="button"
              onClick={() => setViewMode('grid')}
              style={{
                padding: '5px 8px',
                border: 'none',
                background: viewMode === 'grid' ? 'rgba(59,130,246,0.15)' : 'transparent',
                color: viewMode === 'grid' ? 'var(--s-accent)' : 'var(--s-text-2)',
                cursor: 'pointer',
                display: 'flex',
              }}
              title="Grid view"
            >
              <LayoutGrid size={14} />
            </button>
            <button
              type="button"
              onClick={() => setViewMode('list')}
              style={{
                padding: '5px 8px',
                border: 'none',
                borderLeft: '1px solid var(--s-border, rgba(255,255,255,0.1))',
                background: viewMode === 'list' ? 'rgba(59,130,246,0.15)' : 'transparent',
                color: viewMode === 'list' ? 'var(--s-accent)' : 'var(--s-text-2)',
                cursor: 'pointer',
                display: 'flex',
              }}
              title="List view"
            >
              <List size={14} />
            </button>
          </div>
        </div>
      </div>

      <div className="home-page__section-label">Recent Notebooks</div>

      {viewMode === 'grid' ? (
        <div className="notebook-grid">
          <CreateNotebookCard onClick={handleCreate} />
          {filtered.map(nb => (
            <NotebookCard
              key={nb.id}
              notebook={nb}
              onClick={handleOpen}
              onDelete={handleDeleteRequest}
              view="grid"
            />
          ))}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <div
            onClick={handleCreate}
            role="button"
            tabIndex={0}
            onKeyDown={e => { if (e.key === 'Enter') handleCreate(); }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '8px 12px',
              borderRadius: 8,
              cursor: 'pointer',
              color: 'var(--s-accent)',
              fontSize: 13,
              fontWeight: 500,
            }}
          >
            + Create New Notebook
          </div>
          {filtered.map(nb => (
            <NotebookCard
              key={nb.id}
              notebook={nb}
              onClick={handleOpen}
              onDelete={handleDeleteRequest}
              view="list"
            />
          ))}
        </div>
      )}

      {search && filtered.length === 0 && (
        <div style={{
          textAlign: 'center',
          padding: 40,
          fontSize: 13,
          color: 'var(--s-text-2)',
        }}>
          No notebooks match &apos;{search}&apos;
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div style={{
          position: 'fixed',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'rgba(0,0,0,0.5)',
          zIndex: 1000,
        }}
        onClick={(e) => { if (e.target === e.currentTarget) setDeleteConfirm(null); }}
        >
          <div style={{
            background: 'var(--s-bg, #1a1a2e)',
            borderRadius: 12,
            border: '1px solid var(--s-border)',
            padding: 20,
            minWidth: 320,
            textAlign: 'center',
          }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--s-text-1)', marginBottom: 8 }}>
              Delete {deletingNotebook?.title ?? 'Notebook'}?
            </div>
            <div style={{ fontSize: 12, color: 'var(--s-text-2)', marginBottom: 16 }}>
              This cannot be undone.
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
              <button
                type="button"
                onClick={() => setDeleteConfirm(null)}
                style={{
                  padding: '6px 16px',
                  borderRadius: 6,
                  fontSize: 12,
                  border: '1px solid var(--s-border)',
                  background: 'transparent',
                  color: 'var(--s-text-2)',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteConfirm}
                style={{
                  padding: '6px 16px',
                  borderRadius: 6,
                  fontSize: 12,
                  border: 'none',
                  background: 'var(--red, #ef4444)',
                  color: '#fff',
                  cursor: 'pointer',
                }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/HomePage.tsx
git commit -m "feat(frontend): notebook list with search, grid/list toggle, gradient thumbnails, delete

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Final Task: Build Verification

### Task 15: Build + Verify

- [ ] **Step 1: Frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 2: Backend import check**

Run: `cd backend && python -c "from api.chat import router; from api.legal_studio import router; from core.deep_research_export import to_branded_pdf; print('All imports OK')"`
Expected: `All imports OK`

- [ ] **Step 3: Fix any build errors and re-verify**

If TypeScript errors appear, fix them. Common issues:
- Missing imports
- Type mismatches from new props
- Unused imports from removed code

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "fix: resolve build errors from bug fix bundle

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```
