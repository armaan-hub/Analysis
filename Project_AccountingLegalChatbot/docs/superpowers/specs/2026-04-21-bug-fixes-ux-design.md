# Bug Fixes & UX Improvements — April 21 2026

Scope: fixes for bugs discovered during live testing on April 20-21. Organized into three priority tiers. All changes are model-agnostic — no provider lock-in.

---

## Tier 1 — Crash / Data Loss Fixes

### 1.1 Session Persistence

**Problem**: Navigating away from a notebook and back loses all chat history, generated reports, and sources. React component unmounts → all `useState` is discarded.

**Root cause**: `LegalStudio.tsx` has no load-on-mount logic. The backend already has both endpoints needed.

**Fix**:

Add a `useEffect` in `LegalStudio.tsx` that fires when `conversationId` is set or changes:

```ts
useEffect(() => {
  if (!conversationId) return;
  // Load messages
  API.get(`/api/chat/conversations/${conversationId}/messages`)
    .then(r => setMessages(r.data ?? []));
  // Load sources
  API.get(`/api/legal-studio/notebook/${conversationId}/sources`)
    .then(r => setDocs(r.data ?? []));
}, [conversationId]);
```

Also ensure sources are written back to DB when user adds/removes documents. Currently `checked_source_ids` may not be persisted on every change — add a `PATCH /api/legal-studio/notebook/{id}/sources` call on `selectedDocIds` change.

**Files**:
- `frontend/src/components/studios/LegalStudio/LegalStudio.tsx` — add load useEffect
- `backend/api/legal_studio.py` — add/confirm PATCH sources endpoint

---

### 1.2 Chat Messages Disappearing on Repeated Questions

**Problem**: Sending a follow-up question causes previous messages/answers to disappear. Deep research mode clears the screen before the new result arrives.

**Root cause**: Two separate state systems in `LegalStudio.tsx`:
- `messages[]` — for normal mode
- `researchPhases[]` + `researchReport` — for deep research mode

On a new deep research query, `researchReport` is cleared immediately (set to `null`) before the new result arrives → blank screen. On repeated normal queries there may be a race condition resetting `messages[]` via a stale closure.

**Fix**: Unify into one message list. Deep research results become a special message entry:

```ts
type Message =
  | { role: 'user' | 'assistant'; content: string; sources?: Source[] }
  | { role: 'research'; phases: ResearchPhase[]; report: string | null; sources: Source[]; query: string }
```

Append to `messages[]` — never replace. Clear only `researchPhases`/`researchReport` transient state, never the accumulated message history.

`ChatMessages.tsx` renders the `research` role using `ResearchBubble`. Normal roles render as before.

**Files**:
- `frontend/src/components/studios/LegalStudio/LegalStudio.tsx` — unify message state
- `frontend/src/components/studios/LegalStudio/ChatMessages.tsx` — handle `research` role
- `frontend/src/lib/api.ts` — extend `Message` type

---

### 1.3 Answers Hidden / Overflow in Chat Areas

**Problem**: Generated answers are hidden or cut off in Analyst mode, Legal Studio, and AuditChat. Content grows beyond container bounds and gets clipped.

**Root cause**: Chat scroll containers missing `overflow-y: auto` and/or `flex: 1 1 0` height constraint. Without explicit height, flex children expand to content size and overflow silently.

**Fix**: Apply to all three studios' main chat scroll wrapper:

```ts
// Chat scroll container style
{ display: 'flex', flexDirection: 'column', flex: '1 1 0', overflowY: 'auto', minHeight: 0 }
```

The `minHeight: 0` is required — without it, flex items ignore the `flex: 1` shrink and still overflow.

**Files**:
- `frontend/src/components/studios/LegalStudio/ThreePaneLayout.tsx` — chat pane scroll
- `frontend/src/components/studios/FinanceStudio/FinanceStudio.tsx` — analyst chat area
- `frontend/src/components/studios/FinanceStudio/AuditChat/AuditChat.tsx` — audit chat area

---

## Tier 2 — Correctness Fixes

### 2.1 Deep Research Hallucination

**Problem**: Deep Research mode generates generic clarifying questions as sub-questions, then searches those → garbage RAG/web results → hallucinated synthesis.

Example of current broken output from `_plan()`:
```
["What specific aspect of the topic are you interested in?",
 "Are you looking for general information or detailed analysis?",
 "Do you have prior knowledge about this topic?"]
```

**Root cause**: `_plan()` system prompt in `backend/core/research/orchestrator.py` is ambiguous. LLM interprets it as "ask user for clarification" rather than "decompose into factual search queries".

**Fix — Part A**: Rewrite `_plan()` system prompt with explicit constraint + few-shot example:

```python
system = (
    "You are a research planner specializing in UAE legal and financial topics. "
    "Your job is to decompose a research query into 3-5 SPECIFIC, FACTUAL sub-questions "
    "that can be answered by searching documents and the web.\n\n"
    "RULES:\n"
    "- Sub-questions must be about the TOPIC, not about what the user wants\n"
    "- Never ask clarifying questions like 'what aspect?' or 'general or detailed?'\n"
    "- Each sub-question must be independently searchable\n\n"
    "EXAMPLE INPUT: 'Peppol e-invoicing buyer ID for third party shipment UAE'\n"
    "EXAMPLE OUTPUT: {\"sub_questions\": [\n"
    "  \"Who must register for Peppol participant ID in UAE e-invoicing?\",\n"
    "  \"What is the Peppol BIS billing standard for third-party shipment scenarios?\",\n"
    "  \"UAE FTA e-invoicing requirements for buyer identification in cross-border transactions\"\n"
    "]}\n\n"
    "Respond ONLY with valid JSON: {\"sub_questions\": [\"q1\", \"q2\", ...]}"
)
```

**Fix — Part B**: Add validation after parsing. If any sub-question matches generic patterns → discard all, fall back to `[query]`:

```python
GENERIC_PATTERNS = [
    "what aspect", "general or detailed", "prior knowledge",
    "interested in learning", "specific topic", "what type of information",
    "what would you like", "are you looking for",
]

def _is_generic(q: str) -> bool:
    ql = q.lower()
    return any(p in ql for p in GENERIC_PATTERNS)

# After parsing sub_questions:
if any(_is_generic(q) for q in sub_questions):
    sub_questions = [query]  # fall back to original query
```

**Files**:
- `backend/core/research/orchestrator.py` — rewrite `_plan()` + add `_is_generic()` validation

---

### 2.2 Domain System Prompt Improvements (Model-Agnostic Tuning)

**Problem**: LLM produces hallucinated answers with fabricated citations. Fine-tuning is provider-specific and not portable. Need improvements that transfer across NVIDIA → Anthropic → OpenAI.

**Approach**: Enhance system prompts in `backend/core/prompt_router.py` with:
1. Explicit grounding rules (no fabrication)
2. One few-shot Q&A example per domain
3. Citation format instruction

**Grounding rules block** (add to ALL domain prompts):
```
RULES:
- Answer ONLY from the provided context and your verified knowledge of UAE law
- If the context does not contain enough information, say "I don't have enough context to answer this accurately"
- Never fabricate UAE law article numbers, decree numbers, or monetary thresholds
- Always state which decree/law/standard your answer is based on
```

**Few-shot examples** — add one per domain:

| Domain | Example Q | Example A snippet |
|--------|-----------|-------------------|
| `vat` | VAT on residential rental? | Exempt under Art 46(1)(b) Federal Decree-Law 8/2017 |
| `corporate_tax` | CT rate for small business? | 0% if taxable income ≤ AED 375,000 (Small Business Relief) |
| `audit` | ISA 315 scope? | Identifying and assessing risks of material misstatement |
| `aml` | STR filing deadline UAE? | Within 30 days of suspicion under CBUAE regulation |
| `peppol` | Peppol UBL version for UAE? | UBL 2.1 per FTA e-invoicing technical specs |
| `finance` | IFRS 15 revenue recognition criteria? | 5-step model — identify contract, PO, transaction price, allocate, recognize |

**Files**:
- `backend/core/prompt_router.py` — add grounding block + few-shot examples to each domain

---

### 2.3 MIS Report Raw Markdown Rendering

**Problem**: MIS Report output displays raw markdown (`**bold**`, `## headings`, `| table |`) as plain text instead of rendered HTML.

**Root cause**: FinanceStudio analyst chat message bubbles render content as plain text. `ResearchBubble` already uses `ReactMarkdown` correctly — same pattern not applied to report output in FinanceStudio.

**Fix**: Wrap assistant/report message content in `ReactMarkdown`:

```tsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// In analyst message bubble:
<div className="report-markdown">
  <ReactMarkdown remarkPlugins={[remarkGfm]}>
    {message.content}
  </ReactMarkdown>
</div>
```

Add `.report-markdown table` CSS for styled tables (borders, alternating rows).

**Files**:
- `frontend/src/components/studios/FinanceStudio/FinanceStudio.tsx` — add ReactMarkdown to analyst response bubble
- `frontend/src/index.css` (or equivalent) — add `.report-markdown` table styles

---

### 2.4 Entity Name Auto-Extraction (MIS Report)

**Problem**: MIS Report questionnaire asks user to type Entity Name. Users should not need to type what is already in their uploaded documents.

**Fix**: Make Entity Name field optional in the questionnaire. If left blank:
1. Backend checks `Conversation.checked_source_ids` for source documents
2. Runs a lightweight LLM call: `"Extract the company/entity name from this document. Respond with only the name."`
3. Uses extracted name in report generation

Add helper function in `backend/api/legal_studio.py` or `backend/services/report_service.py`:

```python
async def extract_entity_name(source_ids: list[str], db: AsyncSession) -> str | None:
    # Fetch first source doc text snippet
    # Run quick LLM extraction
    # Return name or None
```

Frontend: show entity name field with placeholder "Auto-detected from sources" and grey italic text if auto-extracted.

**Files**:
- `backend/api/legal_studio.py` — add `extract_entity_name()` helper
- `frontend/src/components/studios/LegalStudio/QuestionnaireMessage.tsx` — make entity field optional + show auto-detected value

---

## Tier 3 — UX Polish

### 3.1 Notebook Card Hover Delete Bug

**Problem**: Delete icon disappears before user can click it when moving mouse toward it.

**Root cause**: Delete button `position: absolute` positioned relative to nearest positioned ancestor. If `.notebook-card` CSS class lacks `position: relative`, button floats outside card's DOM bounding box. Moving mouse to button triggers `onMouseLeave` on the card div → `hovered=false` → button opacity 0 → unclickable.

**Fix** in `NotebookCard.tsx`:
1. Add `position: 'relative'` to card outer div inline style (not relying on CSS class)
2. Add `onMouseEnter={() => setHovered(true)}` to the delete button itself — prevents hover cancel when cursor reaches it

```tsx
<div
  style={{ ...cardStyle, position: 'relative' }}
  onMouseEnter={() => setHovered(true)}
  onMouseLeave={() => setHovered(false)}
>
  ...
  <button
    onMouseEnter={() => setHovered(true)}  // keep hover alive
    style={deleteBtnStyle}
    onClick={handleDelete}
  >
    <Trash2 size={16} />
  </button>
</div>
```

**Files**:
- `frontend/src/components/common/NotebookCard.tsx` — add position + button onMouseEnter

---

### 3.2 Multi-Select + Bulk Delete

**Problem**: Can only delete one notebook at a time. No way to select and delete multiple.

**Design**:

`HomePage.tsx` additions:
- `selectionMode: boolean` state — toggle via "Select" button in toolbar
- `selectedIds: Set<string>` state
- When `selectionMode=true`: toolbar shows "Delete (N)" danger button instead of view toggle
- Clicking outside any card → deselects all

`NotebookCard.tsx` additions:
- `selected?: boolean` prop — shows blue checkbox overlay on thumbnail when true
- `onSelect?: (id: string) => void` prop — fires on click when `selectionMode=true` (instead of navigate)
- Visual: selected card gets `outline: 2px solid var(--s-accent)` on thumbnail

Bulk delete flow:
```ts
const handleBulkDelete = async () => {
  await Promise.all([...selectedIds].map(id =>
    API.delete(`/api/legal-studio/notebook/${id}`)
  ));
  setNotebooks(prev => prev.filter(n => !selectedIds.has(n.id)));
  setSelectedIds(new Set());
  setSelectionMode(false);
};
```

Confirmation modal: "Delete 3 notebooks? This cannot be undone."

**Files**:
- `frontend/src/pages/HomePage.tsx` — selection state + bulk delete
- `frontend/src/components/common/NotebookCard.tsx` — selected prop + checkbox UI

---

### 3.3 Domain Icons Instead of 2-Letter Initials

**Problem**: All notebook thumbnails show 2-letter initials (e.g., "TE", "LE"). Hard to distinguish notebook type visually.

**Design**:

Backend: Add `domain` column to `Conversation` model (nullable string). Populate from `classifier_result.domain` on first message of each conversation. Expose in `GET /api/chat/conversations` response.

Frontend icon map in `NotebookCard.tsx`:
```ts
import { Scale, BarChart2, ClipboardCheck, Receipt, Building2, Shield, BookOpen, FileText } from 'lucide-react';

const DOMAIN_ICONS: Record<string, React.ElementType> = {
  legal: Scale,
  finance: BarChart2,
  audit: ClipboardCheck,
  vat: Receipt,
  corporate_tax: Building2,
  aml: Shield,
  general: BookOpen,
  default: FileText,
};
```

Render: when `notebook.domain` is set → show icon (24px, white). When not set → fall back to 2-letter initials.

`Notebook` interface in `NotebookCard.tsx`:
```ts
interface Notebook {
  id: string;
  title: string;
  updated_at: string;
  source_count?: number;
  domain?: string;  // add this
}
```

**Files**:
- `backend/db/models.py` — add `domain` column to `Conversation`
- `backend/api/chat.py` — store `classifier_result.domain` on new conversation
- `backend/api/chat.py` — expose `domain` in `ConversationResponse`
- `frontend/src/components/common/NotebookCard.tsx` — add domain icon rendering

---

### 3.4 Auditor Format / Custom Template Wire-Up

**Problem**: Selecting "Custom Template" in AuditorFormatGrid does nothing — cannot generate report in custom auditor format.

**Root cause**: `AuditorFormatGrid` selection state likely not propagated to the API call payload. `auditor_format` param may be missing or ignored by backend.

**Fix**:
1. Verify `AuditorFormatGrid` selection fires `onFormatChange` callback in `StudioPanel.tsx`
2. Verify `StudioPanel` passes selected format to report generation API call as `auditor_format`
3. Verify `backend/api/audit_studio.py` reads and applies `auditor_format` to report output
4. For `custom_template`: load user's saved templates from `GET /api/templates/`, let user pick one, pass `template_id` to audit API

**Files**:
- `frontend/src/components/studios/LegalStudio/AuditorFormatGrid.tsx` — verify callback
- `frontend/src/components/studios/LegalStudio/StudioPanel.tsx` — wire format to API call
- `backend/api/audit_studio.py` — verify `auditor_format` param handling

---

## Implementation Order

```
Tier 1.3 (overflow fix)          — 30 min, immediate visual relief
Tier 1.1 (session persistence)   — 2 hrs, eliminates data loss
Tier 1.2 (message unification)   — 2 hrs, eliminates disappearing messages
Tier 2.1 (orchestrator fix)      — 1 hr, eliminates hallucination
Tier 2.2 (prompt engineering)    — 2 hrs, improves answer quality
Tier 2.3 (markdown rendering)    — 30 min, MIS report readable
Tier 2.4 (entity extraction)     — 1 hr, removes friction
Tier 3.1 (hover fix)             — 15 min
Tier 3.2 (multi-select)          — 1.5 hrs
Tier 3.3 (domain icons)          — 1 hr
Tier 3.4 (auditor format)        — 1 hr
```

Total estimated effort: ~13 hours of implementation.

---

## Model Portability Note

All LLM improvements in this spec (Tier 2.1, 2.2) are stored in Python prompt strings — no weights, no fine-tuning. Switching from NVIDIA free → Anthropic Claude → OpenAI GPT-4 requires only updating `LLM_PROVIDER` in `.env`. All prompt improvements transfer automatically.
