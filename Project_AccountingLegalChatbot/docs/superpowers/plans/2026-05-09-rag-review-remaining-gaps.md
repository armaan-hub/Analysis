# RAG Review — Remaining UI Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close three remaining polish gaps after the core RAG overhaul: (1) fast-model dropdown in Settings, (2) frontend "no sources" visual badge in chat, and (3) PROJECT_JOURNAL.md update.

**Architecture:** Pure frontend + documentation changes. No backend changes needed. All 439 docs are indexed, 0 failures, E2E verified working. These are UI polish items only.

**Tech Stack:** React 18 + TypeScript (frontend), pytest (tests already passing), Markdown (journal).

---

## Current State (as of 2026-05-09)

- ✅ 439 documents ingested, 0 failures, 58,517 chunks in DB, 57,387 vectors in ChromaDB
- ✅ E2E query "Federal Decree-Law No. 50 of 2022 cheque bounce" → 15 sources, correct law, no hallucination
- ✅ All 22 RAG tests pass (677 total pass)
- ✅ ChromaDB "Error finding id" bug fixed and committed (325ef209)
- ✅ `/api/documents/search` doc_id kwarg bug fixed and committed

---

## File Map

| File | Change |
|---|---|
| `frontend/src/pages/SettingsPage.tsx` | Fast model: `<input>` → `<select>` when models loaded |
| `frontend/src/components/studios/LegalStudio/ChatMessages.tsx` | Detect `⚠ No matching` prefix → styled warning banner |
| `PROJECT_JOURNAL.md` | Append session summary entry |

---

### Task 1: Fast Model `<select>` Dropdown

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx:363-369`

The main model field already uses `models.length > 0 ? <select> : <input>` (lines 304-320).
The fast model field (lines 362-370) always uses `<input type="text">`. Apply the same pattern.

- [ ] **Step 1: Locate the fast model input block**

Open `frontend/src/pages/SettingsPage.tsx`. Find lines ~361-371:
```tsx
<div className="settings-field" style={{ marginBottom: 0 }}>
  <label className="settings-label" style={{ fontSize: '0.78rem' }}>Fast Mode Model</label>
  <input
    type="text"
    className="settings-input"
    placeholder="e.g. deepseek-ai/deepseek-v3.1-terminus"
    value={editFastModel}
    onChange={e => setEditFastModel(e.target.value)}
  />
</div>
```

- [ ] **Step 2: Replace with conditional `<select>` / `<input>`**

Replace the `<div className="settings-field" ...>` block (lines ~361-370) with:
```tsx
<div className="settings-field" style={{ marginBottom: 0 }}>
  <label className="settings-label" style={{ fontSize: '0.78rem' }}>Fast Mode Model</label>
  {models.length > 0 ? (
    <select
      className="settings-input settings-select"
      value={editFastModel}
      onChange={e => setEditFastModel(e.target.value)}
    >
      <option value="">— select fast model —</option>
      {models.map(m => <option key={m} value={m}>{m}</option>)}
    </select>
  ) : (
    <input
      type="text"
      className="settings-input"
      placeholder="e.g. deepseek-ai/deepseek-v3.1-terminus"
      value={editFastModel}
      onChange={e => setEditFastModel(e.target.value)}
    />
  )}
</div>
```

**Why `models` is available here:** The `models` state (line ~56, `const [models, setModels] = useState<string[]>([])`) is already populated by the `loadModels()` effect when a provider is selected. It's in scope for this JSX block — same as the main model field.

- [ ] **Step 3: Verify in browser**

1. Start dev server: `cd frontend && npm run dev`
2. Navigate to Settings page
3. Select the NVIDIA provider — click "Refresh" or wait for models to load
4. Under "⚡ Fast Mode Configuration", the "Fast Mode Model" field should now show a dropdown with the same model list as the main model field
5. Selecting a value should update the form (save works as before)

- [ ] **Step 4: Commit**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot
git add frontend/src/pages/SettingsPage.tsx
git commit -m "feat(ui): fast mode model as <select> when provider models are loaded

Mirrors the same conditional pattern already used for the main model
field. When provider has hasFastModel=true and models are available
from the API, shows a <select> with an empty '— select —' option.
Falls back to <input type='text'> if no models loaded (e.g. Groq
with no API key yet).

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push origin main
```

---

### Task 2: Frontend "No Sources" Visual Badge in Chat

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/ChatMessages.tsx`

The backend injects `_NO_SOURCES_DISCLAIMER` as plain text at the start of the AI message:
```
⚠ No matching documents found in my knowledge base for this query.
The following answer is based on my general training knowledge only and may not reflect current UAE law or regulations. Always verify with official sources.

---

[LLM answer here...]
```

Currently this disclaimer appears as markdown text inside the bubble. We want to detect it and render a styled yellow/amber warning banner above the answer text instead.

- [ ] **Step 1: Write a failing test**

Create `frontend/src/components/studios/LegalStudio/__tests__/ChatMessages.test.tsx` (if it doesn't exist, skip — frontend tests not configured in this project). Instead, verify visually in Step 4.

- [ ] **Step 2: Add disclaimer detection constant and helper**

At the top of `ChatMessages.tsx`, after the imports and before `SUGGESTIONS`, add:

```tsx
const NO_SOURCES_PREFIX = '⚠ No matching documents found in my knowledge base';

function parseDisclaimer(text: string): { hasDisclaimer: boolean; cleanText: string } {
  if (text.startsWith(NO_SOURCES_PREFIX)) {
    // Split on the markdown separator "---" to get the actual answer
    const sepIdx = text.indexOf('\n\n---\n\n');
    if (sepIdx !== -1) {
      return { hasDisclaimer: true, cleanText: text.slice(sepIdx + 7).trim() };
    }
    // Fallback: strip the first two paragraphs (disclaimer block)
    const parts = text.split('\n\n');
    return { hasDisclaimer: true, cleanText: parts.slice(2).join('\n\n').trim() };
  }
  return { hasDisclaimer: false, cleanText: text };
}
```

- [ ] **Step 3: Use `parseDisclaimer` in `AIMessage`**

In the `AIMessage` function (line ~77), replace:
```tsx
const displayText = parsed ? parsed.answer : (msg.text || ' ');
```
with:
```tsx
const rawText = parsed ? parsed.answer : (msg.text || ' ');
const { hasDisclaimer, cleanText } = parseDisclaimer(rawText);
const displayText = cleanText || ' ';
```

Then inside the JSX bubble, before `<ReactMarkdown ...>`, add:
```tsx
{hasDisclaimer && (
  <div style={{
    background: 'rgba(255, 190, 0, 0.12)',
    border: '1px solid rgba(255, 190, 0, 0.4)',
    borderRadius: '6px',
    padding: '8px 12px',
    marginBottom: '10px',
    fontSize: '0.82rem',
    color: 'var(--text-1)',
    display: 'flex',
    alignItems: 'flex-start',
    gap: '8px',
  }}>
    <span style={{ fontSize: '1rem', flexShrink: 0 }}>⚠️</span>
    <span>
      <strong>No matching documents found</strong> in the knowledge base for this query.
      Answer is from general training only — verify with official sources.
    </span>
  </div>
)}
```

Full updated `AIMessage` function for reference:
```tsx
function AIMessage({ msg, onSourceClick, resolve }: { msg: Message; onSourceClick: (s: Source) => void; activeSourceId?: string; resolve: (path: string) => string }) {
  if (msg.role === 'research') return null;
  
  const [showThinking, setShowThinking] = useState(false);
  const parsed = parseThinking(msg.text || '');
  const rawText = parsed ? parsed.answer : (msg.text || ' ');
  const { hasDisclaimer, cleanText } = parseDisclaimer(rawText);
  const displayText = cleanText || ' ';

  return (
    <div className="chat-msg chat-msg--ai">
      <DiamondIcon />
      <div className="chat-msg__body">
        <div className="chat-msg__bubble report-markdown">
          {msg.queriesRun && msg.queriesRun.length > 0 && (
            <SearchIndicator queries={msg.queriesRun} />
          )}
          {parsed && (
            <>
              <button type="button" className="chat-thinking-toggle" onClick={() => setShowThinking(v => !v)}>
                <span>◆</span> Show thinking {showThinking ? '▲' : '▾'}
              </button>
              {showThinking && (
                <div className="chat-thinking-content">{parsed.thinking}</div>
              )}
            </>
          )}
          {hasDisclaimer && (
            <div style={{
              background: 'rgba(255, 190, 0, 0.12)',
              border: '1px solid rgba(255, 190, 0, 0.4)',
              borderRadius: '6px',
              padding: '8px 12px',
              marginBottom: '10px',
              fontSize: '0.82rem',
              color: 'var(--text-1)',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '8px',
            }}>
              <span style={{ fontSize: '1rem', flexShrink: 0 }}>⚠️</span>
              <span>
                <strong>No matching documents found</strong> in the knowledge base for this query.
                Answer is from general training only — verify with official sources.
              </span>
            </div>
          )}
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{normalizeMarkdown(displayText)}</ReactMarkdown>
        </div>
        {msg.sources && msg.sources.length > 0 && isSubstantiveAnswer(msg.text || '', msg.sources) && (
          <SourcesChip sources={msg.sources} onSourceClick={onSourceClick} resolveName={resolve} />
        )}
        {msg.messageId && (
          <ChatMessageActions
            messageId={msg.messageId}
            content={msg.text || ''}
            hasTable={(msg.text || '').includes('|---|') || (msg.text || '').includes('| ---')}
          />
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Verify in browser**

To trigger "no sources" for testing (if RAG is working, queries return sources normally):
1. Temporarily ask a completely nonsensical query like "banana quantum unicorn dance"
2. If backend returns disclaimer, the chat should show the amber warning banner above the answer
3. The `---` separator and disclaimer text should NOT appear in the rendered markdown

- [ ] **Step 5: Commit**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot
git add frontend/src/components/studios/LegalStudio/ChatMessages.tsx
git commit -m "feat(ui): styled warning banner when RAG returns no matching documents

Detects the backend _NO_SOURCES_DISCLAIMER prefix ('⚠ No matching
documents found...') and renders an amber warning banner above the
LLM answer instead of showing raw disclaimer text in the markdown.
The separator and disclaimer block are stripped from the displayed text.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push origin main
```

---

### Task 3: Update PROJECT_JOURNAL.md

**Files:**
- Modify: `PROJECT_JOURNAL.md` (at repo root: `35. 11-Apr-2026 Agentic AI/PROJECT_JOURNAL.md`)

Per workflow rules, every major session must add a summary entry.

- [ ] **Step 1: Append session entry to PROJECT_JOURNAL.md**

Open `/Users/armaan/Library/CloudStorage/GoogleDrive-armaanmishra86@gmail.com/My Drive/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI/PROJECT_JOURNAL.md`

Append this entry at the END of the file:

```markdown
---

## Session: 2026-05-09 — RAG Fix Once For All (5th & Final Attempt)

### Problem
LLM was hallucinating law citations (e.g., wrong law for "rent cheque bounce in Dubai") because
the RAG system was returning 0 results on every query. Root causes identified through audit:
1. ChromaDB 1.5.8 Rust u64/BLOB type corruption causing vector store failures
2. NVIDIA embedding 512-token limit exceeded (chunk_size was 1000, should be 350 chars)
3. 62 data source files (subdirectories) never ingested — `os.listdir()` only found root-level files
4. ChromaDB "Error executing plan: Internal error: Error finding id" not caught in error handler
5. `/api/documents/search` passed wrong kwarg `doc_id=` to `rag_engine.search()` (expects `filter=`)

### What Was Built (8 tasks + 2 critical bug fixes)
- **T1**: `DocumentChunk` ORM table — persistent chunk text storage, source of truth for re-embedding
- **T2**: `OllamaEmbeddingProvider` + provider-aware chunk sizing (350 chars NVIDIA, 1200 Ollama)
- **T3**: ChromaDB corruption recovery (`_reinit_client()` + retry on BLOB/segment/u64 errors)
- **T4**: `scan_and_ingest_all()` with `os.walk()` recursive discovery — found all 439 PDFs
- **T5**: `_NO_SOURCES_DISCLAIMER` injected in both streaming + non-streaming chat paths
- **T6**: `Document.needs_reindex` column + fingerprint change detection at startup
- **T7**: Settings UI embedding provider card (status badge, re-index all button)
- **T8**: Full E2E ingest — 439 docs, 58,517 chunks, 57,387 vectors
- **Bug fix**: Extended ChromaDB error handler to catch "executing plan"/"error finding id"
- **Bug fix**: Fixed `/api/documents/search` kwarg mismatch

### Verification
- E2E query "Federal Decree-Law No. 50 of 2022 cheque bounce in Dubai" → 15 sources,
  `DecreeLaw_50_2022_pdf.pdf` at top (score 0.47), correct law cited, no hallucination
- 22 RAG tests pass, 677 total tests pass
- 0 failed documents (all 439 indexed)

### Key Architecture Decisions
- NVIDIA embedding stays at 350-char chunks (512 NVIDIA token limit)
- ChromaDB reinit + retry is the recovery strategy (not rebuild on every error)
- `general_law` domain suppression threshold: 0.35 (vectors needed to pass)
- No domain filter applied for `general_law` queries — all docs eligible

### Commits
- 9d0ca059..325ef209 (11 commits) — all pushed to origin/main
```

- [ ] **Step 2: Commit journal entry**

```bash
cd "/Users/armaan/Library/CloudStorage/GoogleDrive-armaanmishra86@gmail.com/My Drive/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI"
git add PROJECT_JOURNAL.md
git commit -m "docs: 2026-05-09 RAG fix session summary in PROJECT_JOURNAL.md

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push origin main
```

---

## Self-Review Checklist

### Spec Coverage
- ✅ Fast model `<select>` dropdown — T1
- ✅ Frontend "no sources" visual badge — T2
- ✅ PROJECT_JOURNAL.md update — T3
- ✅ No backend changes needed (all backend gaps already closed)

### Not Included (deliberately out of scope)
- `provider=anthropic` routing: The frontend correctly uses `claude` key. `settings.py` `_KEY_MAP` has `"claude"` entry. No bug exists.
- Background auto-reindex job: User has Re-Index All button in Settings. Auto-job adds complexity without clear trigger.
- Arabic PDF / .doc handling: All 439 docs now show `status=indexed` — no failures remain.

### Placeholder Check
None — all steps contain actual code with exact line numbers.

### Type Consistency
- `parseDisclaimer` returns `{ hasDisclaimer: boolean; cleanText: string }` — used consistently in T2
- `models` state (already `string[]`) used for `<select>` — consistent with main model field pattern
