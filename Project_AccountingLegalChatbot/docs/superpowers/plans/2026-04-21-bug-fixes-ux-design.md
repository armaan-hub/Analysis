# Bug Fixes & UX Improvements — April 21 2026 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 11 bugs across 3 priority tiers — crash/data-loss fixes first, correctness second, UX polish third.

**Architecture:** Frontend is React + TypeScript in `frontend/src/`. Backend is FastAPI + SQLAlchemy (async) in `backend/`. Shared types live in `frontend/src/lib/api.ts`. All changes are isolated to individual components / API modules — no cross-cutting refactors.

**Tech Stack:** React 18, TypeScript, Vite, ReactMarkdown + remark-gfm, Python 3.11, FastAPI, SQLAlchemy async, SQLite (dev).

**Spec file:** `docs/superpowers/specs/2026-04-21-bug-fixes-ux-design.md`

---

## Implementation Order

1. Task 1 — 1.3 Chat overflow (quick CSS, 30 min)
2. Task 2 — 1.2 Message state unification (foundation for persistence)
3. Task 3 — 1.1 Session persistence (built on unified state)
4. Task 4 — 2.1 Research orchestrator (eliminate hallucination)
5. Task 5 — 2.2 Prompt grounding (improve answer quality)
6. Task 6 — 2.3 MIS markdown rendering (readability)
7. Task 7 — 2.4 Entity name extraction (remove friction)
8. Task 8 — 3.1 Notebook card hover fix (15 min)
9. Task 9 — 3.2 Multi-select bulk delete
10. Task 10 — 3.3 Domain icons
11. Task 11 — 3.4 Auditor format wire-up (verify-first)

---

## Task 1: Chat Overflow Fix (1.3)

**Problem:** Chat content clips silently — missing `flex: '1 1 0'`, `overflowY: 'auto'`, `minHeight: 0` on scroll containers.

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/ThreePaneLayout.tsx`
- Modify: `frontend/src/components/studios/FinanceStudio/FinanceStudio.tsx`
- Modify: `frontend/src/components/studios/FinanceStudio/AuditChat/AuditChat.tsx`

- [ ] **Step 1: Fix ThreePaneLayout center pane**

In `frontend/src/components/studios/LegalStudio/ThreePaneLayout.tsx`, update the center wrapper:

```tsx
export function ThreePaneLayout({ left, center, right }: Props) {
  return (
    <div className="three-pane-layout">
      {left}
      <div
        className="three-pane-layout__center"
        style={{ display: 'flex', flexDirection: 'column', flex: '1 1 0', overflowY: 'auto', minHeight: 0 }}
      >
        {center}
      </div>
      {right}
    </div>
  );
}
```

- [ ] **Step 2: Fix FinanceStudio AuditChat section**

In `frontend/src/components/studios/FinanceStudio/FinanceStudio.tsx`, find the AuditChat section div (currently `<div>` wrapping `PanelHeader + AuditChat`) and add scroll style:

```tsx
<section className="finance-studio__center">
  <div style={{ display: 'flex', flexDirection: 'column', flex: '1 1 0', overflowY: 'auto', minHeight: 0 }}>
    <PanelHeader icon={<MessageSquare size={18} />} title="Chat" />
    <AuditChat />
  </div>
  <div>
    <PanelHeader icon={<Eye size={18} />} title="Preview" />
    <ReportPreview />
  </div>
</section>
```

- [ ] **Step 3: Fix AuditChat messages container**

In `frontend/src/components/studios/FinanceStudio/AuditChat/AuditChat.tsx`, update the messages div:

```tsx
<div
  className="audit-chat__messages"
  style={{ flex: '1 1 0', overflowY: 'auto', minHeight: 0 }}
>
  {chatHistory.map(m => <ChatMessage key={m.id} msg={m} />)}
  {chatLoading && <div className="chat-msg chat-msg--loading">Thinking…</div>}
</div>
```

- [ ] **Step 4: Verify visually**

Start the dev server (`cd frontend && npm run dev`), open AuditChat and LegalStudio, send a long response. Confirm content scrolls instead of clipping.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/ThreePaneLayout.tsx \
        frontend/src/components/studios/FinanceStudio/FinanceStudio.tsx \
        frontend/src/components/studios/FinanceStudio/AuditChat/AuditChat.tsx
git commit -m "fix: chat overflow — add flex+overflow to all studio scroll containers

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: Message State Unification (1.2)

**Problem:** `researchReport` cleared to `null` on new deep research before result arrives → blank screen. Two state systems cause race conditions.

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`
- Modify: `frontend/src/components/studios/LegalStudio/ChatMessages.tsx`

- [ ] **Step 1: Add ResearchMessage type to api.ts**

In `frontend/src/lib/api.ts`, extend the `Message` interface into a discriminated union:

```ts
export interface TextMessage {
  role: 'user' | 'ai' | 'assistant';
  text: string;
  time: string;
  sources?: Source[];
  id?: string;
  messageId?: string;
  queriesRun?: string[];
  isResearching?: boolean;
}

export interface ResearchMessage {
  role: 'research';
  id: string;
  query: string;
  phases: Array<{ phase: string; message: string; sub_questions?: string[]; progress?: number; total?: number; report?: string }>;
  report: string | null;
  sources: Source[];
  time: string;
}

export type Message = TextMessage | ResearchMessage;
```

> Note: All existing code referencing `msg.role === 'user'` or `msg.role === 'ai'` still works — those are cases of `TextMessage`. Only `ChatMessages.tsx` and `LegalStudio.tsx` need to handle the new `'research'` branch.

- [ ] **Step 2: Remove separate research state from LegalStudio.tsx**

In `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`:

Remove these state declarations (lines ~64-71):
```ts
// DELETE these:
const [researchPhases, setResearchPhases] = useState<...>([]);
const [researchReport, setResearchReport] = useState<string | null>(null);
const [researching, setResearching] = useState(false);
const [researchQuery, setResearchQuery] = useState<string>('');
const [researchSources, setResearchSources] = useState<Source[]>([]);
```

Add a single `researching` flag (for loading indicator only):
```ts
const [researching, setResearching] = useState(false);
```

- [ ] **Step 3: Update deep research send handler to append ResearchMessage**

Still in `LegalStudio.tsx`, replace the deep research branch inside `sendMessage` (~lines 337-366):

```ts
if (mode === 'deep_research') {
  setResearching(true);
  // Create a placeholder research message in the unified list
  const researchId = crypto.randomUUID();
  const researchMsg: ResearchMessage = {
    role: 'research',
    id: researchId,
    query: text,
    phases: [],
    report: null,
    sources: [],
    time: fmtTime(),
  };
  setMessages(prev => [...prev, researchMsg]);

  try {
    const res = await API.post('/api/legal-studio/research', { query: text });
    const jobId = res.data.job_id;
    const evtSource = new EventSource(`${API_BASE}/api/legal-studio/research/${jobId}/stream`);
    evtSource.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (!data.phase) return;
      if (data.phase === 'completed') {
        setMessages(prev => prev.map(m =>
          m.id === researchId
            ? { ...m, report: data.report ?? '', sources: data.sources ?? [] } as ResearchMessage
            : m
        ));
        setResearching(false);
        setLoading(false);
        evtSource.close();
        return;
      }
      setMessages(prev => prev.map(m =>
        m.id === researchId
          ? { ...m, phases: [...(m as ResearchMessage).phases, data] } as ResearchMessage
          : m
      ));
    };
    evtSource.onerror = () => { evtSource.close(); setResearching(false); setLoading(false); };
  } catch {
    setResearching(false);
    setLoading(false);
  }
  return;
}
```

- [ ] **Step 4: Update the auto-scroll effect**

Replace the research-specific auto-scroll effect (which referenced `researchReport` and `researchPhases`) with one that fires on any `messages` change:

```ts
// Auto-scroll to bottom whenever messages update
useEffect(() => {
  chatAreaBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
}, [messages]);
```

Remove the old effect:
```ts
// DELETE this effect:
useEffect(() => {
  if (researchReport || researchPhases.length > 0) {
    chatAreaBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }
}, [researchReport, researchPhases]);
```

- [ ] **Step 5: Update the JSX rendering in LegalStudio.tsx**

Remove the standalone `ResearchBubble` block (~lines 564-574):
```tsx
// DELETE this block:
{(researching || researchReport) && (
  <div className="legal-section-pad">
    <ResearchBubble
      phases={researchPhases}
      report={researchReport}
      sources={researchSources}
      query={researchQuery}
      onSourceClick={handleSourceClick}
    />
  </div>
)}
```

`ChatMessages.tsx` will now render `ResearchMessage` entries inline (see next step).

- [ ] **Step 6: Update ChatMessages.tsx to render research role**

In `frontend/src/components/studios/LegalStudio/ChatMessages.tsx`, import ResearchBubble and handle the new type:

```tsx
import { ResearchBubble } from './ResearchBubble';
import type { Message, ResearchMessage } from '../../../lib/api';
```

Inside the `messages.map(...)` block, add a branch before the existing `if (msg.role === 'user')`:

```tsx
{messages.map((msg, i) => {
  if (msg.role === 'research') {
    const rm = msg as ResearchMessage;
    return (
      <div key={rm.id || `msg-${i}`} className="legal-section-pad">
        <ResearchBubble
          phases={rm.phases}
          report={rm.report}
          sources={rm.sources}
          query={rm.query}
          onSourceClick={onSourceClick}
        />
      </div>
    );
  }
  if (msg.role === 'user') {
    return (
      <div key={msg.id || `msg-${i}`} className="chat-msg chat-msg--user">
        // ... existing user message JSX ...
      </div>
    );
  }
  return (
    <AIMessage
      key={msg.id || `msg-${i}`}
      msg={msg}
      onSourceClick={onSourceClick}
      activeSourceId={activeSourceId}
    />
  );
})}
```

Also remove `activeSourceId` from `AIMessage` props if it was only used for research (verify — it's already passed to `AIMessage` fine).

- [ ] **Step 7: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 0 errors. Fix any type errors before proceeding.

- [ ] **Step 8: Manual test**

Start dev server. Open LegalStudio in Deep Research mode. Send a question. Confirm:
- Phases stream in as ResearchBubble inline
- Report renders when complete
- Sending a second research question adds a NEW ResearchBubble below — previous one stays visible

- [ ] **Step 9: Commit**

```bash
git add frontend/src/lib/api.ts \
        frontend/src/components/studios/LegalStudio/LegalStudio.tsx \
        frontend/src/components/studios/LegalStudio/ChatMessages.tsx
git commit -m "fix: unify message state — research results stored as messages, never cleared

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: Session Persistence (1.1)

**Problem:** Navigating away from a notebook and back loses chat history and sources. The backend endpoints already exist; the frontend never loads them on mount.

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`

> Note: The backend already has:
> - `GET /api/chat/conversations/{id}/messages` → messages
> - `GET /api/legal-studio/notebook/{id}/sources` → `{ source_ids: string[] }`
> - `POST /api/legal-studio/save-sources` with `{ conversation_id, source_ids }`

- [ ] **Step 1: Add message-load useEffect**

In `LegalStudio.tsx`, the existing load effect (lines ~167-193) already loads messages when `initialConversationId` is present. Verify it maps `role: 'assistant'` → `role: 'ai'` correctly:

```ts
// Existing effect (~line 177) — verify this mapping is correct:
useEffect(() => {
  if (!initialConversationId) return;
  setConversationId(initialConversationId);
  API.get(`/api/chat/conversations/${initialConversationId}/messages`)
    .then(r => {
      const msgs = (r.data ?? []).map((m: any): TextMessage => ({
        role: m.role === 'user' ? 'user' : 'ai',
        text: m.content,
        time: fmtTime(),
        sources: m.sources ?? [],
        id: m.id,
        messageId: m.id,
      }));
      setMessages(msgs);
    })
    .catch(() => {});
}, [initialConversationId]);
```

If this exists and is correct, no change needed. If `Message` type was changed in Task 2, update the return type to `TextMessage`.

- [ ] **Step 2: Add sources-load useEffect**

Add a new `useEffect` below the message-load effect:

```ts
useEffect(() => {
  if (!initialConversationId) return;
  API.get(`/api/legal-studio/notebook/${initialConversationId}/sources`)
    .then(r => {
      const ids: string[] = r.data?.source_ids ?? [];
      if (ids.length > 0) {
        setSelectedDocIds(ids);
        // Mark those IDs as "ready" in docs list so they show as selected
        setDocs(ids.map(id => ({
          id,
          filename: id,  // placeholder; will be overwritten if document metadata loads
          source: id,
          status: 'ready' as const,
        })));
      }
    })
    .catch(() => {});
}, [initialConversationId]);
```

- [ ] **Step 3: Persist sources on selectedDocIds change**

Add an effect that saves `selectedDocIds` to the backend whenever they change:

```ts
const persistSourcesRef = useRef<ReturnType<typeof setTimeout> | null>(null);

useEffect(() => {
  if (!conversationId) return;
  // Debounce — don't fire on every keystroke/checkbox, only after 500ms quiet
  if (persistSourcesRef.current) clearTimeout(persistSourcesRef.current);
  persistSourcesRef.current = setTimeout(() => {
    API.post('/api/legal-studio/save-sources', {
      conversation_id: conversationId,
      source_ids: selectedDocIds,
    }).catch(() => {});
  }, 500);
}, [conversationId, selectedDocIds]);
```

- [ ] **Step 4: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 5: Manual test**

1. Open a notebook, send a message.
2. Navigate to home page, navigate back.
3. Confirm messages are present.
4. Add a source document, navigate away and back.
5. Confirm the source is still selected.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/LegalStudio.tsx
git commit -m "fix: session persistence — load messages and sources on notebook open

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4: Research Orchestrator Fix (2.1)

**Problem:** `_plan()` LLM system prompt is ambiguous — produces clarifying questions instead of factual sub-questions.

**Files:**
- Modify: `backend/core/research/orchestrator.py`

- [ ] **Step 1: Rewrite `_plan()` system prompt**

In `backend/core/research/orchestrator.py`, replace the `_plan` function:

```python
GENERIC_PATTERNS = [
    "what aspect", "general or detailed", "prior knowledge",
    "interested in learning", "specific topic", "what type of information",
    "what would you like", "are you looking for", "which area",
    "how detailed should", "what do you want to know",
]


def _is_generic(q: str) -> bool:
    ql = q.lower()
    return any(p in ql for p in GENERIC_PATTERNS)


async def _plan(query: str) -> list[str]:
    """Generate 3-5 factual, independently-searchable sub-questions from query."""
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
    raw = await _llm(system, query)
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            cleaned = "\n".join(inner)
        data = json.loads(cleaned.strip())
        sub_questions = list(data.get("sub_questions", [query]))[:5]
    except Exception:
        return [query]

    # Validate: if any sub-question is generic, fall back to the original query
    if any(_is_generic(q) for q in sub_questions):
        logger.warning("_plan() returned generic questions — falling back to original query")
        return [query]

    return sub_questions
```

- [ ] **Step 2: Run backend tests**

```bash
cd backend && python -m pytest tests/ -v -k "research or orchestrat" 2>&1 | head -60
```

Expected: All existing research tests pass (or "no tests collected" if there are none — that's fine).

- [ ] **Step 3: Manual smoke test**

```bash
cd backend && python -c "
import asyncio
from core.research.orchestrator import _plan
result = asyncio.run(_plan('What is VAT treatment for exported services in UAE?'))
print(result)
assert len(result) >= 1
assert not any('what aspect' in q.lower() for q in result)
print('PASS')
"
```

Expected output: A list of 3-5 specific factual questions about UAE VAT.

- [ ] **Step 4: Commit**

```bash
git add backend/core/research/orchestrator.py
git commit -m "fix: research orchestrator — specific system prompt + generic-question guard

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5: Domain Prompt Grounding (2.2)

**Problem:** LLMs hallucinate article numbers and thresholds. Grounding rules and few-shot examples reduce this without provider lock-in.

**Files:**
- Modify: `backend/core/prompt_router.py`

- [ ] **Step 1: Add GROUNDING_RULES constant**

At the top of `backend/core/prompt_router.py`, after the existing `ABBREVIATION_SUFFIX` constant, add:

```python
GROUNDING_RULES = (
    "\n\nGROUNDING RULES — always follow:\n"
    "- Answer ONLY from the provided context and your verified knowledge of UAE law.\n"
    "- If the context does not contain enough information, say "
    "\"I don't have enough context to answer this accurately.\"\n"
    "- Never fabricate UAE law article numbers, decree numbers, or monetary thresholds.\n"
    "- Always state which decree/law/standard your answer is based on."
)
```

- [ ] **Step 2: Add FEW_SHOT_EXAMPLES constant**

After `GROUNDING_RULES`:

```python
FEW_SHOT_EXAMPLES: dict[str, str] = {
    "vat": (
        "\n\nEXAMPLE:\n"
        "Q: Is VAT charged on residential rental?\n"
        "A: No. Residential property rental is exempt from VAT under Article 46(1)(b) of "
        "Federal Decree-Law No. 8 of 2017 on VAT."
    ),
    "corporate_tax": (
        "\n\nEXAMPLE:\n"
        "Q: What is the Corporate Tax rate for a small business?\n"
        "A: 0% if taxable income does not exceed AED 375,000 (Small Business Relief). "
        "The standard 9% rate applies above that threshold under Federal Decree-Law No. 47 of 2022."
    ),
    "audit": (
        "\n\nEXAMPLE:\n"
        "Q: What does ISA 315 cover?\n"
        "A: ISA 315 (Revised 2019) covers identifying and assessing the risks of material "
        "misstatement through understanding the entity and its environment, including internal control."
    ),
    "aml": (
        "\n\nEXAMPLE:\n"
        "Q: What is the STR filing deadline in UAE?\n"
        "A: A Suspicious Transaction Report must be filed within 30 days of forming suspicion, "
        "under CBUAE AML/CFT Regulation No. 24 of 2000 and subsequent CBUAE circulars."
    ),
    "peppol": (
        "\n\nEXAMPLE:\n"
        "Q: What UBL version is used for UAE Peppol e-invoicing?\n"
        "A: UBL 2.1 per the FTA e-invoicing technical specifications (Peppol BIS Billing 3.0 profile)."
    ),
    "finance": (
        "\n\nEXAMPLE:\n"
        "Q: What are the IFRS 15 revenue recognition criteria?\n"
        "A: Revenue is recognised using the 5-step model under IFRS 15: (1) identify the contract, "
        "(2) identify performance obligations, (3) determine transaction price, "
        "(4) allocate transaction price, (5) recognise revenue when/as obligation is satisfied."
    ),
}
```

- [ ] **Step 3: Apply grounding + few-shot to each domain in DOMAIN_PROMPTS**

In `DOMAIN_PROMPTS`, for each key (`finance`, `law`, `audit`, `general`, `vat`, `corporate_tax`, `aml`, `peppol`, and any others), append `GROUNDING_RULES` and the matching `FEW_SHOT_EXAMPLES` entry at the end of the string.

Example for `finance` — update the value to:

```python
"finance": (
    "You are an expert AI assistant specialising in financial accounting, IFRS, UAE Corporate Tax "
    "(9% rate from June 2023), VAT (5% standard rate), FTA compliance, and financial reporting. "
    "When answering: cite the relevant standard or article, use AED as the default currency, "
    "present calculations step-by-step, and be precise with numbers, dates, and regulatory references. "
    "When financial data (trial balance, ledger, income statement, balance sheet) is provided in the context, "
    "ALWAYS extract ALL relevant figures from the data and perform precise calculations. "
    "Show your calculation step-by-step. Sum up revenue items, expense items, compute net figures. "
    "Do NOT say the data is insufficient if it is present in the context — extract and calculate."
    + FORMATTING_SUFFIX + ABBREVIATION_SUFFIX + GROUNDING_RULES + FEW_SHOT_EXAMPLES.get("finance", "")
),
```

Apply the same pattern to: `law`, `audit`, `vat`, `corporate_tax`, `aml`, and `general`.

For domains that don't have a few-shot entry (e.g. `law`, `general`), `FEW_SHOT_EXAMPLES.get("law", "")` returns `""` — that is fine.

- [ ] **Step 4: Verify prompt_router imports correctly**

```bash
cd backend && python -c "from core.prompt_router import get_system_prompt, DOMAIN_PROMPTS; print('GROUNDING' in DOMAIN_PROMPTS['finance']); print('len vat:', len(DOMAIN_PROMPTS['vat']))"
```

Expected: `True` printed, and a positive integer length.

- [ ] **Step 5: Commit**

```bash
git add backend/core/prompt_router.py
git commit -m "feat: add grounding rules + few-shot examples to all domain prompts

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 6: MIS Report Markdown Rendering (2.3)

**Problem:** AuditChat `ChatMessage.tsx` renders `msg.content` as plain text — markdown shows raw symbols.

**Files:**
- Modify: `frontend/src/components/studios/FinanceStudio/AuditChat/ChatMessage.tsx`
- Modify: `frontend/src/components/studios/FinanceStudio/FinanceStudio.css`

- [ ] **Step 1: Add ReactMarkdown to ChatMessage**

`ReactMarkdown` and `remark-gfm` are already installed (used in LegalStudio's `ChatMessages.tsx`). Update `ChatMessage.tsx`:

```tsx
import type { ChatMessage as CM } from '../types';
import { FileText } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export function ChatMessage({ msg }: { msg: CM }) {
  return (
    <div className={`chat-msg chat-msg--${msg.role}`} data-testid={`msg-${msg.id}`}>
      <div className="chat-msg__content">
        {msg.role === 'assistant' ? (
          <div className="report-markdown">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
          </div>
        ) : (
          msg.content
        )}
      </div>
      {msg.citations?.length > 0 && (
        <div className="chat-msg__citations">
          {msg.citations.map((c, i) => (
            <span key={i} className="citation-chip">
              <FileText size={10} />
              {c.doc_id}{c.page ? ` p.${c.page}` : ''}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add .report-markdown table styles**

In `frontend/src/components/studios/FinanceStudio/FinanceStudio.css`, append:

```css
.report-markdown table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  margin: 8px 0;
}

.report-markdown th,
.report-markdown td {
  border: 1px solid var(--s-border, rgba(255,255,255,0.08));
  padding: 6px 10px;
  text-align: left;
}

.report-markdown th {
  background: rgba(255, 255, 255, 0.06);
  font-weight: 600;
}

.report-markdown tr:nth-child(even) td {
  background: rgba(255, 255, 255, 0.02);
}

.report-markdown h2 {
  font-size: 15px;
  font-weight: 600;
  margin: 12px 0 6px;
}

.report-markdown h3 {
  font-size: 13px;
  font-weight: 600;
  margin: 8px 0 4px;
}
```

- [ ] **Step 3: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: Visual test**

Start dev server, go to FinanceStudio, run a report via AuditChat. Confirm headings, bold text, and tables render as HTML.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/studios/FinanceStudio/AuditChat/ChatMessage.tsx \
        frontend/src/components/studios/FinanceStudio/FinanceStudio.css
git commit -m "fix: render markdown in AuditChat messages — tables, bold, headings visible

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 7: Entity Name Auto-Extraction (2.4)

**Problem:** MIS Report questionnaire forces user to type Entity Name that's already in uploaded docs.

**Files:**
- Modify: `backend/api/legal_studio.py`
- Modify: `frontend/src/components/studios/LegalStudio/QuestionnaireMessage.tsx`

- [ ] **Step 1: Add extract_entity_name helper to legal_studio.py**

In `backend/api/legal_studio.py`, add after imports:

```python
from sqlalchemy import select as sa_select
from db.models import Document
from core.llm_manager import get_llm_provider


async def extract_entity_name(source_ids: list[str], db: AsyncSession) -> str | None:
    """Run a quick LLM extraction on the first available source doc.

    Returns the extracted entity name, or None if extraction fails or
    the result is ambiguous (multiple distinct names in one doc).
    Only uses the first source document to avoid multi-entity confusion.
    """
    if not source_ids:
        return None

    # Use only the first document to avoid multi-entity confusion
    result = await db.execute(
        sa_select(Document).where(Document.id == source_ids[0])
    )
    doc = result.scalar_one_or_none()
    if not doc:
        return None

    # Use summary if available (cheaper than re-reading full doc)
    snippet = doc.summary or ""
    if not snippet and doc.metadata_json:
        meta = doc.metadata_json if isinstance(doc.metadata_json, dict) else {}
        snippet = meta.get("structured_text", "")[:1000]

    if not snippet:
        return None

    try:
        llm = get_llm_provider()
        resp = await llm.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Extract the primary company or entity name from this document text. "
                        "Respond with ONLY the entity name — nothing else. "
                        "If you cannot determine a single clear entity name, respond with: UNKNOWN"
                    ),
                },
                {"role": "user", "content": snippet[:2000]},
            ],
            temperature=0.0,
            max_tokens=50,
        )
        name = resp.content.strip()
        if name.upper() == "UNKNOWN" or not name:
            return None
        return name
    except Exception:
        return None
```

- [ ] **Step 2: Add auto-extract endpoint**

Still in `backend/api/legal_studio.py`, add a new GET endpoint:

```python
@router.get("/notebook/{conversation_id}/entity-name")
async def get_entity_name(conversation_id: str, db: AsyncSession = Depends(get_db)):
    """Extract entity name from the conversation's checked source documents."""
    result = await db.execute(
        sa_select(Conversation.checked_source_ids).where(Conversation.id == conversation_id)
    )
    source_ids = result.scalar_one_or_none() or []
    name = await extract_entity_name(source_ids, db)
    return {"entity_name": name}
```

- [ ] **Step 3: Update QuestionnaireMessage.tsx to support auto-detected placeholder**

In `frontend/src/components/studios/LegalStudio/QuestionnaireMessage.tsx`, update the `PrefilledField` interface and render:

```tsx
interface PrefilledField {
  key: string;
  label: string;
  value: string;
  editable: boolean;
  placeholder?: string;      // new optional field
  autoDetected?: boolean;    // new: show italic grey hint
}
```

Update the input render to use placeholder and show auto-detected hint:

```tsx
{f.editable ? (
  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
    <input
      value={values[f.key] ?? ''}
      onChange={e => handleChange(f.key, e.target.value)}
      disabled={generating}
      placeholder={f.placeholder ?? ''}
      style={{
        fontSize: 12,
        padding: '4px 8px',
        borderRadius: 'var(--s-r-sm)',
        border: '1px solid var(--s-border, rgba(255,255,255,0.1))',
        background: 'rgba(255,255,255,0.05)',
        color: 'var(--s-text-1, #fff)',
        outline: 'none',
      }}
    />
    {f.autoDetected && values[f.key] && (
      <span style={{ fontSize: 11, color: 'var(--s-text-2)', fontStyle: 'italic' }}>
        Auto-detected from sources
      </span>
    )}
  </div>
) : (
  <span style={{ fontSize: 12, color: 'var(--s-text-1, #fff)' }}>
    {values[f.key]}
  </span>
)}
```

- [ ] **Step 4: Wire auto-extract into the report questionnaire flow in LegalStudio.tsx**

In `LegalStudio.tsx`, update `handleReportRequest` to fetch the entity name before showing the questionnaire:

```ts
const handleReportRequest = useCallback(async (reportType: string) => {
  const config = REPORT_CONFIGS[reportType];
  if (!config) return;

  // Auto-extract entity name if conversation exists and field is present
  let entityName = '';
  if (conversationId && config.fields.some(f => f.key === 'entity_name')) {
    try {
      const r = await API.get(`/api/legal-studio/notebook/${conversationId}/entity-name`);
      entityName = r.data?.entity_name ?? '';
    } catch { /* non-fatal — leave blank */ }
  }

  const fields = config.fields.map(f =>
    f.key === 'entity_name'
      ? { ...f, value: entityName, placeholder: 'Auto-detected from sources', autoDetected: !!entityName }
      : { ...f }
  );

  setActiveQuestionnaire({ reportType, fields, label: config.label });
  setTimeout(() => chatAreaBottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
}, [conversationId]);
```

- [ ] **Step 5: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 6: Manual test**

1. Upload a PDF with a company name visible in its text.
2. Open an MIS Report questionnaire.
3. Confirm Entity Name field shows the extracted company name (or blank with placeholder if extraction fails).
4. Confirm field is still editable — user can override.

- [ ] **Step 7: Commit**

```bash
git add backend/api/legal_studio.py \
        frontend/src/components/studios/LegalStudio/QuestionnaireMessage.tsx \
        frontend/src/components/studios/LegalStudio/LegalStudio.tsx
git commit -m "feat: auto-extract entity name from sources in MIS questionnaire

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 8: Notebook Card Hover Delete Bug (3.1)

**Problem:** Moving mouse toward the delete button triggers `onMouseLeave` on the card → button hides before click lands.

**Files:**
- Modify: `frontend/src/components/common/NotebookCard.tsx`

- [ ] **Step 1: Fix card position and delete button hover**

In `frontend/src/components/common/NotebookCard.tsx`, update the `NotebookCard` JSX:

1. Add `position: 'relative'` to the outer `<div>` inline style (so the absolute-positioned delete button is clipped to the card):

```tsx
<div
  className={`notebook-card${isList ? ' notebook-card--list' : ''}`}
  style={{ ...cardStyle, position: 'relative' }}
  onClick={() => onClick(notebook.id)}
  role="button"
  tabIndex={0}
  onKeyDown={e => { if (e.key === 'Enter') onClick(notebook.id); }}
  onMouseEnter={() => setHovered(true)}
  onMouseLeave={() => setHovered(false)}
>
```

2. Add `onMouseEnter={() => setHovered(true)}` to the delete button so hovering over it keeps `hovered=true`:

```tsx
{onDelete && (
  <button
    aria-label="Delete notebook"
    style={deleteBtnStyle}
    onClick={handleDelete}
    onMouseEnter={() => setHovered(true)}
  >
    <Trash2 size={16} />
  </button>
)}
```

- [ ] **Step 2: Verify visually**

Start dev server, go to home page. Hover a card — delete button appears. Slowly move mouse onto the delete button. Confirm it stays visible and is clickable.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/common/NotebookCard.tsx
git commit -m "fix: notebook card delete button stays visible on hover — position + onMouseEnter

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 9: Multi-Select + Bulk Delete (3.2)

**Problem:** Can only delete one notebook at a time.

**Files:**
- Modify: `frontend/src/pages/HomePage.tsx`
- Modify: `frontend/src/components/common/NotebookCard.tsx`

- [ ] **Step 1: Add selection state to HomePage.tsx**

In `frontend/src/pages/HomePage.tsx`, add state after the existing `deleteTarget` state:

```ts
const [selectionMode, setSelectionMode] = useState(false);
const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
```

- [ ] **Step 2: Add "Select" toggle button to the toolbar**

In the toolbar JSX in `HomePage.tsx`, after the view toggle buttons, add:

```tsx
<button
  onClick={() => {
    setSelectionMode(s => !s);
    setSelectedIds(new Set());
  }}
  style={{
    ...toggleBtnBase,
    background: selectionMode ? 'var(--s-accent, #6366f1)' : 'rgba(255,255,255,0.06)',
    color: selectionMode ? '#fff' : 'var(--s-text-2)',
    borderColor: selectionMode ? 'transparent' : undefined,
    fontSize: '13px',
    fontWeight: 600,
    width: 'auto',
    padding: '0 12px',
  }}
>
  {selectionMode ? `✕ Cancel` : 'Select'}
</button>

{selectionMode && selectedIds.size > 0 && (
  <button
    onClick={() => setDeleteTarget('__bulk__')}
    style={{
      ...toggleBtnBase,
      width: 'auto',
      padding: '0 12px',
      fontSize: '13px',
      fontWeight: 600,
      background: 'rgba(239,68,68,0.8)',
      color: '#fff',
      borderColor: 'transparent',
    }}
  >
    Delete ({selectedIds.size})
  </button>
)}
```

- [ ] **Step 3: Add handleBulkDelete and update handleDeleteConfirm**

In `HomePage.tsx`, update `handleDeleteConfirm`:

```ts
const handleDeleteConfirm = async () => {
  if (!deleteTarget) return;

  if (deleteTarget === '__bulk__') {
    try {
      await Promise.all([...selectedIds].map(id =>
        API.delete(`/api/legal-studio/notebook/${id}`)
      ));
      setNotebooks(prev => prev.filter(n => !selectedIds.has(n.id)));
      setSelectedIds(new Set());
      setSelectionMode(false);
    } catch { /* ignore individual failures */ }
    setDeleteTarget(null);
    return;
  }

  // Single delete (existing logic)
  try {
    await API.delete(`/api/legal-studio/notebook/${deleteTarget}`);
    setNotebooks(prev => prev.filter(n => n.id !== deleteTarget));
  } catch { /* ignore */ }
  setDeleteTarget(null);
};
```

- [ ] **Step 4: Update the confirmation modal text**

Update `deleteNotebook` lookup and modal to handle bulk:

```tsx
const isBulkDelete = deleteTarget === '__bulk__';
const deleteNotebook = isBulkDelete ? null : (filtered.find(n => n.id === deleteTarget) ?? notebooks.find(n => n.id === deleteTarget));

// In the modal:
{deleteTarget && (
  <div style={overlayStyle}>
    <div style={modalStyle}>
      <p style={{ marginBottom: 16, color: 'var(--s-text)' }}>
        {isBulkDelete
          ? `Delete ${selectedIds.size} notebook${selectedIds.size !== 1 ? 's' : ''}? This cannot be undone.`
          : `Delete "${deleteNotebook?.title}"? This cannot be undone.`
        }
      </p>
      // ... existing Cancel / Delete buttons ...
    </div>
  </div>
)}
```

- [ ] **Step 5: Add selected prop and onSelect to NotebookCard**

In `frontend/src/components/common/NotebookCard.tsx`, update the `Props` interface:

```ts
interface Props {
  notebook: Notebook;
  onClick: (id: string) => void;
  onDelete?: (id: string) => void;
  onSelect?: (id: string) => void;
  selected?: boolean;
  selectionMode?: boolean;
  view?: 'grid' | 'list';
}
```

Update the `NotebookCard` function signature:

```tsx
export function NotebookCard({ notebook, onClick, onDelete, onSelect, selected = false, selectionMode = false, view = 'grid' }: Props) {
```

Update the card's `onClick` handler:

```tsx
onClick={() => {
  if (selectionMode && onSelect) {
    onSelect(notebook.id);
  } else {
    onClick(notebook.id);
  }
}}
```

Add a selection overlay to the thumbnail:

```tsx
<div className="notebook-card__thumb" style={{
  ...thumbStyle,
  outline: selected ? '2px solid var(--s-accent, #6366f1)' : undefined,
}}>
  {selected ? (
    <span style={{ fontSize: isList ? '16px' : '22px', fontWeight: 700 }}>✓</span>
  ) : titleInitials(notebook.title)}
</div>
```

- [ ] **Step 6: Pass selection props in HomePage.tsx**

Update `NotebookCard` usage in `HomePage.tsx`:

```tsx
<NotebookCard
  key={n.id}
  notebook={n}
  onClick={handleOpen}
  onDelete={n => setDeleteTarget(n)}
  onSelect={id => setSelectedIds(prev => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  })}
  selected={selectedIds.has(n.id)}
  selectionMode={selectionMode}
  view={viewMode}
/>
```

- [ ] **Step 7: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 8: Manual test**

1. Click "Select" — enters selection mode.
2. Click two notebooks — both show checkmark overlay.
3. Click "Delete (2)" — confirmation modal says "Delete 2 notebooks?".
4. Confirm — both notebooks removed from list.
5. Click "Cancel" — exits selection mode.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/pages/HomePage.tsx \
        frontend/src/components/common/NotebookCard.tsx
git commit -m "feat: multi-select bulk delete for notebooks on home page

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 10: Domain Icons (3.3)

**Problem:** All notebooks show 2-letter initials. Domain icons make notebook type instantly recognizable.

**Key facts:**
- `Conversation.domain` column **already exists** in `db/models.py` (nullable string, line 36)
- `ConversationResponse` does **not** currently expose `domain`
- `GET /api/chat/conversations` does **not** include `domain` in the response
- Old notebooks have `domain = NULL` — they fall back to initials gracefully

**Files:**
- Modify: `backend/api/chat.py`
- Modify: `frontend/src/components/common/NotebookCard.tsx`
- Modify: `frontend/src/pages/HomePage.tsx`

- [ ] **Step 1: Expose domain in ConversationResponse**

In `backend/api/chat.py`, update `ConversationResponse`:

```python
class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0
    domain: str | None = None   # add this
```

- [ ] **Step 2: Populate domain in list_conversations**

In `list_conversations`, update the `response.append(...)` call:

```python
response.append(ConversationResponse(
    id=conv.id,
    title=conv.title,
    created_at=str(conv.created_at),
    updated_at=str(conv.updated_at),
    message_count=msg_count,
    domain=conv.domain,   # add this
))
```

- [ ] **Step 3: Save domain when new conversation created**

In `send_message` (~line 226-232), after `await db.flush()`, save the detected domain:

```python
conversation = Conversation(
    title=req.message[:80] + ("..." if len(req.message) > 80 else ""),
    llm_provider=req.provider or settings.llm_provider,
    llm_model=settings.active_model,
    domain=classifier_result.domain.value if classifier_result else None,  # save domain
)
```

> Note: `classifier_result` is computed at line ~310 before it's needed at ~325, but the conversation is created at ~226. The simplest fix is to set domain on the conversation after classification runs. Find the spot after `classifier_result` is set and add:
> ```python
> if not conversation.domain and classifier_result:
>     conversation.domain = classifier_result.domain.value
>     await db.flush()
> ```

- [ ] **Step 4: Add domain icons to NotebookCard**

In `frontend/src/components/common/NotebookCard.tsx`, add the icon map and update the interface:

```tsx
import { Scale, BarChart2, ClipboardCheck, Receipt, Building2, Shield, BookOpen, FileText } from 'lucide-react';

const DOMAIN_ICONS: Record<string, React.ElementType> = {
  legal: Scale,
  law: Scale,
  finance: BarChart2,
  audit: ClipboardCheck,
  vat: Receipt,
  corporate_tax: Building2,
  aml: Shield,
  general: BookOpen,
};

interface Notebook {
  id: string;
  title: string;
  updated_at: string;
  source_count?: number;
  thumbnail_icon?: string;
  domain?: string;   // add this
}
```

Update the thumbnail JSX to render an icon when `domain` is set:

```tsx
<div className="notebook-card__thumb" style={{
  ...thumbStyle,
  outline: selected ? '2px solid var(--s-accent, #6366f1)' : undefined,
}}>
  {selected ? (
    <span style={{ fontSize: isList ? '16px' : '22px', fontWeight: 700 }}>✓</span>
  ) : notebook.domain && DOMAIN_ICONS[notebook.domain] ? (
    React.createElement(DOMAIN_ICONS[notebook.domain], { size: isList ? 18 : 24 })
  ) : (
    titleInitials(notebook.title)
  )}
</div>
```

Add `import React from 'react';` at top if not present.

- [ ] **Step 5: Pass domain in HomePage.tsx**

Update the `Notebook` mapping in `HomePage.tsx`:

```ts
setNotebooks(convos.map((c: any) => ({
  id: c.id,
  title: c.title || 'Untitled Notebook',
  updated_at: c.updated_at || new Date().toISOString(),
  source_count: c.source_count,
  domain: c.domain ?? undefined,   // add this
})));
```

- [ ] **Step 6: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 7: Manual test**

1. Start dev server + backend.
2. Create new VAT question → check home page → notebook thumbnail shows `Receipt` icon.
3. Old notebook with no domain → shows 2-letter initials as before.

- [ ] **Step 8: Commit**

```bash
git add backend/api/chat.py \
        frontend/src/components/common/NotebookCard.tsx \
        frontend/src/pages/HomePage.tsx
git commit -m "feat: domain icons on notebook thumbnails — scales, charts, receipts

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 11: Auditor Format Wire-Up (3.4)

**Problem:** "Custom Template" selection does nothing. Audit format not wired from UI to API.

**Spec note:** This is verify-first. The actual root cause must be confirmed before fixing.

**Context established during planning:**
- `AuditorFormatGrid` fires `onChange(format)` correctly — callback exists.
- `StudioPanel.tsx` has its own local `format` state, BUT when `onReportRequest` is set (always the case in LegalStudio), `handleGenerateReport` calls `onReportRequest(type)` and returns — **the format is never passed**.
- `LegalStudio.tsx` has its own `auditorFormat` state (default `'standard'`) but no `AuditorFormatGrid` rendered — it only sees the format when the audit questionnaire sets it from `auditFields` memoized value.
- `backend/api/legal_studio.py` `AuditRequest` model only accepts `document_ids` — `format`, `entity_name`, `period`, `scope` are silently dropped.

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/StudioPanel.tsx`
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`
- Modify: `backend/api/legal_studio.py`

- [ ] **Step 1: Add onFormatChange prop to StudioPanel**

In `frontend/src/components/studios/LegalStudio/StudioPanel.tsx`, update the `Props` interface:

```tsx
interface Props {
  sourceIds: string[];
  companyName?: string;
  mode?: ChatMode;
  onReportRequest?: (reportType: string) => void;
  onFormatChange?: (format: AuditorFormat) => void;  // add this
  auditorFormat?: AuditorFormat;                      // add this (controlled)
}
```

Update the component signature:

```tsx
export function StudioPanel({ sourceIds, companyName = 'Analysis', mode, onReportRequest, onFormatChange, auditorFormat: controlledFormat }: Props) {
  const [localFormat, setLocalFormat] = useState<AuditorFormat>('standard');
  const format = controlledFormat ?? localFormat;

  const handleFormatChange = (f: AuditorFormat) => {
    setLocalFormat(f);
    onFormatChange?.(f);
  };
```

Update `AuditorFormatGrid` in StudioPanel JSX: `<AuditorFormatGrid value={format} onChange={handleFormatChange} />`

- [ ] **Step 2: Wire format from StudioPanel → LegalStudio**

In `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`, update the `StudioPanel` render:

```tsx
right={
  <StudioPanel
    sourceIds={selectedDocIds}
    mode={mode}
    onReportRequest={handleReportRequest}
    auditorFormat={auditorFormat}
    onFormatChange={setAuditorFormat}
  />
}
```

Now `auditorFormat` in LegalStudio is always in sync with what's shown in StudioPanel.

- [ ] **Step 3: Fix AuditRequest backend model to accept full params**

In `backend/api/legal_studio.py`, update `AuditRequest`:

```python
class AuditRequest(BaseModel):
    document_ids: list[str]
    entity_name: str = ""
    period: str = ""
    format: str = "standard"
    scope: str = "Full financial audit"
```

Update the `auditor` endpoint to pass the params to `run_audit`:

```python
@router.post("/auditor", response_model=AuditResponse)
async def auditor(req: AuditRequest):
    """Run audit analysis on selected documents."""
    result = await run_audit(
        req.document_ids,
        entity_name=req.entity_name,
        period=req.period,
        auditor_format=req.format,
        scope=req.scope,
    )
    return AuditResponse(**result)
```

- [ ] **Step 4: Check run_audit signature**

Open `backend/core/chat/auditor_agent.py` and check if `run_audit` accepts `entity_name`, `period`, `auditor_format`, `scope` kwargs. If not, add them:

```python
async def run_audit(
    document_ids: list[str],
    entity_name: str = "",
    period: str = "",
    auditor_format: str = "standard",
    scope: str = "Full financial audit",
) -> dict:
    # ... existing logic ...
    # Pass entity_name, period, auditor_format, scope into the audit prompt as context
```

If the function signature already accepts `**kwargs`, just ensure the params are used in the audit system prompt.

- [ ] **Step 5: TypeScript check + backend import check**

```bash
cd frontend && npx tsc --noEmit
cd ../backend && python -c "from api.legal_studio import router; print('OK')"
```

Both should succeed.

- [ ] **Step 6: Manual test — custom template flow**

1. In LegalStudio, select "Custom Template" in StudioPanel's AuditorFormatGrid.
2. CustomTemplatePicker should open (LegalStudio already handles this in `handleRunAudit`).
3. Select a template.
4. Run audit — confirm `format: "custom:TemplateName"` appears in network request payload.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/StudioPanel.tsx \
        frontend/src/components/studios/LegalStudio/LegalStudio.tsx \
        backend/api/legal_studio.py
git commit -m "fix: wire auditor format from StudioPanel through to backend API

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Self-Review Checklist

### Spec Coverage
| Spec item | Task |
|-----------|------|
| 1.1 Session persistence | Task 3 |
| 1.2 Message unification | Task 2 |
| 1.3 Chat overflow | Task 1 |
| 2.1 Research orchestrator | Task 4 |
| 2.2 Domain prompts | Task 5 |
| 2.3 MIS markdown | Task 6 |
| 2.4 Entity extraction | Task 7 |
| 3.1 Hover delete bug | Task 8 |
| 3.2 Multi-select bulk delete | Task 9 |
| 3.3 Domain icons | Task 10 |
| 3.4 Auditor format | Task 11 |

All 11 spec items covered. ✓

### Known Deviations from Spec (documented)
1. **Task 11**: Spec said `backend/api/audit_studio.py` handles `auditor_format`. Investigation showed the audit endpoint is in `legal_studio.py` — plan targets the correct file.
2. **Task 10**: `domain` column already exists in `Conversation` model — no DB migration needed; only the API response and frontend need updates.
3. **Task 2**: The `researchSources` + `researchQuery` state vars are collapsed into the `ResearchMessage` type — functionally equivalent but cleaner.
