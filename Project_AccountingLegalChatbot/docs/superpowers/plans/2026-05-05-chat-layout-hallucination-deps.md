# Chat Layout, Hallucination Guard & Dependencies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the wasted right-side whitespace in chat, stop the LLM from hallucinating URLs in Fast/RAG mode, install 4 missing frontend libraries, and create a living DEPENDENCIES.md that auto-tracks future additions.

**Architecture:**
- T1 — CSS-only: remove `max-width: 720px` from `.chat-msg` so AI messages fill available width.
- T2 — Backend: inject `URL_RULE` into ALL code paths (Fast/RAG mode currently unguarded), then always run `strip_hallucinated_urls` even when `_sources` is empty (strip everything when there's nothing to allow).
- T3 — Frontend: `npm install` 4 missing packages + add type stubs.
- T4 — Docs: create `DEPENDENCIES.md` at repo root, commit, push.

**Tech Stack:** CSS (Vite/React), Python 3.11 (FastAPI, chat.py, citation_validator.py), Node/npm, Markdown

---

## Files Modified / Created

| File | Action | Reason |
|------|--------|--------|
| `frontend/src/index.css` | Modify | Remove 720px cap, set `.chat-msg` to full width |
| `backend/api/chat.py` | Modify | Add URL rule to Fast/RAG path; always strip hallucinated URLs |
| `backend/core/prompt_router.py` | Modify | Add `URL_NO_HALLUCINATE_RULE` constant |
| `backend/core/accuracy/citation_validator.py` | Modify | Accept empty allowed_urls → strip all hyperlinks |
| `frontend/package.json` | Auto-modified by npm | Add 4 packages |
| `DEPENDENCIES.md` | Create | Living dependency manifest with update rule |

---

## Task 1: Fix Chat Layout — Full-Width AI Messages

**Files:**
- Modify: `frontend/src/index.css` (lines 1071–1079 and 1282–1295)

**Root cause:** `.chat-msg { max-width: 720px }` caps AI responses. User wants full available width. User messages stay at 75% (right-aligned bubble is fine narrow).

- [ ] **Step 1: Write failing snapshot/visual test**

```ts
// frontend/src/components/studios/LegalStudio/__tests__/chatLayout.test.ts
import { describe, it, expect } from 'vitest';

describe('chat-msg CSS', () => {
  it('chat-msg has no max-width so AI messages fill container', () => {
    // We verify by reading the compiled index.css content
    // The max-width: 720px line must NOT exist on .chat-msg
    const fs = require('fs');
    const css = fs.readFileSync('src/index.css', 'utf-8');
    // Extract .chat-msg block (up to next rule)
    const match = css.match(/\.chat-msg\s*\{([^}]+)\}/);
    expect(match).not.toBeNull();
    expect(match![1]).not.toMatch(/max-width/);
  });
});
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/frontend
npx vitest run src/components/studios/LegalStudio/__tests__/chatLayout.test.ts --reporter=verbose
```
Expected: FAIL (`max-width` found in `.chat-msg`)

- [ ] **Step 3: Implement — remove max-width from `.chat-msg`, keep user bubble width**

In `frontend/src/index.css`, change line ~1071–1079:

```css
/* BEFORE */
.chat-msg {
  display: flex;
  gap: 12px;
  max-width: 720px;   /* ← REMOVE this line */
}
.chat-msg--user {
  align-self: flex-end;
  flex-direction: row-reverse;
  max-width: 60%;
}
```

```css
/* AFTER */
.chat-msg {
  display: flex;
  gap: 12px;
  width: 100%;        /* ← fills available space */
}
.chat-msg--user {
  align-self: flex-end;
  flex-direction: row-reverse;
  max-width: 60%;     /* user bubbles stay narrow */
}
```

Also update the duplicate block at line ~1283–1295 (`.chat-msg--user .chat-msg__bubble`):
The `.chat-msg__bubble` on AI messages needs to allow full width:

```css
/* In the "chat message redesign" section (~line 1295) add: */
.chat-msg--ai .chat-msg__bubble {
  background: transparent;
  border: none;
  padding: 0;
  width: 100%;        /* ← add this */
}
```

- [ ] **Step 4: Run test — expect PASS**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/frontend
npx vitest run src/components/studios/LegalStudio/__tests__/chatLayout.test.ts --reporter=verbose
```
Expected: PASS

- [ ] **Step 5: Visual check — restart Vite and verify in browser**

```bash
# Vite hot-reloads automatically; just open http://localhost:5173
# Send a test message — AI response should now fill the full chat column width
# User message should still appear as a narrow right-aligned bubble
```

- [ ] **Step 6: Commit**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot
git add frontend/src/index.css frontend/src/components/studios/LegalStudio/__tests__/chatLayout.test.ts
git commit -m "fix(frontend): remove 720px cap — AI chat messages now fill full width

User messages keep max-width: 60% right-aligned bubble.
AI messages use width: 100% to fill available column space.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push origin main
```

---

## Task 2: Fix URL Hallucination — Inject URL Rule in ALL Paths

**Files:**
- Modify: `backend/core/prompt_router.py` — add `URL_NO_HALLUCINATE_RULE` constant
- Modify: `backend/api/chat.py` — inject rule in Fast/RAG path; always strip URLs even with empty source list
- Modify: `backend/core/accuracy/citation_validator.py` — strip ALL links when allowed_urls is empty

**Root cause analysis:**
- The URL rule (`CRITICAL URL RULE: Only include hyperlinks…`) is injected ONLY when web search results exist (line ~772 and ~1546 in chat.py).
- In Fast/RAG mode with RAG results: `strip_hallucinated_urls` is called BUT only if `if _sources:` is truthy. If no RAG sources match → `_sources=[]` → strip is skipped entirely → LLM hallucinate URLs freely.
- In Fast/RAG mode with RAG results present: sources are internal doc filenames, not URLs → `_allowed_urls` contains only doc names → all web-style URLs the LLM generates get stripped ✓ (this path works)
- The broken path: **LLM answers from knowledge (no RAG match, no web search fallback for non-research queries)** → no URL rule → no strip → hallucinated links go out.

**Fix strategy:**
1. Add `URL_NO_HALLUCINATE_RULE` to `prompt_router.py` and append to ALL domain system prompts.
2. In `citation_validator.strip_hallucinated_urls`: when `allowed_urls` is empty, strip ALL markdown hyperlinks (caller passes empty set → zero allowed → remove all).
3. In `chat.py`: always call `strip_hallucinated_urls` regardless of whether `_sources` is populated (remove `if _sources:` guard before the strip call).

- [ ] **Step 1: Write failing test for strip_hallucinated_urls with empty allowed set**

```python
# backend/tests/test_citation_validator.py  (add to existing file)
def test_strip_hallucinated_urls_empty_allowed_removes_all():
    """When no URLs are allowed (no sources), ALL hyperlinks must be stripped."""
    from core.accuracy.citation_validator import strip_hallucinated_urls
    text = "Visit [Beta Consultants](https://www.betaconsultants.com) or [FTA](https://www.fta.gov.ae)"
    result = strip_hallucinated_urls(text, set())
    assert "https://www.betaconsultants.com" not in result
    assert "https://www.fta.gov.ae" not in result
    assert "Beta Consultants" in result  # label kept as plain text
    assert "FTA" in result               # label kept as plain text

def test_strip_hallucinated_urls_allowed_url_kept():
    """URLs in the allowed set must be preserved."""
    from core.accuracy.citation_validator import strip_hallucinated_urls
    text = "See [FTA](https://www.fta.gov.ae) and [fake](https://www.invented.com)"
    result = strip_hallucinated_urls(text, {"https://www.fta.gov.ae"})
    assert "[FTA](https://www.fta.gov.ae)" in result
    assert "https://www.invented.com" not in result
    assert "fake" in result
```

- [ ] **Step 2: Run tests — expect FAIL for first test**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
~/chatbot_venv/bin/python3 -m pytest tests/test_citation_validator.py::test_strip_hallucinated_urls_empty_allowed_removes_all -v
```
Expected: FAIL — current code returns unchanged when `not allowed_urls`.

- [ ] **Step 3: Fix `citation_validator.py` — strip all links when allowed set is empty**

In `backend/core/accuracy/citation_validator.py`, change `strip_hallucinated_urls`:

```python
def strip_hallucinated_urls(answer: str, allowed_urls: set[str]) -> str:
    """Replace markdown hyperlinks whose URLs are NOT in allowed_urls with plain text.

    If allowed_urls is EMPTY, all hyperlinks are stripped (caller has no verified
    sources to allow, so every URL the LLM generated is unverified).

    Keeps the link label so the answer remains readable.
    """
    def _replace(m: re.Match) -> str:
        label, url = m.group(1), m.group(2)
        # Empty set → strip everything; non-empty set → keep only allowed URLs
        if allowed_urls and url in allowed_urls:
            return m.group(0)
        return label

    return re.sub(r'\[([^\]]+)\]\((https?://[^)\s]+)\)', _replace, answer)
```

- [ ] **Step 4: Run both new tests — expect PASS**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
~/chatbot_venv/bin/python3 -m pytest tests/test_citation_validator.py -v -k "strip_hallucinated"
```
Expected: Both PASS

- [ ] **Step 5: Add `URL_NO_HALLUCINATE_RULE` constant to `prompt_router.py`**

After the existing `GROUNDING_RULES` block in `backend/core/prompt_router.py`, add:

```python
URL_NO_HALLUCINATE_RULE = (
    "\n\nURL RULE — always follow:\n"
    "- NEVER invent, guess, or reconstruct a hyperlink from a company name or domain you know.\n"
    "- Only include a markdown hyperlink [Label](URL) when the exact URL was EXPLICITLY provided "
    "in the search results or context above.\n"
    "- If you know a company exists but do not have its URL in the provided context, "
    "write the company name as plain text only — do NOT add a link.\n"
    "- Phone numbers and email addresses follow the same rule: only include them when "
    "explicitly listed in the provided context."
)
```

Then append `+ URL_NO_HALLUCINATE_RULE` to every `DOMAIN_PROMPTS` value (the lines that already end with `+ GROUNDING_RULES + FEW_SHOT_EXAMPLES.get(...)`). For example:

```python
# Each domain prompt currently ends like:
    + FORMATTING_SUFFIX + ABBREVIATION_SUFFIX + GROUNDING_RULES + FEW_SHOT_EXAMPLES.get("vat", "")
# Change to:
    + FORMATTING_SUFFIX + ABBREVIATION_SUFFIX + GROUNDING_RULES + URL_NO_HALLUCINATE_RULE + FEW_SHOT_EXAMPLES.get("vat", "")
```

Apply this to ALL 8 domain entries in `DOMAIN_PROMPTS`.

- [ ] **Step 6: Fix `chat.py` — always strip, regardless of `_sources` being populated**

In `backend/api/chat.py`, find the streaming path block (around line 856):

```python
# BEFORE (buggy — skip strip when no sources):
if _sources:
    _allowed_urls = {s.get("source", "") for s in _sources} | {s.get("href", "") for s in _sources}
    _allowed_urls.discard("")
    full_response = strip_hallucinated_urls(full_response, _allowed_urls)
```

```python
# AFTER (always strip — empty set strips all):
_allowed_urls: set[str] = set()
if _sources:
    _allowed_urls = {s.get("source", "") for s in _sources} | {s.get("href", "") for s in _sources}
    _allowed_urls.discard("")
full_response = strip_hallucinated_urls(full_response, _allowed_urls)
```

Repeat the same pattern for the non-streaming path at ~line 1202:

```python
# BEFORE:
if sources:
    _allowed_urls = {s.get("source", "") for s in sources} | {s.get("href", "") for s in sources}
    _allowed_urls.discard("")
    answer_content = strip_hallucinated_urls(answer_content, _allowed_urls)
```

```python
# AFTER:
_allowed_urls_ns: set[str] = set()
if sources:
    _allowed_urls_ns = {s.get("source", "") for s in sources} | {s.get("href", "") for s in sources}
    _allowed_urls_ns.discard("")
answer_content = strip_hallucinated_urls(answer_content, _allowed_urls_ns)
```

- [ ] **Step 7: Run full backend test suite — no regressions**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
~/chatbot_venv/bin/python3 -m pytest tests/ -v --tb=short -q 2>&1 | tail -30
```
Expected: All existing tests PASS + 2 new tests PASS

- [ ] **Step 8: Manual smoke test**

```bash
curl -s -X POST http://localhost:8002/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"List UAE VAT service providers with their websites","mode":"fast","conversation_id":null}' \
  --no-buffer 2>&1 | python3 -c "
import sys, json
for line in sys.stdin:
    line = line.strip()
    if line.startswith('data:'):
        try:
            d = json.loads(line[5:])
            if d.get('type') == 'chunk': print(d['content'], end='')
        except: pass
" 2>&1 | grep -o '\[.*\](http[^)]*)'
```
Expected: No markdown hyperlinks `[...](https://...)` in output (all stripped because no real sources).

- [ ] **Step 9: Commit**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot
git add backend/core/accuracy/citation_validator.py \
        backend/core/prompt_router.py \
        backend/api/chat.py \
        backend/tests/test_citation_validator.py
git commit -m "fix(backend): close URL hallucination gap in Fast/RAG path

Root cause: strip_hallucinated_urls was skipped when _sources was empty,
letting LLM freely generate fake company website URLs. URL rule was only
injected in web-search paths, not Fast/RAG.

Fixes:
1. citation_validator: empty allowed_urls now strips ALL hyperlinks
2. prompt_router: URL_NO_HALLUCINATE_RULE added to all 8 domain prompts
3. chat.py: always call strip_hallucinated_urls (both streaming and
   non-streaming paths), regardless of _sources being populated

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push origin main
```

---

## Task 3: Install 4 Missing Frontend Libraries

**Files:**
- Auto-modify: `frontend/package.json` (npm install)
- Auto-modify: `frontend/package-lock.json`

**Missing packages:** `remark-math`, `rehype-katex`, `rehype-highlight`, `react-syntax-highlighter` (+ `@types/react-syntax-highlighter`)

- [ ] **Step 1: Write test confirming packages resolve**

```ts
// frontend/src/lib/__tests__/deps.test.ts
import { describe, it, expect } from 'vitest';

describe('required dependencies are importable', () => {
  it('remark-math resolves', async () => {
    const mod = await import('remark-math');
    expect(mod).toBeDefined();
  });
  it('rehype-katex resolves', async () => {
    const mod = await import('rehype-katex');
    expect(mod).toBeDefined();
  });
  it('rehype-highlight resolves', async () => {
    const mod = await import('rehype-highlight');
    expect(mod).toBeDefined();
  });
  it('react-syntax-highlighter resolves', async () => {
    const mod = await import('react-syntax-highlighter');
    expect(mod).toBeDefined();
  });
});
```

- [ ] **Step 2: Run test — expect 4 FAIL**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/frontend
npx vitest run src/lib/__tests__/deps.test.ts --reporter=verbose
```
Expected: 4 FAILs (cannot find module)

- [ ] **Step 3: Install packages**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/frontend
npm install remark-math rehype-katex rehype-highlight react-syntax-highlighter
npm install --save-dev @types/react-syntax-highlighter
```
Expected: 5 packages added, no peer-dep errors

- [ ] **Step 4: Run tests — expect 4 PASS**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/frontend
npx vitest run src/lib/__tests__/deps.test.ts --reporter=verbose
```
Expected: 4 PASS

- [ ] **Step 5: Run full frontend test suite — no regressions**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/frontend
npx vitest run --reporter=verbose 2>&1 | tail -20
```
Expected: All existing tests PASS

- [ ] **Step 6: Commit**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot
git add frontend/package.json frontend/package-lock.json \
        frontend/src/lib/__tests__/deps.test.ts
git commit -m "feat(frontend): install missing dependencies

Added: remark-math, rehype-katex, rehype-highlight,
react-syntax-highlighter, @types/react-syntax-highlighter

These were imported by components but absent from node_modules,
causing runtime errors for math rendering and syntax highlighting.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push origin main
```

---

## Task 4: Create DEPENDENCIES.md with Auto-Update Rule

**Files:**
- Create: `DEPENDENCIES.md` at repo root (`~/chatbot_local/DEPENDENCIES.md`)

**Rule (to be embedded in DEPENDENCIES.md):** Any time a new library/tool is added to frontend (`package.json`), backend (`requirements.txt`), or desktop (`package.json`) — this file MUST be updated and the change committed and pushed in the same PR/commit.

- [ ] **Step 1: Scan current dependencies to build initial content**

```bash
# Backend
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
cat requirements.txt

# Frontend
cd ~/chatbot_local/Project_AccountingLegalChatbot/frontend
cat package.json | python3 -c "
import sys, json
d = json.load(sys.stdin)
deps = d.get('dependencies', {})
dev = d.get('devDependencies', {})
print('=== dependencies ===')
for k,v in sorted(deps.items()): print(f'  {k}: {v}')
print('=== devDependencies ===')
for k,v in sorted(dev.items()): print(f'  {k}: {v}')
"
```

- [ ] **Step 2: Create `DEPENDENCIES.md` at repo root**

Create file at `~/chatbot_local/DEPENDENCIES.md` with the following content (fill in actual versions from step 1 output):

```markdown
# Project Dependencies

> **Rule:** Whenever a library is added, removed, or version-changed in any of the three
> sub-projects (backend, frontend, desktop), this file MUST be updated and committed in
> the same git commit. Push to GitHub immediately after. This keeps DEPENDENCIES.md the
> single source of truth for all third-party tools used in this project.

---

## Backend (`Project_AccountingLegalChatbot/backend/requirements.txt`)

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | (from requirements.txt) | REST API framework |
| uvicorn | … | ASGI server |
| sqlalchemy | … | Async ORM for chat/document DB |
| chromadb | 0.5.15 | Vector store for RAG retrieval |
| httpx | … | Async HTTP client (LLM API calls) |
| openai | … | OpenAI-compatible client (NVIDIA NIM) |
| pydantic | … | Request/response validation |
| python-multipart | … | File upload handling |
| pypdf | … | PDF text extraction |
| python-docx | … | DOCX text extraction |
| nltk | … | Text tokenization for BM25 |
| rank-bm25 | … | BM25 keyword retrieval |
| networkx | … | Graph RAG entity relations |
| sentence-transformers | … | Embedding model for vector search |
| … | … | (add all from requirements.txt) |

## Frontend (`Project_AccountingLegalChatbot/frontend/package.json`)

### Runtime dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| react | … | UI framework |
| react-dom | … | DOM rendering |
| react-router-dom | … | Client-side routing |
| react-markdown | … | Markdown rendering in chat |
| remark-gfm | … | GitHub-Flavoured Markdown plugin |
| remark-math | … | LaTeX math in markdown |
| rehype-katex | … | KaTeX math rendering |
| rehype-highlight | … | Code syntax highlighting (rehype) |
| react-syntax-highlighter | … | Code blocks with language detection |
| recharts | … | Charts in Finance Studio |
| axios | … | HTTP client for API calls |
| lucide-react | … | Icon library |
| @tanstack/react-table | … | Data table component |

### Dev dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| vite | … | Frontend build tool |
| vitest | … | Unit test runner |
| @vitejs/plugin-react | … | React fast-refresh for Vite |
| typescript | … | Static typing |
| @testing-library/react | … | Component test utilities |
| happy-dom | … | Lightweight DOM for tests |

## Desktop (`Project_AccountingLegalChatbot/desktop/`)

> Desktop Electron wrapper — check `desktop/package.json` for current deps.

---

## Update Checklist

When adding a new library:

1. `npm install <pkg>` or `pip install <pkg>` as appropriate
2. Update the relevant table above with package name, version, and purpose
3. `git add DEPENDENCIES.md <lockfile/requirements>`
4. Commit: `docs(deps): add <pkg> for <purpose>`
5. `git push origin <branch>`
```

- [ ] **Step 3: Fill in actual versions from step 1 scan output** (replace all `…` placeholders)

- [ ] **Step 4: Commit and push**

```bash
cd ~/chatbot_local
git add DEPENDENCIES.md
git commit -m "docs(deps): create DEPENDENCIES.md — living library manifest

Documents all backend (requirements.txt), frontend (package.json),
and desktop dependencies in one place.

Rule: update this file + push in the same commit as any library change.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push origin main
```

---

## Final Verification

- [ ] Open http://localhost:5173 → send a long AI response → verify it spans full chat width
- [ ] Send "List UAE VAT service providers with websites" → verify NO `[Company](https://...)` hyperlinks appear in Fast mode response
- [ ] Run `npx vitest run` in frontend → all tests pass
- [ ] Run `pytest tests/ -q` in backend → all tests pass
- [ ] `DEPENDENCIES.md` visible at https://github.com/armaan-hub/Analysis/blob/main/DEPENDENCIES.md
