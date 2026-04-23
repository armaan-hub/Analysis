# Design: Chatbot Improvements — Deep Research, Analyst, Chat Bugs, Skills, LLM Council

**Date:** 2026-04-23  
**Project:** Project_AccountingLegalChatbot  
**Status:** Approved

---

## Problem Statement

Five distinct improvement areas were identified through user testing:

1. **Deep Research** doesn't reliably complete, and its exported document lacks a Table of Contents and source links.
2. **Analyst mode** crashes on click — the tool stops working entirely.
3. **Three chat bugs** degrade daily usability: source names show UUIDs instead of filenames, the LLM answers off-topic, and the first message is often silently dropped.
4. **No reusable skills** exist for Deep Research or Analyst workflows.
5. **No multi-expert review** mechanism exists — users want a "Run by the council" feature with four financial expert personas providing consensus-driven answers.

---

## Priority Order

1. Deep Research Overhaul
2. Analyst Mode Fix + Redesign
3. Three Chat Bugs
4. New Skills (Deep Research + Analyst)
5. LLM Council

---

## Priority 1 — Deep Research Overhaul

### Problem

- `run_deep_research` in `core/research/deep_research_service.py` does not guarantee the `answer` event is always emitted. If a web search or RAG call raises an unhandled exception, the SSE stream closes without sending `type: answer` or `type: done`, leaving the frontend hanging.
- The existing export (`ArtifactPanel.onExport`) writes a plain `.md` file. The `deep_research_export.py` module already supports branded PDF and DOCX but is not wired to the UI.
- Downloaded documents do not include source links.

### Backend Fix — `core/research/deep_research_service.py`

- Wrap the entire generator body in `try/except`. If any unhandled error occurs, yield an `{"type":"error","text":"..."}` event, then yield `{"type":"done"}`.
- Add a per-query timeout (10 seconds) on each `brave_search` call using `asyncio.wait_for`. On timeout, log the failure and continue with whatever results were collected.
- Ensure the `answer` event payload always includes:
  ```json
  {
    "type": "answer",
    "content": "<synthesized markdown answer>",
    "sources": [{"filename": "...", "page": "..."}],
    "web_sources": [{"title": "...", "url": "..."}]
  }
  ```
  `web_sources` was already collected but must now be included in the `sources appendix` section of the exported document.

### Backend — Export Endpoints

Add two new endpoints to `api/chat.py` (or a new `api/research.py`):

```
POST /api/research/export/docx
POST /api/research/export/pdf
```

Request body:
```json
{
  "query": "original research question",
  "content": "full markdown answer",
  "sources": [...],
  "web_sources": [{"title": "...", "url": "..."}]
}
```

These call `deep_research_export.to_branded_pdf` and `deep_research_export.to_branded_docx` respectively. Both must include a **Sources Appendix** section at the end with numbered entries: document name + page reference (for RAG chunks) and title + clickable URL (for web sources).

`deep_research_export.to_branded_docx` needs to be created (currently only PDF exists). It must:
- Use `python-docx`.
- Generate: Cover Page → Table of Contents (via `docx` TOC field) → Body (markdown headings → DOCX styles) → Sources Appendix (numbered list with hyperlinks).

### Frontend Fix — `useDeepResearch.ts` + `ResearchPanel`

- The `handleFrame` function in `useDeepResearch.ts` already handles `type: answer`. No change needed here.
- `ResearchPanel` currently shows steps and the answer text. Add a **download row** at the bottom:
  - `⬇ Download DOCX` button
  - `⬇ Download PDF` button
  - Both buttons POST to the new export endpoints with the answer + sources from the `answer` state object.
- When the `answer` event arrives, also dispatch it as a **summary chat message** (2–3 sentences) in the main thread. In `LegalStudio.tsx`, the existing `useEffect` that appends a `research` role message already does this — verify the summary is capped at ~300 chars to keep it readable inline.

### Exported Document Structure

All exports (DOCX and PDF) follow this structure:

| Section | Content |
|---|---|
| Cover Page | Research title (query), date, "Prepared by: AI Research Engine" |
| Table of Contents | Auto-generated from `##` and `###` headings in the answer |
| Full Answer | All sections, inline citations, tables |
| Sources Appendix | Numbered list — web sources with title + clickable URL; doc sources with filename + page |

---

## Priority 2 — Analyst Mode Fix + Redesign

### Problem

Clicking the Analyst pill in `ModePills` triggers a re-render of `LegalStudio` into `ThreePaneLayout`. This crashes silently — the tool goes blank. Root causes (to be confirmed in browser console during implementation):

1. `three-pane-layout` CSS may lack `height: 100%` / `min-height: 0` causing overflow collapse.
2. `ReactMarkdown` in `ArtifactPanel.tsx` may fail if version mismatch or missing.
3. `MisChart` and `MisKpiCards` imports may fail if their dependencies are missing.
4. `setMode` is `async` but `ChatInput.onModeChange` types it as `(mode: ChatMode) => void` — could swallow promise rejection.

### Fix

1. **Error Boundary** — create `AnalystErrorBoundary` React component wrapping `ThreePaneLayout` in `LegalStudio`. On error: render a "Analyst mode failed to load. [Reload]" fallback that resets mode to `fast`.
2. **CSS audit** — add `height: 100%; min-height: 0; overflow: hidden;` to `.three-pane-layout` and its children in `FinanceStudio.css` / global CSS.
3. **Lazy-load heavy components** — wrap `ArtifactPanel`, `MisChart`, `MisKpiCards`, `StudioPanel` in `React.lazy()` with `<Suspense>` fallbacks.
4. **Type fix** — change `ChatInput.onModeChange` to accept `(mode: ChatMode) => void | Promise<void>`.

### Analyst Reporting Workflow (Redesigned)

The `ThreePaneLayout` three-pane structure is correct. The workflow is:

```
[Left: Sources Sidebar]   [Center: Chat + Report Cards]   [Right: Artifact Panel or Studio Panel]
```

**User flow:**
1. Upload documents → they appear in Sources Sidebar (left).
2. Chat input accepts ad-hoc questions (standard fast-mode LLM response using `analyst` system prompt).
3. **Studio Panel** (right, when no artifact is open) shows `ANALYST_CARDS` — 12 report types.
4. User clicks a report card → `ConfirmReportCard` appears in center, auto-detecting entity name and period from uploaded docs.
5. User confirms (or edits) → report streams into `ArtifactPanel` (right pane).
6. `ArtifactPanel` gains:
   - **Download DOCX** button — calls `POST /api/research/export/docx` with report content.
   - **Download PDF** button — calls `POST /api/research/export/pdf` with report content.
   - Existing "Export Markdown" button remains.

---

## Priority 3 — Three Chat Bugs

### Bug 1: Source Names Show UUIDs

**Root cause:** When `LegalStudio` loads notebook sources from `GET /api/legal-studio/notebook/:id/sources`, it only receives a list of document IDs. It constructs `SourceDoc` objects with `filename: id, source: id` — so the sidebar displays the raw UUID.

**Fix:**
- After receiving the source IDs, call `GET /api/documents?ids=id1,id2,...` (or individual `GET /api/documents/:id` calls in parallel) to resolve `original_name` for each ID.
- Update the `SourceDoc` state to use `original_name` as `filename` and `source`.
- Backend: ensure `GET /api/documents/:id` returns `original_name` in its response (verify existing endpoint).

### Bug 2: LLM Answers Off-Topic (Two-Pass Reasoning)

**Root cause:** The system prompt defines the domain persona, but the LLM has no explicit instruction about *what type of output* the user expects. The LLM defaults to a comprehensive domain-expert answer instead of interpreting the specific question intent.

**Fix — Two-Pass Intent Classification in `api/chat.py`:**

Pass 1 (intent classification, ~100 tokens):
```
System: "Classify this question. Return JSON: 
  {\"intent\": \"question|checklist|one_pager|calculation|comparison|definition\",
   \"key_entities\": [...],
   \"expected_output\": \"brief description of what the user wants\"}"
User: <message>
```

Pass 2 (main answer):
- Prepend the classified intent to the system prompt:
  ```
  [Intent: {expected_output}. Answer exactly this — do not expand to related topics.]
  ```
- The main LLM call proceeds as normal with the enriched system prompt.

Pass 1 runs as a lightweight non-streaming call with `max_tokens=150, temperature=0.0`. Total overhead ≈ 200–400ms.

### Bug 3: Must Ask Twice (Loading State Race Condition)

**Root cause:** The `sendMessage` function in `LegalStudio.tsx` sets `setLoading(true)` before the `fetch` call. If the fetch throws (e.g., Analyst mode crash, network error, or AbortError), the catch block may not always call `setLoading(false)`, leaving `loading` stuck as `true`. The `ChatInput` is then `disabled` — the user appears to need to refresh or re-click.

**Fix:**

```typescript
// In sendMessage, restructure as:
setLoading(true);
try {
  // ... fetch logic
} catch (err) {
  if (!(err instanceof Error && err.name === 'AbortError')) {
    // log
  }
} finally {
  setLoading(false);   // ← always runs
  setWebSearching(false);
}
```

Additionally, add a 30-second `AbortController` timeout on the `/api/chat/send` fetch call so stale requests auto-cancel and reset loading state.

---

## Priority 4 — New Skills

Two skills are added to `skills/` at the project root. Each skill is mode-gated — it only activates when the corresponding mode is selected.

### `skills/deep-research/skill.md`

Encapsulates the Deep Research pipeline:

1. Decompose query → 2–3 sub-queries (via `query_decomposer.py`).
2. Brave Search + RAG search in parallel for each sub-query.
3. Synthesize answer with inline citations using the research synthesis prompt.
4. Offer DOCX + PDF export with sources appendix.

**Gate:** Available only when `mode === 'deep_research'`. The skill file documents this constraint clearly so the LLM agent knows not to invoke it in Fast mode.

### `skills/analyst/skill.md`

Encapsulates the Analyst reporting workflow:

1. Auto-detect entity name and period end from uploaded documents.
2. Present `ConfirmReportCard` with detected values pre-filled.
3. User confirms → stream report using the `analyst` domain prompt (`ca_auditor_system_prompt.md`).
4. Render in `ArtifactPanel`. Offer DOCX + PDF export.

**Gate:** Available only when `mode === 'analyst'`.

---

## Priority 5 — LLM Council

### Overview

The LLM Council is a multi-expert consensus feature. When triggered, four financial expert personas review the question sequentially. Each expert sees the responses of all prior experts, enabling adversarial refinement. A final synthesis LLM call produces a unified recommendation.

**Trigger:**
- Toolbar button: `🏛 Council` — visible only in `deep_research` and `analyst` modes (hidden in `fast`).
- Slash command: `/council` typed in the chat input — handled in `sendMessage` before the regular dispatch.

### Expert Personas (Sequential Chain)

| Order | Persona | Focus |
|---|---|---|
| 1 | Senior CA | ISA standards, IFRS, audit opinion, financial statements |
| 2 | CPA | UAE Corporate Tax (FDL 47/2022), VAT (FDL 8/2017), cross-border tax |
| 3 | CMA | Management accounting, budgeting, MIS, cost analysis, KPIs |
| 4 | Financial Analyst | Market risk, valuation, ratio analysis, investment perspective |
| 5 | Synthesis | Reconciles all four, produces final recommendation |

Each expert's system prompt lives in `backend/core/chat/prompts/council/` as individual `.md` files:
- `ca_expert.md`
- `cpa_expert.md`
- `cma_expert.md`
- `financial_analyst_expert.md`
- `synthesis.md`

### Backend — `core/council/council_service.py`

```python
async def run_council(query: str, llm, rag, selected_doc_ids) -> AsyncGenerator[dict, None]:
    """Run 4 experts sequentially, each seeing prior responses. Yield SSE events."""
    expert_responses = {}
    for expert in [CA, CPA, CMA, FINANCIAL_ANALYST]:
        yield {"type": "council_expert_start", "expert": expert.name}
        response = ""
        async for chunk in llm.stream(
            build_expert_prompt(expert, query, expert_responses),
            max_tokens=800, temperature=0.2
        ):
            response += chunk
            yield {"type": "council_expert_chunk", "expert": expert.name, "content": chunk}
        expert_responses[expert.name] = response
        yield {"type": "council_expert_done", "expert": expert.name}
    
    # Synthesis
    yield {"type": "council_synthesis_start"}
    async for chunk in llm.stream(
        build_synthesis_prompt(query, expert_responses),
        max_tokens=1000, temperature=0.1
    ):
        yield {"type": "council_synthesis_chunk", "content": chunk}
    yield {"type": "council_done"}
```

New endpoint: `POST /api/chat/council`  
Request: `{"query": "...", "conversation_id": "...", "selected_doc_ids": [...]}`  
Response: SSE stream of council events.

### Frontend — `CouncilPanel` Component

Location: `frontend/src/components/studios/LegalStudio/CouncilPanel.tsx`

**Layout:** Full-height sliding panel (same side as `ResearchPanel`). Contains:
- Header: "🏛 Council Review" + Close button.
- 4 expert cards in a scrollable column. Each card:
  - Header with expert name + role badge.
  - Streams text in real-time as `council_expert_chunk` events arrive.
  - Shows a spinner while waiting for its turn.
  - Greyed-out until the prior expert finishes.
- Synthesis section at the bottom — streams after all 4 experts finish.
- "Send to Chat" button — appends the synthesis as an AI message in the main thread.
- "Download Report" button — exports the full council report as DOCX.

**Hook:** `useCouncil(conversationId)` — mirrors `useDeepResearch` pattern. Manages `experts` state (map of expert name → streamed text), `synthesis` string, and `running` boolean.

### Skill — `skills/council/skill.md`

Documents the four-phase workflow:
1. **Phase 1 — Brainstorm:** Generate 2–3 approaches to the problem.
2. **Phase 2 — Council Review:** Each of the 4 experts gives Pro/Con on each approach.
3. **Phase 3 — Deliberation:** Identify the strongest approach, address critiques.
4. **Phase 4 — Final Recommendation:** Verified, refined plan ready for action.

Gate: available in `deep_research` and `analyst` modes only.

---

## File Change Map

### Backend (Python)

| File | Change |
|---|---|
| `core/research/deep_research_service.py` | try/finally guarantee, per-query timeout, web_sources in answer event |
| `core/deep_research_export.py` | Add `to_branded_docx()` function with TOC + sources appendix with hyperlinks |
| `api/chat.py` or new `api/research.py` | Add `POST /api/research/export/docx` and `POST /api/research/export/pdf` |
| `api/chat.py` | Two-pass intent classification in `send_message`; add `/council` route dispatch |
| `core/council/` (new dir) | `__init__.py`, `council_service.py`, `prompts/council/*.md` |
| `api/chat.py` | Add `POST /api/chat/council` SSE endpoint |

### Frontend (TypeScript/React)

| File | Change |
|---|---|
| `hooks/useDeepResearch.ts` | No change (already handles answer event correctly) |
| `components/studios/LegalStudio/ResearchPanel.tsx` | Add DOCX + PDF download buttons wired to export endpoints |
| `components/studios/LegalStudio/LegalStudio.tsx` | Source name resolution on load; `/council` slash command detection in sendMessage; loading state `finally` block; council button in toolbar; render `CouncilPanel` |
| `components/studios/LegalStudio/ArtifactPanel.tsx` | Add Download DOCX + Download PDF buttons |
| `components/studios/LegalStudio/CouncilPanel.tsx` | New component |
| `hooks/useCouncil.ts` | New hook |
| `components/studios/LegalStudio/AnalystErrorBoundary.tsx` | New component |
| `FinanceStudio.css` / global CSS | Fix `three-pane-layout` height/overflow CSS |

### Skills (Markdown)

| File | Content |
|---|---|
| `skills/deep-research/skill.md` | Deep Research skill — mode-gated to `deep_research` |
| `skills/analyst/skill.md` | Analyst skill — mode-gated to `analyst` |
| `skills/council/skill.md` | Council skill — available in `deep_research` + `analyst` |

---

## Constraints and Non-Goals

- **Fast mode is untouched** — no skills, no council button, no two-pass reasoning overhead in fast mode.
- The two-pass intent classification adds ~200–400ms per message. This is acceptable for Deep Research and Analyst modes but is only applied when `mode !== 'fast'`.
- The LLM Council uses the same `llm` provider configured in settings — no new LLM dependency.
- `python-docx==1.1.2` is confirmed in `requirements.txt` — no new dependency required.
