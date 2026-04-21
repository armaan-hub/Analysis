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

Full Deep Research functionality (Brave Search integration, live streaming steps) is completed in Sub-project B.

---

## Sub-Project B — Deep Research

### B1. Search Engine: Brave Search API (Free)

**Why Brave:** 2,000 free queries/month, structured JSON results, no API key approval friction, designed for programmatic use.

Add `BRAVE_SEARCH_API_KEY` to `.env` and `config.py`.

```python
# core/research/brave_search.py
import os, httpx

BRAVE_API_KEY = os.environ.get("BRAVE_SEARCH_API_KEY", "")
BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"

async def brave_search(query: str, max_results: int = 5) -> list[dict]:
    """Return list of {title, url, description} from Brave Search."""
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(BRAVE_URL,
            headers={"Accept": "application/json", "X-Subscription-Token": BRAVE_API_KEY},
            params={"q": query, "count": max_results, "text_decorations": False},
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {"title": r.get("title"), "url": r.get("url"), "content": r.get("description", "")}
            for r in data.get("web", {}).get("results", [])
        ]
```

---

### B2. LLM Query Decomposition Skill

Before executing any search, an internal LLM call decomposes the user's query into 2-3 focused search sub-queries targeting the most important aspects. This produces fewer, more precise searches — reducing API usage and improving result quality.

```python
# core/research/query_decomposer.py

DECOMPOSE_PROMPT = """
You are a search query expert. Given the user's question, generate 2-3 focused web search queries
that together cover the most important aspects needed to fully answer the question.

Rules:
- Each query should target a distinct, specific aspect
- Keep queries concise (3-7 words)
- Use domain-specific terminology when relevant (e.g., "UAE FTA", "IFRS 15", "ISA 700")
- Output ONLY a JSON array of strings: ["query 1", "query 2", "query 3"]

User question: {question}
"""

async def decompose_query(question: str, llm_client) -> list[str]:
    """Use LLM to break question into 2-3 targeted search queries."""
    response = await llm_client.complete(
        DECOMPOSE_PROMPT.format(question=question),
        max_tokens=150,
        temperature=0.1,
    )
    import json
    try:
        queries = json.loads(response.strip())
        return queries[:3] if isinstance(queries, list) else [question]
    except Exception:
        return [question]  # fallback to original query
```

---

### B3. Deep Research Endpoint

```
POST /api/chat/deep-research
{
  "conversation_id": "...",
  "query": "...",
  "selected_doc_ids": ["..."]
}
```

Returns a **Server-Sent Events (SSE) stream** for live progress display. Event types:

```
data: {"type": "step", "text": "Analyzing query..."}
data: {"type": "step", "text": "Generated 3 search queries"}
data: {"type": "step", "text": "Searching: UAE e-invoicing PEPPOL mandate 2025"}
data: {"type": "step", "text": "Searching: FTA e-invoicing compliance requirements UAE"}
data: {"type": "step", "text": "Searching: UAE Decree-Law e-invoicing penalties"}
data: {"type": "step", "text": "Found 12 web results across 3 searches"}
data: {"type": "step", "text": "Searching your documents..."}
data: {"type": "step", "text": "Found 5 relevant document chunks"}
data: {"type": "step", "text": "Synthesizing answer..."}
data: {"type": "answer", "content": "...", "sources": [...], "web_sources": [...]}
data: {"type": "done"}
```

**Processing flow:**
1. Call `decompose_query()` → get 2-3 focused sub-queries
2. Execute all Brave searches in parallel (asyncio.gather) → aggregate web results
3. Search RAG engine with the original query, filtered to `selected_doc_ids` → get doc chunks
4. Save fetched web content as new RAG documents (source: `"research"`) via existing `document_processor` for future reference
5. Build synthesis prompt: web results + doc chunks + original question
6. Stream LLM answer back via SSE

---

### B4. Frontend: Research Panel (Full)

`ResearchPanel` shows live streaming steps, then collapses to a source list after the answer arrives:

```
🔬 Research Log
────────────────
✅ Generated search queries
✅ Searched: "UAE e-invoicing PEPPOL..."
✅ Searched: "FTA compliance requirements..."
✅ Searched: "UAE e-invoicing penalties..."
✅ 12 web results · 5 doc chunks
✅ Answer ready

Web Sources
• Taxscape.ae — UAE E-Invoicing Guide 2025
• FTA.gov.ae — PEPPOL Implementation Details
• PWC.com — UAE Digital Tax Landscape

Document Sources
• Financial_Policy.pdf — p.4
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

### C4. Report Config System — All Report Types

Every report type is defined in `reportConfigs.ts` as a `ReportConfig` object. This drives the entire generation pipeline — what data to extract, what sections to render, what formats apply, and what regulatory rules to follow.

```typescript
// reportConfigs.ts
interface ReportSection {
  id: string;
  label: string;
  type: 'kpi_cards' | 'chart' | 'table' | 'narrative' | 'regulatory_form' | 'signature_block';
  extractionPrompt: string;  // what to ask RAG for this section
  required: boolean;
}

interface ReportConfig {
  id: string;
  label: string;
  icon: string;
  category: 'financial' | 'regulatory' | 'audit' | 'custom';
  sections: ReportSection[];
  supportedFormats: AuditorFormat[];
  detectFields: string[];       // fields to auto-detect from docs (e.g. entity_name, period_end)
  regulatoryNote?: string;      // e.g. "Based on UAE FTA VAT-201 form structure"
  chartTypes?: string[];        // e.g. ['bar', 'line'] — empty means no charts
}
```

**All 9 report types configured:**

| Report | Category | Charts | Key Sections |
|--------|----------|--------|-------------|
| MIS Report | financial | bar + line | KPI cards, Dept P&L, trends, narrative |
| Budget vs Actual | financial | bar (variance) | Budget table, actual table, variance %, commentary |
| Forecasting | financial | line (projection) | Historical trend, 3/6/12-month forecast, assumptions |
| Board Report | financial | summary KPIs | Executive summary, financial highlights, risks, decisions needed |
| IFRS Statements | financial | none | Statement of Financial Position, P&L, Cash Flow, Notes (IFRS-referenced) |
| VAT Return (FTA VAT-201) | regulatory | none | Box 1-9 of VAT-201 form: standard-rated, zero-rated, exempt, input tax, payable |
| Corporate Tax | regulatory | none | Taxable income computation, Small Business Relief check, CT payable |
| Audit Report (ISA 700) | audit | none | Basis, Opinion paragraph, Key Audit Matters, Going Concern, Signature |
| Custom Report | custom | optional | User-defined sections — prompted interactively |

#### MIS-Specific Sections

1. **KPI Cards Row** — Revenue, Expenses, Net Profit, Gross Margin (extracted from docs)
2. **Charts** — Bar (Revenue vs Expenses by period) + Line (trend). Uses **Recharts** (`npm install recharts` if not present)
3. **Department P&L Table** — sortable, from attached docs
4. **Narrative Summary** — source-tagged LLM paragraph

#### VAT Return (FTA VAT-201) Specific

The VAT-201 form has fixed boxes. The LLM extracts values from attached accounting docs and maps them to form boxes:

- **Box 1** — Standard-rated supplies (AED)
- **Box 2** — Zero-rated supplies (AED)  
- **Box 3** — Exempt supplies (AED)
- **Box 4** — Goods imported into UAE
- **Box 5** — Adjustments
- **Box 6** — Total value of supplies
- **Box 7** — Total value of taxable supplies (VAT amount due)
- **Box 8** — Recoverable input tax
- **Box 9** — Payable / Reclaimable net VAT

Each box shows the extracted value + the source document/page it came from.

#### Audit Report (ISA 700) Specific

Sections follow the ISA 700 Big 4 structure:
1. **Independent Auditor's Report** heading
2. **Opinion** — unmodified/modified (LLM determines based on doc findings)
3. **Basis for Opinion** — what was audited, standards applied
4. **Key Audit Matters** — LLM identifies from doc contents (going concern, significant estimates, etc.)
5. **Responsibilities** — management vs auditor
6. **Signature block** — firm name, date, location (auto-detected or editable)

#### Corporate Tax Specific

Follows UAE CT Decree-Law 47 structure:
1. Accounting profit (from docs)
2. Non-deductible adjustments
3. Exempt income
4. Taxable income
5. Small Business Relief eligibility check (revenue < AED 3M)
6. CT payable at 9% (or 0% if SBR applies)

#### Custom Report

When user selects Custom Report:
- A short interactive prompt appears in chat: *"Describe the sections you want in your report (e.g. 'Executive summary, cash flow analysis, risk register, recommendations')"*
- User types the structure they want
- LLM builds a `ReportConfig` on the fly with those sections and generates accordingly

All reports: system prompt enforces *"Extract data ONLY from the provided document chunks. Do not invent figures, names, or dates."*

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
    brave_search.py              # Brave Search API client (free, 2000/month)
    query_decomposer.py          # LLM query decomposition: 1 question → 2-3 search queries
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
  config.py                      # add BRAVE_SEARCH_API_KEY setting
```

---

## Environment Variables

Add to `.env` for Sub-project B:

```
BRAVE_SEARCH_API_KEY=BSA-xxxxxxxxxxxx
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
- [ ] Deep research fires Brave Search and shows steps live in research panel
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
