# Chatbot Redesign — Sub-project A (Foundation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded three-pane layout with a per-conversation mode system (Fast / Deep Research / Analyst) persisted in the DB, fix UUID filenames leaking into the UI, hide sources on non-answers, and unblank the Deep Research screen with a placeholder panel.

**Architecture:** Add a `mode` column on `conversations`; expose it through GET/PATCH endpoints; introduce `useNotebookMode(conversationId)` and `useDocumentResolver(docs)` hooks on the frontend; render one of three layouts (`ChatOnlyLayout`, `ChatWithResearchLayout`, existing `ThreePaneLayout`) based on mode. Everything else (ChatMessages, SourcesSidebar, SourcePeeker) keeps its current structure and only gets small targeted patches.

**Tech Stack:** Backend — FastAPI, SQLAlchemy, SQLite, pytest. Frontend — React 18 + TypeScript + Vite, Vitest + React Testing Library for hook/component tests.

**Spec reference:** `docs/superpowers/specs/2026-04-21-chatbot-redesign-design.md` — Sub-project A (A1–A4).

---

## File Structure

### New files

```
backend/
  db/migrations/add_conversation_mode.py   # one-shot SQLite ALTER + backfill helper
  tests/api/test_conversation_mode.py      # GET/PATCH mode integration tests
  tests/db/test_migration_add_mode.py      # migration idempotency test

frontend/src/
  hooks/
    useNotebookMode.ts                     # mode state + load/save per conversation
    useDocumentResolver.ts                 # UUID / filename → original_name map
  components/studios/LegalStudio/
    ChatOnlyLayout.tsx                     # Fast mode single column
    ChatWithResearchLayout.tsx             # DR two-column (chat + research panel)
    ResearchPanel.tsx                      # A-level placeholder (B replaces inner)
    isSubstantiveAnswer.ts                 # pure helper + test
  hooks/__tests__/useNotebookMode.test.ts
  hooks/__tests__/useDocumentResolver.test.ts
  components/studios/LegalStudio/__tests__/isSubstantiveAnswer.test.ts
  components/studios/LegalStudio/__tests__/ResearchPanel.test.tsx
```

### Modified files

```
backend/
  db/models.py                             # add Conversation.mode column
  api/chat.py                              # mode in GET responses + PATCH endpoint
  main.py                                  # run add_conversation_mode migration on startup

frontend/src/
  components/studios/LegalStudio/ModePills.tsx        # rename 'normal' → 'fast'
  components/studios/LegalStudio/LegalStudio.tsx      # use useNotebookMode, conditional layout
  components/studios/LegalStudio/ChatMessages.tsx     # resolve source names + isSubstantiveAnswer
  components/studios/LegalStudio/SourcesSidebar.tsx   # display original_name
  components/studios/LegalStudio/SourcePeeker.tsx     # resolve title
  lib/api.ts                                          # add patchConversationMode helper
```

Each file has one responsibility. Hooks stay small (<80 lines). Layout files are presentational — no data fetching.

---

## Task 1: Backend — Add `mode` column to Conversation model

**Files:**
- Modify: `backend/db/models.py` — Conversation class
- Create: `backend/db/migrations/__init__.py`
- Create: `backend/db/migrations/add_conversation_mode.py`
- Create: `backend/tests/db/test_migration_add_mode.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/db/test_migration_add_mode.py`:

```python
import sqlite3
import pytest
from db.migrations.add_conversation_mode import run_migration


def _make_legacy_db(tmp_path):
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE conversations ("
        "id TEXT PRIMARY KEY, title TEXT, created_at TEXT)"
    )
    conn.execute("INSERT INTO conversations (id, title, created_at) VALUES "
                 "('c1', 'Old', '2026-04-01')")
    conn.commit()
    conn.close()
    return str(db)


def test_migration_adds_mode_column_and_backfills(tmp_path):
    db_path = _make_legacy_db(tmp_path)

    run_migration(db_path)

    conn = sqlite3.connect(db_path)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(conversations)").fetchall()]
    assert "mode" in cols
    rows = conn.execute("SELECT mode FROM conversations").fetchall()
    assert rows == [("fast",)]
    conn.close()


def test_migration_is_idempotent(tmp_path):
    db_path = _make_legacy_db(tmp_path)
    run_migration(db_path)
    run_migration(db_path)  # must not raise

    conn = sqlite3.connect(db_path)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(conversations)").fetchall()]
    assert cols.count("mode") == 1
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/db/test_migration_add_mode.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'db.migrations.add_conversation_mode'`

- [ ] **Step 3: Create the migration module**

Create `backend/db/migrations/__init__.py` (empty file).

Create `backend/db/migrations/add_conversation_mode.py`:

```python
import sqlite3


def run_migration(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(conversations)").fetchall()]
        if "mode" in cols:
            return
        conn.execute(
            "ALTER TABLE conversations ADD COLUMN mode VARCHAR(20) NOT NULL DEFAULT 'fast'"
        )
        conn.execute(
            "UPDATE conversations SET mode = 'fast' WHERE mode IS NULL OR mode = 'normal'"
        )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/db/test_migration_add_mode.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Add the column to the SQLAlchemy model**

In `backend/db/models.py`, inside the `Conversation` class, add (below existing columns, above any relationships):

```python
    mode = Column(String(20), nullable=False, default="fast")
```

Make sure `String` is already imported from `sqlalchemy`; if not, add it.

- [ ] **Step 6: Wire the migration into startup**

In `backend/main.py`, after the existing DB init call, import and invoke:

```python
from db.migrations.add_conversation_mode import run_migration as _add_conv_mode
from db.database import DB_PATH  # or whatever variable holds the sqlite path

_add_conv_mode(DB_PATH)
```

If `DB_PATH` doesn't exist, read the URL from `config.settings.DATABASE_URL` and strip the `sqlite:///` prefix.

- [ ] **Step 7: Commit**

```bash
git add backend/db/models.py backend/db/migrations/ backend/main.py backend/tests/db/test_migration_add_mode.py
git commit -m "feat(db): add mode column to conversations with startup migration"
```

---

## Task 2: Backend — Expose `mode` in conversation API

**Files:**
- Modify: `backend/api/chat.py` — conversation list/detail/patch endpoints
- Create: `backend/tests/api/test_conversation_mode.py`

- [ ] **Step 1: Write failing integration tests**

Create `backend/tests/api/test_conversation_mode.py`:

```python
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def _create_conversation(title="t"):
    r = client.post("/api/chat/conversations", json={"title": title})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_new_conversation_defaults_to_fast_mode():
    cid = _create_conversation()
    r = client.get(f"/api/chat/conversations/{cid}")
    assert r.status_code == 200
    assert r.json()["mode"] == "fast"


def test_list_includes_mode():
    cid = _create_conversation()
    r = client.get("/api/chat/conversations")
    assert r.status_code == 200
    item = next(x for x in r.json() if x["id"] == cid)
    assert item["mode"] == "fast"


def test_patch_mode_updates_and_persists():
    cid = _create_conversation()
    r = client.patch(f"/api/chat/conversations/{cid}", json={"mode": "analyst"})
    assert r.status_code == 200
    assert r.json()["mode"] == "analyst"

    r2 = client.get(f"/api/chat/conversations/{cid}")
    assert r2.json()["mode"] == "analyst"


def test_patch_mode_rejects_invalid_value():
    cid = _create_conversation()
    r = client.patch(f"/api/chat/conversations/{cid}", json={"mode": "garbage"})
    assert r.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/api/test_conversation_mode.py -v`
Expected: FAIL — either missing field `mode` in responses, or 404/405 on PATCH.

- [ ] **Step 3: Add a Pydantic mode type and include it in responses**

In `backend/api/chat.py`, near the top where other schemas live, add:

```python
from typing import Literal
from pydantic import BaseModel

ConversationMode = Literal["fast", "deep_research", "analyst"]


class ConversationOut(BaseModel):
    id: str
    title: str
    mode: ConversationMode
    created_at: str
    # keep any other existing fields that were already serialized
```

Update the existing `GET /api/chat/conversations` handler to include `mode=conv.mode` in each response item, and `GET /api/chat/conversations/{id}` to return `mode=conv.mode`.

- [ ] **Step 4: Add the PATCH endpoint**

In `backend/api/chat.py`:

```python
class ConversationPatch(BaseModel):
    mode: ConversationMode | None = None
    title: str | None = None


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
def patch_conversation(conversation_id: str, patch: ConversationPatch, db=Depends(get_db)):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conv is None:
        raise HTTPException(404, "Conversation not found")
    if patch.mode is not None:
        conv.mode = patch.mode
    if patch.title is not None:
        conv.title = patch.title
    db.commit()
    db.refresh(conv)
    return ConversationOut(
        id=conv.id, title=conv.title, mode=conv.mode, created_at=str(conv.created_at)
    )
```

If a PATCH route already exists, merge the `mode` handling into it rather than adding a duplicate.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/api/test_conversation_mode.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/api/chat.py backend/tests/api/test_conversation_mode.py
git commit -m "feat(api): expose and patch conversation mode"
```

---

## Task 3: Frontend — `useDocumentResolver` hook

**Files:**
- Create: `frontend/src/hooks/useDocumentResolver.ts`
- Create: `frontend/src/hooks/__tests__/useDocumentResolver.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/hooks/__tests__/useDocumentResolver.test.ts`:

```typescript
import { renderHook } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { useDocumentResolver } from '../useDocumentResolver';

const docs = [
  { id: 'abc-123', filename: '4af67c70-7caf.pdf', original_name: 'Financial_Statements_2024.pdf' },
  { id: 'def-456', filename: 'b9e1.pdf',           original_name: 'Policy.pdf' },
] as any;

describe('useDocumentResolver', () => {
  it('resolves a UUID id to original_name', () => {
    const { result } = renderHook(() => useDocumentResolver(docs));
    expect(result.current.resolve('abc-123')).toBe('Financial_Statements_2024.pdf');
  });

  it('resolves a stored UUID filename to original_name', () => {
    const { result } = renderHook(() => useDocumentResolver(docs));
    expect(result.current.resolve('4af67c70-7caf.pdf')).toBe('Financial_Statements_2024.pdf');
  });

  it('passes through an unknown string unchanged', () => {
    const { result } = renderHook(() => useDocumentResolver(docs));
    expect(result.current.resolve('something-else.txt')).toBe('something-else.txt');
  });

  it('passes through an already-original name', () => {
    const { result } = renderHook(() => useDocumentResolver(docs));
    expect(result.current.resolve('Policy.pdf')).toBe('Policy.pdf');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useDocumentResolver.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the hook**

Create `frontend/src/hooks/useDocumentResolver.ts`:

```typescript
import { useCallback, useMemo } from 'react';

export interface SourceDocLike {
  id: string;
  filename: string;
  original_name: string;
}

export function useDocumentResolver(docs: SourceDocLike[] | undefined) {
  const docMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const doc of docs ?? []) {
      map[doc.id] = doc.original_name;
      map[doc.filename] = doc.original_name;
      map[doc.original_name] = doc.original_name;
    }
    return map;
  }, [docs]);

  const resolve = useCallback(
    (source: string): string => docMap[source] ?? source,
    [docMap],
  );

  return { resolve, docMap };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useDocumentResolver.test.ts`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useDocumentResolver.ts frontend/src/hooks/__tests__/useDocumentResolver.test.ts
git commit -m "feat(hooks): add useDocumentResolver for UUID→original_name mapping"
```

---

## Task 4: Frontend — `isSubstantiveAnswer` helper

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/isSubstantiveAnswer.ts`
- Create: `frontend/src/components/studios/LegalStudio/__tests__/isSubstantiveAnswer.test.ts`

- [ ] **Step 1: Write the failing test**

Create the test file:

```typescript
import { describe, it, expect } from 'vitest';
import { isSubstantiveAnswer } from '../isSubstantiveAnswer';

describe('isSubstantiveAnswer', () => {
  it('returns false for empty content', () => {
    expect(isSubstantiveAnswer('', [{ filename: 'x' } as any])).toBe(false);
  });

  it('returns false when sources array is empty', () => {
    expect(isSubstantiveAnswer('Here is a real answer.', [])).toBe(false);
  });

  it('returns false when content contains a non-answer phrase', () => {
    expect(isSubstantiveAnswer("I don't know the answer.", [{ filename: 'x' } as any])).toBe(false);
    expect(isSubstantiveAnswer("I couldn't find relevant info.", [{ filename: 'x' } as any])).toBe(false);
    expect(isSubstantiveAnswer("No relevant information.", [{ filename: 'x' } as any])).toBe(false);
  });

  it('returns true for a real answer with sources', () => {
    expect(
      isSubstantiveAnswer('UAE VAT standard rate is 5%.', [{ filename: 'x' } as any]),
    ).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/studios/LegalStudio/__tests__/isSubstantiveAnswer.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the helper**

Create `frontend/src/components/studios/LegalStudio/isSubstantiveAnswer.ts`:

```typescript
export interface SourceLike {
  filename?: string;
}

const NON_ANSWER_PHRASES = [
  "i don't know",
  "i couldn't find",
  "no information available",
  "not found in",
  "i don't have",
  "cannot find",
  "no relevant",
];

export function isSubstantiveAnswer(content: string, sources: SourceLike[] | undefined): boolean {
  if (!content?.trim()) return false;
  if (!sources?.length) return false;
  const lower = content.toLowerCase();
  return !NON_ANSWER_PHRASES.some(p => lower.includes(p));
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/studios/LegalStudio/__tests__/isSubstantiveAnswer.test.ts`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/isSubstantiveAnswer.ts frontend/src/components/studios/LegalStudio/__tests__/isSubstantiveAnswer.test.ts
git commit -m "feat: add isSubstantiveAnswer helper for source visibility"
```

---

## Task 5: Frontend — Rename `normal` → `fast` in ModePills

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/ModePills.tsx`

- [ ] **Step 1: Update the type and options**

Replace the full contents of `frontend/src/components/studios/LegalStudio/ModePills.tsx` with:

```typescript
export type ChatMode = 'fast' | 'deep_research' | 'analyst';

const MODE_OPTIONS: { value: ChatMode; label: string; icon: string }[] = [
  { value: 'fast', label: 'Fast', icon: '⚡' },
  { value: 'deep_research', label: 'Deep Research', icon: '🔬' },
  { value: 'analyst', label: 'Analyst', icon: '📊' },
];

const PLACEHOLDERS: Record<ChatMode, string> = {
  fast: 'Ask about your sources…',
  deep_research: 'What would you like to research?',
  analyst: 'What should I analyze?',
};

interface Props {
  value: ChatMode;
  onChange: (mode: ChatMode) => void;
}

export function ModePills({ value, onChange }: Props) {
  return (
    <div className="mode-pills">
      {MODE_OPTIONS.map(opt => (
        <button
          key={opt.value}
          type="button"
          className={`mode-pill${opt.value === value ? ' mode-pill--active' : ''}`}
          onClick={() => onChange(opt.value)}
          aria-pressed={opt.value === value}
        >
          <span>{opt.icon}</span> {opt.label}
        </button>
      ))}
    </div>
  );
}

export { PLACEHOLDERS as MODE_PLACEHOLDERS };
```

- [ ] **Step 2: Fix all compile errors from the rename**

Run: `cd frontend && npx tsc --noEmit`
Expected failures: every file that uses the string `'normal'` against `ChatMode` or reads `PLACEHOLDERS.normal`.

For each error, replace `'normal'` with `'fast'`. Expected hits (confirm via grep, fix all):

```bash
git grep -n "'normal'" frontend/src
git grep -n "\\bnormal\\b" frontend/src/components/studios/LegalStudio
```

In `LegalStudio.tsx` and any other callers that default a mode, change `useState<ChatMode>('normal')` → `useState<ChatMode>('fast')`. Do not touch `'normal'` strings that are not ChatMode related.

- [ ] **Step 3: Verify TypeScript is clean**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/
git commit -m "refactor(modes): rename 'normal' mode to 'fast'"
```

---

## Task 6: Frontend — `useNotebookMode` hook

**Files:**
- Modify: `frontend/src/lib/api.ts` — add `patchConversationMode` helper
- Create: `frontend/src/hooks/useNotebookMode.ts`
- Create: `frontend/src/hooks/__tests__/useNotebookMode.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/hooks/__tests__/useNotebookMode.test.ts`:

```typescript
import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../lib/api', () => ({
  getConversation: vi.fn(),
  patchConversationMode: vi.fn(),
}));

import * as api from '../../lib/api';
import { useNotebookMode } from '../useNotebookMode';

describe('useNotebookMode', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('defaults to fast with no conversation id', () => {
    const { result } = renderHook(() => useNotebookMode(null));
    expect(result.current.mode).toBe('fast');
  });

  it('loads mode from the backend when conversation id changes', async () => {
    (api.getConversation as any).mockResolvedValue({ mode: 'analyst' });
    const { result } = renderHook(() => useNotebookMode('c1'));
    await waitFor(() => expect(result.current.mode).toBe('analyst'));
    expect(api.getConversation).toHaveBeenCalledWith('c1');
  });

  it('falls back to fast if the backend returns no mode', async () => {
    (api.getConversation as any).mockResolvedValue({});
    const { result } = renderHook(() => useNotebookMode('c1'));
    await waitFor(() => expect(result.current.mode).toBe('fast'));
  });

  it('updates local state immediately and calls PATCH in background', async () => {
    (api.getConversation as any).mockResolvedValue({ mode: 'fast' });
    (api.patchConversationMode as any).mockResolvedValue(undefined);
    const { result } = renderHook(() => useNotebookMode('c1'));
    await waitFor(() => expect(result.current.mode).toBe('fast'));

    await act(async () => {
      await result.current.setMode('deep_research');
    });

    expect(result.current.mode).toBe('deep_research');
    expect(api.patchConversationMode).toHaveBeenCalledWith('c1', 'deep_research');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useNotebookMode.test.ts`
Expected: FAIL — hook module missing.

- [ ] **Step 3: Add API helpers**

In `frontend/src/lib/api.ts`, add (adapt to the file's existing style — `axios`, `fetch`, or whatever is already in use there):

```typescript
export async function getConversation(id: string): Promise<{ id: string; mode: string; title: string }> {
  const r = await API.get(`/api/chat/conversations/${id}`);
  return r.data;
}

export async function patchConversationMode(id: string, mode: string): Promise<void> {
  await API.patch(`/api/chat/conversations/${id}`, { mode });
}
```

If a `getConversation` already exists, extend it to return `mode`. Do not duplicate.

- [ ] **Step 4: Implement the hook**

Create `frontend/src/hooks/useNotebookMode.ts`:

```typescript
import { useCallback, useEffect, useState } from 'react';
import { getConversation, patchConversationMode } from '../lib/api';
import type { ChatMode } from '../components/studios/LegalStudio/ModePills';

export function useNotebookMode(conversationId: string | null) {
  const [mode, setModeLocal] = useState<ChatMode>('fast');

  useEffect(() => {
    if (!conversationId) return;
    let cancelled = false;
    getConversation(conversationId)
      .then(r => {
        if (cancelled) return;
        const m = (r?.mode as ChatMode) ?? 'fast';
        setModeLocal(m === 'deep_research' || m === 'analyst' || m === 'fast' ? m : 'fast');
      })
      .catch(() => { /* leave default */ });
    return () => { cancelled = true; };
  }, [conversationId]);

  const setMode = useCallback(async (newMode: ChatMode) => {
    setModeLocal(newMode);
    if (conversationId) {
      try {
        await patchConversationMode(conversationId, newMode);
      } catch {
        /* best effort — UI already switched */
      }
    }
  }, [conversationId]);

  return { mode, setMode };
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useNotebookMode.test.ts`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/useNotebookMode.ts frontend/src/hooks/__tests__/useNotebookMode.test.ts frontend/src/lib/api.ts
git commit -m "feat(hooks): persist per-conversation chat mode via useNotebookMode"
```

---

## Task 7: Frontend — Layout components

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/ChatOnlyLayout.tsx`
- Create: `frontend/src/components/studios/LegalStudio/ChatWithResearchLayout.tsx`
- Create: `frontend/src/components/studios/LegalStudio/ResearchPanel.tsx`
- Create: `frontend/src/components/studios/LegalStudio/__tests__/ResearchPanel.test.tsx`

- [ ] **Step 1: Write failing ResearchPanel test**

Create `frontend/src/components/studios/LegalStudio/__tests__/ResearchPanel.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ResearchPanel } from '../ResearchPanel';

describe('ResearchPanel (A-placeholder)', () => {
  it('renders empty state when no steps', () => {
    render(<ResearchPanel steps={[]} />);
    expect(screen.getByText(/Ask a question to begin deep research/i)).toBeInTheDocument();
  });

  it('renders each step with its status class', () => {
    render(
      <ResearchPanel
        steps={[
          { text: 'Analyzing', status: 'done' },
          { text: 'Searching', status: 'active' },
        ]}
      />,
    );
    expect(screen.getByText('Analyzing')).toHaveClass('research-step--done');
    expect(screen.getByText('Searching')).toHaveClass('research-step--active');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/studios/LegalStudio/__tests__/ResearchPanel.test.tsx`
Expected: FAIL — component missing.

- [ ] **Step 3: Implement ResearchPanel (placeholder level)**

Create `frontend/src/components/studios/LegalStudio/ResearchPanel.tsx`:

```tsx
export interface ResearchStep {
  text: string;
  status: 'pending' | 'active' | 'done' | 'error';
}

interface Props {
  steps: ResearchStep[];
}

export function ResearchPanel({ steps }: Props) {
  return (
    <aside className="research-panel">
      <div className="research-panel__header">🔬 Research Log</div>
      {steps.length === 0 ? (
        <div className="research-panel__empty">
          Ask a question to begin deep research. Results and sources will appear here.
        </div>
      ) : (
        <ul className="research-steps">
          {steps.map((s, i) => (
            <li key={i} className={`research-step research-step--${s.status}`}>
              {s.text}
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/studios/LegalStudio/__tests__/ResearchPanel.test.tsx`
Expected: PASS (2 tests)

- [ ] **Step 5: Implement ChatOnlyLayout**

Create `frontend/src/components/studios/LegalStudio/ChatOnlyLayout.tsx`:

```tsx
import type { ReactNode } from 'react';

interface Props {
  modePills: ReactNode;
  chatArea: ReactNode;
}

export function ChatOnlyLayout({ modePills, chatArea }: Props) {
  return (
    <div className="chat-only-layout">
      <div className="chat-only-layout__pills">{modePills}</div>
      <div className="chat-only-layout__chat">{chatArea}</div>
    </div>
  );
}
```

- [ ] **Step 6: Implement ChatWithResearchLayout**

Create `frontend/src/components/studios/LegalStudio/ChatWithResearchLayout.tsx`:

```tsx
import type { ReactNode } from 'react';

interface Props {
  modePills: ReactNode;
  chatArea: ReactNode;
  researchPanel: ReactNode;
}

export function ChatWithResearchLayout({ modePills, chatArea, researchPanel }: Props) {
  return (
    <div className="chat-research-layout">
      <div className="chat-research-layout__main">
        <div className="chat-research-layout__pills">{modePills}</div>
        <div className="chat-research-layout__chat">{chatArea}</div>
      </div>
      <div className="chat-research-layout__side">{researchPanel}</div>
    </div>
  );
}
```

- [ ] **Step 7: Add minimal CSS hooks**

Append to the stylesheet that already styles `ThreePaneLayout` (search with `git grep "three-pane-layout" frontend/src`):

```css
.chat-only-layout { display:flex; flex-direction:column; height:100%; }
.chat-only-layout__pills { padding: 8px 16px; }
.chat-only-layout__chat { flex:1; min-height:0; overflow:auto; }

.chat-research-layout { display:flex; height:100%; }
.chat-research-layout__main { flex:1; display:flex; flex-direction:column; min-width:0; }
.chat-research-layout__pills { padding: 8px 16px; }
.chat-research-layout__chat { flex:1; min-height:0; overflow:auto; }
.chat-research-layout__side { width: 340px; border-left: 1px solid var(--border, rgba(255,255,255,0.08)); overflow:auto; }

.research-panel { padding: 12px; }
.research-panel__header { font-weight: 600; margin-bottom: 8px; }
.research-panel__empty { opacity: 0.6; font-size: 14px; }
.research-steps { list-style:none; padding:0; margin:0; display:flex; flex-direction:column; gap:6px; }
.research-step--done::before { content:'✅ '; }
.research-step--active::before { content:'🔄 '; }
.research-step--error::before { content:'⚠️ '; }
.research-step--pending::before { content:'⏳ '; }
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/
git commit -m "feat(layouts): add ChatOnly, ChatWithResearch, and placeholder ResearchPanel"
```

---

## Task 8: Frontend — Wire mode + layouts into LegalStudio

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`

- [ ] **Step 1: Locate the render block**

Run: `cd frontend && git grep -n "ThreePaneLayout" src/components/studios/LegalStudio/LegalStudio.tsx`
Read the file and identify:
- The line that instantiates local `mode` state (will be removed).
- The line that returns `<ThreePaneLayout ... />`.
- Where `conversationId` is available in scope.

- [ ] **Step 2: Replace local mode state with the hook**

At the top of the component (alongside other hooks), replace:

```typescript
const [mode, setMode] = useState<ChatMode>('normal'); // or similar
```

with:

```typescript
import { useNotebookMode } from '../../../hooks/useNotebookMode';
// ...inside component:
const { mode, setMode } = useNotebookMode(conversationId ?? null);
```

Adjust the import path to match relative depth.

- [ ] **Step 3: Extract the render pieces and branch on mode**

Near the return, build the three pieces once, then branch:

```tsx
import { ChatOnlyLayout } from './ChatOnlyLayout';
import { ChatWithResearchLayout } from './ChatWithResearchLayout';
import { ResearchPanel } from './ResearchPanel';
// ... existing imports

const modePills = <ModePills value={mode} onChange={setMode} />;
const chatArea  = (
  /* the existing JSX that was the `center` prop of ThreePaneLayout */
);

if (mode === 'fast') {
  return <ChatOnlyLayout modePills={modePills} chatArea={chatArea} />;
}
if (mode === 'deep_research') {
  return (
    <ChatWithResearchLayout
      modePills={modePills}
      chatArea={chatArea}
      researchPanel={<ResearchPanel steps={[]} />}
    />
  );
}
return (
  <ThreePaneLayout
    left={/* existing sourcesSidebar */}
    center={chatArea}
    right={/* existing studioPanel */}
  />
);
```

Keep all existing props passed to `ThreePaneLayout`; move their expressions into `const` bindings above so they're reused by the other layouts where applicable.

- [ ] **Step 4: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 5: Smoke-test manually**

Run: `cd frontend && npm run dev` and `cd backend && uv run python main.py`.
- Open the app, create a new conversation — layout defaults to Fast (single column).
- Click **Deep Research** pill — two-column layout with research log empty state on the right.
- Click **Analyst** pill — full three-pane layout returns.
- Reload the page — the last-selected mode is restored from the backend.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/LegalStudio.tsx
git commit -m "feat(studio): mode-conditional layouts wired via useNotebookMode"
```

---

## Task 9: Frontend — Resolve source names in SourcesSidebar + SourcePeeker

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/SourcesSidebar.tsx`
- Modify: `frontend/src/components/studios/LegalStudio/SourcePeeker.tsx`

- [ ] **Step 1: Audit current displays**

Run: `cd frontend && git grep -n "filename" src/components/studios/LegalStudio/SourcesSidebar.tsx src/components/studios/LegalStudio/SourcePeeker.tsx`

Every `doc.filename` / `source.filename` used as display text must become `doc.original_name` (or, for citations, resolved via the hook).

- [ ] **Step 2: Update SourcesSidebar**

In `SourcesSidebar.tsx`, at each place that renders `doc.filename` as the user-visible label, replace with `doc.original_name ?? doc.filename`.

The `SourceDoc` type already includes `original_name` per the spec — confirm by reading the interface at the top of the file. If the field is missing in the local type, add it:

```typescript
interface SourceDoc {
  id: string;
  filename: string;
  original_name: string;
  // …existing fields
}
```

- [ ] **Step 3: Update SourcePeeker**

In `SourcePeeker.tsx`, wherever the title bar renders the filename, replace with `original_name`. Accept `original_name` as a prop if not already present.

- [ ] **Step 4: Typecheck and smoke test**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean.

Manually verify an uploaded doc shows its human-readable name in the sidebar and the peeker title.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/SourcesSidebar.tsx frontend/src/components/studios/LegalStudio/SourcePeeker.tsx
git commit -m "fix(sources): display original_name instead of UUID filename"
```

---

## Task 10: Frontend — Resolve citations + conditional sources in ChatMessages

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/ChatMessages.tsx`

- [ ] **Step 1: Locate the sources render block**

Run: `cd frontend && git grep -n "sources" src/components/studios/LegalStudio/ChatMessages.tsx`
Identify the JSX that renders the per-message source citations.

- [ ] **Step 2: Add the resolver and substantive check**

At the top of the component (after existing hooks), add:

```typescript
import { useDocumentResolver } from '../../../hooks/useDocumentResolver';
import { isSubstantiveAnswer } from './isSubstantiveAnswer';

const { resolve } = useDocumentResolver(docs); // `docs` = the same prop SourcesSidebar uses
```

If the component does not already receive `docs`, thread the `SourceDoc[]` list down from `LegalStudio.tsx` as a prop.

- [ ] **Step 3: Gate the sources block**

Wrap the existing sources render in:

```tsx
{isSubstantiveAnswer(message.content, message.sources) && (
  <div className="chat-sources">
    {message.sources.map((s, i) => (
      <span key={i} className="chat-source">{resolve(s.filename ?? s)}</span>
    ))}
  </div>
)}
```

Adapt the inner mapping to whatever shape `message.sources` has in the current code — the key action is: (a) skip rendering entirely when `isSubstantiveAnswer` is false, and (b) pass the raw source string through `resolve()` before display.

- [ ] **Step 4: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 5: Manual smoke test**

- Ask a real question against a document — citations appear with human-readable names.
- Ask a question the docs don't cover — assistant replies *"I don't know"* and the sources block is hidden.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/ChatMessages.tsx
git commit -m "fix(chat): resolve citation names and hide sources on non-answers"
```

---

## Task 11: Regression pass + full test suites

- [ ] **Step 1: Backend tests**

Run: `cd backend && uv run pytest -q`
Expected: all pass (including the two new test files added above).

- [ ] **Step 2: Frontend tests**

Run: `cd frontend && npx vitest run`
Expected: all pass (including the four new test files).

- [ ] **Step 3: TypeScript**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Final manual verification against the Sub-project A checklist**

Walk the spec's Sub-project A checklist in the browser:

- [ ] Switching mode pills updates layout immediately
- [ ] Mode persists after page reload (DB-backed)
- [ ] Source sidebar shows `original_name`, not UUID filename
- [ ] Source citations in chat show resolved names
- [ ] Sources hidden when LLM responds with "I don't know"
- [ ] Deep Research mode no longer shows blank screen

- [ ] **Step 5: Commit any doc touch-ups**

If the testing pass surfaced any follow-up (a stale comment, a missed rename), commit it as a final cleanup:

```bash
git add -A
git commit -m "chore: Sub-project A cleanup"
```

Sub-project A is complete. Sub-project B (Deep Research) and Sub-project C (Analyst) can now proceed — they each consume the Fast/DR/Analyst mode contract established here.
