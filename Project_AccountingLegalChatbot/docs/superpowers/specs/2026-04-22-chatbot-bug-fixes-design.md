# Chatbot Bug Fixes Design

## Problem Statement

Four bugs affecting the accounting/legal chatbot UX:
1. Source citations show UUID hash filenames instead of the original document names
2. Markdown formatting (headers, horizontal rules) renders as raw syntax in long chats
3. Deep Research mode completes but shows no answer in the chat
4. Switching to Analyst mode gets silently reset to Fast after the first message

---

## Bug 1 — Sources Showing UUIDs Instead of Proper Names

**Root cause:** Two code locations read the `source` metadata field from ChromaDB, which stores the UUID hash filename. The `original_name` field (which holds the human-readable name) is stored in the same metadata but never used for display.

**Files changed:**
- `backend/core/rag_engine.py` line 342 — `search()` result dict
- `backend/api/chat.py` line 368 — sources list for SSE streaming

**Fix:** In both locations, prefer `original_name` over `source`:
```python
# Before
r["metadata"].get("source", "Unknown")
# After
r["metadata"].get("original_name") or r["metadata"].get("source", "Unknown")
```

No frontend changes needed — the backend now sends the correct name and `SourcesChip` renders whatever string it receives.

---

## Bug 2 — Markdown Formatting Breaks in Long Chats

**Root cause:** The LLM generates `---`, `##`, `###` inline within flowing text (e.g. `answer text --- ## New Section more text`). ReactMarkdown only interprets these as structural elements if they are preceded and followed by blank lines. Without proper line breaks, they render as literal characters.

**Files changed:**
- `frontend/src/components/studios/LegalStudio/ChatMessages.tsx`

**Fix:** Add a `normalizeMarkdown(text)` utility that inserts blank lines around headers and horizontal rules before passing to `<ReactMarkdown>`:
```ts
function normalizeMarkdown(text: string): string {
  return text
    // Ensure --- is on its own line, surrounded by blank lines
    .replace(/([^\n])\s*(---+)\s*([^\n])/g, '$1\n\n$2\n\n$3')
    // Ensure ## headers are preceded by a blank line
    .replace(/([^\n])\n(#{1,6} )/g, '$1\n\n$2');
}
```
Applied in `AIMessage` before: `<ReactMarkdown>{normalizeMarkdown(displayText)}</ReactMarkdown>`

---

## Bug 3 — Deep Research Shows No Answer in Chat

**Root causes (two sub-bugs):**

**3a — Empty RAG context:** `chat.py` line 822 reads `r.get("document", "")` to get the text snippet, but the RAG search result dict uses key `"text"` (not `"document"`). All document snippets are empty strings, so the LLM synthesis has no document context.

**3b — No live streaming, silent completion:** The LLM synthesis collects all chunks into `answer_parts` with no intermediate SSE events. For a 2000-token response, this can take 30–120 seconds. If the response is empty (due to 3a) or the LLM returns nothing, the `answer` event fires with `content: ""`, and the message appears invisible.

**Files changed:**
- `backend/api/chat.py` — fix key + stream chunks + heartbeat
- `frontend/src/hooks/useDeepResearch.ts` — handle chunk events
- `frontend/src/components/studios/LegalStudio/LegalStudio.tsx` — output as ResearchBubble

**Fix 3a:** Change `r.get("document", "")[:600]` → `r.get("text", "")[:600]`

**Fix 3b — Streaming synthesis:**
```python
answer_parts: list[str] = []
async for chunk in llm.chat_stream(messages_for_llm, temperature=0.3, max_tokens=2000):
    answer_parts.append(chunk)
    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
full_answer = "".join(answer_parts)
yield f"data: {json.dumps({'type': 'answer', 'content': full_answer, ...})}\n\n"
```

**Fix 3c — ResearchBubble output (user-requested):**
In `useDeepResearch.ts`, accumulate streaming chunks into a `streamingContent` state. In `LegalStudio.tsx`, replace the current `role: 'ai'` useEffect with one that adds a `role: 'research'` message when `answer` arrives. This uses the `ResearchBubble` component, which renders:
- Formatted markdown report
- Export buttons (PDF / Word / Excel)
- Web sources panel (already shown in ResearchPanel right rail)

```ts
// LegalStudio.tsx useEffect
useEffect(() => {
  if (!answer) return;
  const phases = steps.map(s => ({ phase: s.status, message: s.text }));
  setMessages(prev => [...prev, {
    role: 'research' as const,
    id: crypto.randomUUID(),
    query: lastResearchQuery.current ?? '',
    phases,
    report: answer.content,
    sources: answer.sources.map(s => ({
      source: s.filename, page: s.page ?? '', score: 0, excerpt: '',
    })),
    time: fmtTime(),
  } satisfies ResearchMessage]);
}, [answer]);
```

The `steps` ref is captured at the time `answer` arrives (both are from `useDeepResearch`). A `lastResearchQuery` ref tracks the user's query string.

---

## Bug 4 — Analyst Mode Resets After First Message

**Root cause:** When a new conversation is created in `chat.py` (lines 228–233), the `mode` field is not set — it defaults to `"fast"` in the DB. When the frontend receives the new `conversation_id` in the meta event, `useNotebookMode` resets `manuallySet.current = false` and fetches the conversation. Since the server returns `mode: "fast"`, it overwrites the user's `"analyst"` selection.

**Files changed:**
- `backend/api/chat.py` — pass `mode` on conversation creation

**Fix:**
```python
# Before
conversation = Conversation(
    title=req.message[:80] + ("..." if len(req.message) > 80 else ""),
    llm_provider=req.provider or settings.llm_provider,
    llm_model=settings.active_model,
)
# After
conversation = Conversation(
    title=req.message[:80] + ("..." if len(req.message) > 80 else ""),
    llm_provider=req.provider or settings.llm_provider,
    llm_model=settings.active_model,
    mode=req.mode,
)
```

---

## Scope

- Only fixes the 4 reported bugs
- No schema migrations needed (Conversation.mode column already exists)
- No new dependencies

## Testing

1. Upload a document, ask a question → sources should show the original filename
2. Ask a long question that triggers a structured response → headers and rules should render properly
3. Switch to Deep Research, ask a question → a ResearchBubble with the synthesized answer should appear in the chat
4. Switch to Analyst mode *before* sending a message, then send → mode should stay as Analyst
