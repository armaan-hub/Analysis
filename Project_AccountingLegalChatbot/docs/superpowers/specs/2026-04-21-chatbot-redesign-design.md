# Chatbot Redesign — Design Spec
**Date:** 2026-04-21  
**Project:** Project_AccountingLegalChatbot  
**Scope:** Sub-projects A, B, C — Mode System, Source Fixes, Deep Research, Analyst, MIS, Reports

---

## Overview

This spec covers a comprehensive redesign across three sequential sub-projects:

- **Sub-project A — Foundation:** Mode system redesign (Normal → Fast/Deep Research/Analyst), source UUID resolution fix, mode persistence per conversation, Deep Research blank screen fix.
- **Sub-project B — Deep Research:** Internet search via Tavily, right-side research log panel, auto-save fetched data to RAG database.
- **Sub-project C — Analyst:** LLM scoped to attached documents, audit auto-detection, draggable audit overlay, MIS with charts and KPIs in artifact panel, reports with smart confirm card + instant generation + chat refinement.

Sub-projects are implemented in order: A is a prerequisite for B and C. B and C are implemented sequentially.

---

## Sub-Project A — Foundation

### A1. Mode System Redesign

#### Modes

| Mode | Value | Layout | Purpose |
|------|-------|--------|---------|
| ⚡ Fast | `fast` | Single center panel | Quick chat, general LLM knowledge |
| 🔬 Deep Research | `deep_research` | Center + right research log | Research-driven answers with internet + RAG |
| 📊 Analyst | `analyst` | Left sources + center chat + right studio | Document analysis, audit, reports |

The existing `normal` mode value is renamed to `fast` (data migration: update existing conversations with `mode = NULL` or `mode = 'normal'` to `mode = 'fast'`).

#### Backend: DB Schema

Add a `mode` column to the `conversations` table:

```python
# db/models.py — Conversation model
mode = Column(String(20), nullable=False, default="fast")
# values: "fast" | "deep_research" | "analyst"
```

Add an Alembic migration (or SQLite ALTER TABLE at startup) to add the column. On migration, set all existing rows to `"fast"`.

Expose mode on the conversation REST endpoints:
- `GET /api/chat/conversations` — include `mode` in response
- `GET /api/chat/conversations/{id}` — include `mode` in response
- `PATCH /api/chat/conversations/{id}` — accept `{ "mode": "analyst" }` to update mode

#### Frontend: `useNotebookMode` Hook

```typescript
// hooks/useNotebookMode.ts
function useNotebookMode(conversationId: string | null) {
  const [mode, setModeLocal] = useState<ChatMode>('fast');

  // Load mode when conversation changes
  useEffect(() => {
    if (!conversationId) return;
    API.get(`/api/chat/conversations/${conversationId}`)
      .then(r => setModeLocal(r.data.mode ?? 'fast'))
      .catch(() => {});
  }, [conversationId]);

  // Save mode to backend on change
  const setMode = useCallback(async (newMode: ChatMode) => {
    setModeLocal(newMode);
    if (conversationId) {
      await API.patch(`/api/chat/conversations/${conversationId}`, { mode: newMode });
    }
  }, [conversationId]);

  return { mode, setMode };
}
```

#### Frontend: ModePills

- Rename `normal` → `fast`, label "Fast" (icon: ⚡)
- Pills remain at top of the chat area in all modes
- Clicking a pill calls `setMode()` → layout re-renders immediately + API save in background

```typescript
// ModePills.tsx
export type ChatMode = 'fast' | 'deep_research' | 'analyst';

const MODE_OPTIONS = [
  { value: 'fast',          label: 'Fast',          icon: '⚡' },
  { value: 'deep_research', label: 'Deep Research', icon: '🔬' },
  { value: 'analyst',       label: 'Analyst',       icon: '📊' },
];
```

#### Frontend: Conditional Layout Rendering

Replace the hardcoded `ThreePaneLayout` usage in `LegalStudio.tsx` with mode-conditional rendering:

```typescript
if (mode === 'fast') {
  return <ChatOnlyLayout chatArea={chatArea} modePills={modePills} />;
}
if (mode === 'deep_research') {
  return <ChatWithResearchLayout chatArea={chatArea} researchPanel={researchPanel} modePills={modePills} />;
}
// analyst
return <ThreePaneLayout left={sourcesSidebar} center={chatArea} right={studioPanel} />;
```

**`ChatOnlyLayout`**: Single full-width column. No source sidebar, no studio panel. Chat fills the screen. ModePills at top.

**`ChatWithResearchLayout`**: Two columns — chat (flexible width) + research log panel (right, ~340px). See Sub-project B for research panel details.

**`ThreePaneLayout`**: Existing component, unchanged. Used only in Analyst mode.

---

### A2. Source UUID Resolution Fix

#### Problem

The `SourcesSidebar` displays `doc.filename` (UUID-based stored filename like `4af67c70-7caf.pdf`) instead of `doc.original_name` (the human-readable uploaded name like `Financial_Statements_2024.pdf`).

Chat message source citations show the same raw UUID filenames.

#### Fix: `useDocumentResolver` Hook

```typescript
// hooks/useDocumentResolver.ts
function useDocumentResolver(docs: SourceDoc[]) {
  const docMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const doc of docs) {
      map[doc.id] = doc.original_name;        // UUID id → original name
      map[doc.filename] = doc.original_name;  // stored UUID filename → original name
      map[doc.original_name] = doc.original_name; // passthrough
    }
    return map;
  }, [docs]);

  const resolve = useCallback((source: string): string => {
    return docMap[source] ?? source;
  }, [docMap]);

  return { resolve, docMap };
}
```

**Apply in `SourcesSidebar`:** Display `doc.original_name` directly (it already exists in the `SourceDoc` interface; just use it instead of `doc.filename`).

**Apply in `ChatMessages`:** When rendering source citations below a message, pass each source string through `resolve()` before display.

**Apply in `SourcePeeker`:** Title bar shows resolved name.

---

### A3. Source Citations: Show/Hide Logic

#### Rule

Source citations are shown below an LLM response only when the response is substantive. They are hidden when:
- Response content is empty
- Response contains phrases indicating no answer: *"I don't know"*, *"I couldn't find"*, *"no information available"*, *"not found in"*, *"I don't have"*
- The `sources` array is empty

#### Implementation

Add a helper `isSubstantiveAnswer(content: string, sources: Source[]): boolean` in `ChatMessages.tsx`:

```typescript
const NON_ANSWER_PHRASES = [
  "i don't know", "i couldn't find", "no information available",
  "not found in", "i don't have", "cannot find", "no relevant"
];

function isSubstantiveAnswer(content: string, sources: Source[]): boolean {
  if (!content?.trim()) return false;
  if (!sources?.length) return false;
  const lower = content.toLowerCase();
  return !NON_ANSWER_PHRASES.some(p => lower.includes(p));
}
```

Only render the sources block when `isSubstantiveAnswer(message.content, message.sources)` is `true`.

---

### A4. Deep Research Blank Screen Fix

#### Problem

Switching to `deep_research` mode renders a blank screen. The current codebase has no `ResearchPanel` or `DeepResearchLayout` component — the layout falls through to nothing.

#### Fix for Sub-project A

Render a placeholder `ResearchPanel` component so the screen is not blank:

```tsx
// components/studios/LegalStudio/ResearchPanel.tsx
export function ResearchPanel({ steps }: { steps: ResearchStep[] }) {
  return (
    <aside className="research-panel">
      <div className="research-panel__header">🔬 Research Log</div>
      {steps.length === 0 ? (
        <div className="research-panel__empty">
          Ask a question to begin deep research. Results and sources will appear here.
        </div>
      ) : (
        <ul className="research-steps">
          {steps.map((s, i) => <li key={i} className={`research-step research-step--${s.status}`}>{s.text}</li>)}
        </ul>
      )}
    </aside>
  );
}
```

Full Deep Research functionality (Tavily integration, live streaming steps) is completed in Sub-project B.

---

## Sub-Project B — Deep Research

### B1. Tavily Internet Search Integration

#### Backend: Tavily Search Service

```python
# core/research/tavily_search.py
import os
import httpx

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
TAVILY_URL = "https://api.tavily.com/search"

async def tavily_search(query: str, max_results: int = 5) -> list[dict]:
    """Return list of {title, url, content, score} from Tavily."""
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(TAVILY_URL, json={
            "api_key": TAVILY_API_KEY,
            "query": query,
            "search_depth": "advanced",
            "max_results": max_results,
            "include_answer": False,
        })
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])
```

Add `TAVILY_API_KEY` to `.env` and `config.py` settings.

#### Backend: Deep Research Endpoint

```
POST /api/chat/deep-research
{
  "conversation_id": "...",
  "query": "...",
  "selected_doc_ids": ["..."]
}
```

Returns a **Server-Sent Events (SSE) stream** so the frontend can display progress live. Each event is one of:

```
data: {"type": "step", "text": "Searching Tavily for: e-invoicing UAE 2025..."}
data: {"type": "step", "text": "Found 4 web results"}
data: {"type": "step", "text": "Searching RAG documents..."}
data: {"type": "step", "text": "Found 3 relevant document chunks"}
data: {"type": "step", "text": "Synthesizing answer..."}
data: {"type": "answer", "content": "...", "sources": [...], "web_sources": [...]}
data: {"type": "done"}
```

**Processing flow:**
1. Search Tavily with the user's query → get web results
2. Search RAG engine with the same query, filtered to `selected_doc_ids` → get doc chunks
3. Save fetched web content as new RAG documents (source: `"research"`) via existing `document_processor`
4. Send all context (web + RAG) to LLM with synthesis prompt
5. Stream the answer back

#### Frontend: Research Panel (Full)

`ResearchPanel` shows live streaming steps while research is in progress, then displays web sources with clickable links after the answer arrives:

```
🔬 Research Log
────────────────
✅ Searching: e-invoicing UAE...
✅ 4 web results found
✅ 3 document chunks found
✅ Synthesizing answer...

Web Sources
• Taxscape.ae — UAE E-Invoicing Guide 2025
• FTA.gov.ae — PEPPOL Implementation
```

---

## Sub-Project C — Analyst Mode

### C1. LLM Scoped to Attached Documents

When `mode === "analyst"`, the system prompt sent to the LLM is modified:

```python
ANALYST_SYSTEM_PREFIX = """
You are a financial and legal analyst. You MUST base your answers primarily on the documents provided below.
If the answer is clearly contained in the documents, cite the document and page.
If the answer is not in the documents, you may draw on your professional knowledge but must explicitly say:
"This is based on general knowledge, not your attached documents."
Do NOT make up figures, dates, or entities.
"""
```

This prefix is prepended to the system prompt when `conversation.mode == "analyst"`.

---

### C2. Audit Auto-Detection (No More Question Dialog)

#### Flow

1. User clicks **Run Audit** in the Studio panel
2. Frontend fires `POST /api/reports/detect` with `{ report_type: "audit", selected_doc_ids }`
3. Backend runs a targeted RAG search: *"company name entity name organization"* and *"financial year period end date reporting date"* against selected docs
4. Returns: `{ entity_name, period_end, confidence }` (confidence: `high | low | none`)
5. Frontend behavior by confidence:
   - **high** (≥ 0.7): Show a **non-blocking toast banner** at top of chat: *"Detected: ABC Trading LLC — FY ended 31 Dec 2024. [✅ Confirm & Run Audit] [✏️ Edit]"*
   - **low** (0.3–0.7): Same toast but with inline editable fields pre-filled
   - **none** (< 0.3): Show a minimal 2-field inline form (entity name + period end) in chat — no modal
6. User confirms → `POST /api/audit/run` fires with confirmed entity + period

---

### C3. Audit Overview: Draggable Persistent Overlay

#### Component: `<AuditOverlay>`

- Rendered as a **fixed-position** element in the DOM root (not inside chat scroll area)
- Position controlled by React state: `{ x, y }` initialized to bottom-right corner
- Draggable: `onPointerDown` on the header starts drag, `onPointerMove`/`onPointerUp` on window update position
- **Persists across navigation**: stored in React Context attached to the app root, not the page component. Navigating to Home and back does not unmount it.
- **Minimizable**: collapses to a `56×56px` pill at its current position showing "📊"
- **Content**: Summary text, Risk Flags (with severity badges), Anomalies, Compliance Gaps — all scrollable within the card

```tsx
// Overlay states
type OverlayState = 'full' | 'minimized' | 'closed';
```

CSS position: `position: fixed; z-index: 1000;` — overlays everything but is draggable out of the way.

---

### C4. MIS Report: Source-Grounded, Charts, Artifact Panel

#### MIS Generation Flow

1. User clicks "MIS Report" in Studio → frontend calls `POST /api/reports/generate` with `{ report_type: "mis", selected_doc_ids, format: "mis" }`
2. Backend:
   - Searches RAG for financial figures: revenue, expenses, profit, department breakdown
   - Structures extracted data into MIS sections
   - Returns structured JSON: `{ kpis: [...], chart_data: {...}, pl_table: [...], summary: "..." }`
3. Frontend renders result in the **Artifact Panel** (see C5)

#### MIS Artifact Panel Sections

1. **KPI Cards Row** — 4 cards: Revenue / Expenses / Net Profit / Gross Margin
2. **Charts** — Bar chart (Revenue vs Expenses by period) + Line chart (trend). Uses **Recharts** (add if not present: `npm install recharts`)
3. **Department P&L Table** — sortable table extracted from docs
4. **Narrative Summary** — LLM-generated paragraph, each claim tagged with source

All content is strictly from `selected_doc_ids`. System prompt: *"Extract data ONLY from the provided document chunks. Do not invent figures."*

---

### C5. Artifact Panel (Shared by MIS and Reports)

A reusable right-side panel that slides in over the Studio panel when a report or MIS is generated:

```
┌──────────────────────────────────────┐
│  📊 MIS Report — ABC Trading FY 2024  [Export PDF] [✕] │
├──────────────────────────────────────┤
│  KPI Cards                           │
│  Charts                              │
│  P&L Table                           │
│  Narrative Summary                   │
└──────────────────────────────────────┘
```

- Implemented as `<ArtifactPanel>` component, rendered inside the three-pane layout replacing the studio panel when active
- The main chat area stays visible on the left; artifact panel takes the right column
- Closing the panel returns to the Studio panel
- Export PDF uses `window.print()` scoped to the panel via a print stylesheet, or `html2pdf.js` if higher quality is needed

---

### C6. Reports: Smart Confirm Card + Instant Generation + Chat Refinement

#### Report Generation Flow

**Step 1 — User selects report type** in Studio panel (e.g., "ISA 700 Audit Report")

**Step 2 — Smart Confirm Card** appears in chat as a special message bubble:

```
📋 Ready to generate ISA 700 Audit Report
   Entity: ABC Trading LLC
   Period: FY ended 31 Dec 2024
   Documents: 3 in scope
   Format: Big 4 (auto-detected)
   
   [✅ Generate Report]  [✏️ Edit Details]
```

- Auto-detection uses `POST /api/reports/detect` with `{ report_type, selected_doc_ids }` — same endpoint used by Run Audit (which passes `report_type: "audit"`) and all other report types
- "Edit Details" expands the card to inline editable fields — no modal

**Step 3 — User clicks Generate** → `POST /api/reports/generate` fires → Artifact Panel opens immediately with a loading state → report streams in

**Step 4 — Chat Refinement**
After generation, the user can type follow-up instructions in the normal chat input:
- *"Add a going concern section"*
- *"Change format to Standard"*
- *"Make the executive summary shorter"*

These are sent as `role: "user"` messages with a system context indicating *"The artifact panel currently contains the following report... Apply the user's requested change and return the updated report."* The artifact panel updates with the revised content.

#### Available Report Types (from existing `reportConfigs.ts`)

MIS Report, Budget vs Actual, Forecasting, VAT Return (FTA VAT-201), Corporate Tax, Audit Report (ISA 700 Big 4), Board Report, IFRS Statements, Custom Report.

#### Auditor Formats (from existing `AuditorFormatGrid`)

Standard | Big 4 (Deloitte/PwC style) | Legal Brief | Compliance (SOX/GDPR) | Custom Template

Format is auto-detected from docs where possible (e.g., if doc mentions IFRS → suggest Big 4). User can override via the confirm card before generating.

---

## Architecture Summary

### New Files

```
frontend/src/
  hooks/
    useNotebookMode.ts          # mode persistence per conversation
    useDocumentResolver.ts      # UUID → original_name resolution
  components/studios/LegalStudio/
    ResearchPanel.tsx            # deep research log (Sub-project A placeholder, B full)
    AuditOverlay.tsx             # draggable persistent audit overview
    ArtifactPanel.tsx            # shared MIS + report right-side panel
    ChatOnlyLayout.tsx           # fast mode single-panel layout
    ChatWithResearchLayout.tsx   # deep research two-panel layout
    ConfirmReportCard.tsx        # smart confirm card message bubble

backend/
  core/research/
    tavily_search.py             # Tavily API client
  api/
    research.py                  # POST /api/chat/deep-research SSE endpoint
    reports.py                   # POST /api/reports/detect, /generate
  db/migrations/
    add_conversation_mode.py     # Alembic migration: add mode column
```

### Modified Files

```
frontend/src/
  components/studios/LegalStudio/
    ModePills.tsx                # rename normal→fast, update ChatMode type
    LegalStudio.tsx              # use useNotebookMode, conditional layout render
    ChatMessages.tsx             # isSubstantiveAnswer, resolve source names
    SourcesSidebar.tsx           # display original_name instead of filename
    SourcePeeker.tsx             # resolve source name in title
  
backend/
  db/models.py                   # add mode column to Conversation
  api/chat.py                    # include mode in conversation responses, PATCH mode
  config.py                      # add TAVILY_API_KEY setting
```

---

## Environment Variables

Add to `.env` for Sub-project B:

```
TAVILY_API_KEY=tvly-xxxxxxxxxxxx
```

---

## Testing Checklist

### Sub-project A
- [ ] Switching mode pills updates layout immediately
- [ ] Mode persists after page reload (DB-backed)
- [ ] Source sidebar shows `original_name`, not UUID filename
- [ ] Source citations in chat show resolved names
- [ ] Sources hidden when LLM responds with "I don't know"
- [ ] Deep Research mode no longer shows blank screen

### Sub-project B
- [ ] Deep research fires Tavily search and shows steps live in research panel
- [ ] Web sources appear in research panel after answer
- [ ] Fetched web content is saved to RAG DB with `source: "research"`
- [ ] RAG sources with page references appear alongside web sources

### Sub-project C
- [ ] Run Audit auto-detects entity + period; no dialog shown
- [ ] Audit overlay is draggable and doesn't cover chat by default
- [ ] Audit overlay persists after navigating to Home and back
- [ ] MIS report is grounded in attached docs (no generic content)
- [ ] MIS artifact panel shows KPI cards + charts + P&L table
- [ ] Report confirm card shows auto-detected entity/period/format
- [ ] Report generates into artifact panel immediately on confirm
- [ ] Follow-up chat messages update the artifact panel content
