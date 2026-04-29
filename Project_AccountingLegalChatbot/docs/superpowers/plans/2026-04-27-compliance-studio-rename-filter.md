# Compliance and Analysis Studio — Rename + Mode Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename "Legal Studio" to "Compliance and Analysis Studio" and add a multi-select colour-coded mode filter (Fast / Deep Research / Analyst) to the homepage notebook history.

**Architecture:** Two frontend files only — `NotebookCard.tsx` gains a `mode` field + glowing dot, `HomePage.tsx` gains the filter state + UI and maps `mode` from the API response that already includes it. No backend changes.

**Tech Stack:** React 18, TypeScript, Vitest + @testing-library/react, jsdom

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `frontend/src/components/common/NotebookCard.tsx` | Modify | Add `mode?: string` to `Notebook` interface; add `MODE_COLOURS` map; render glowing dot on thumbnail |
| `frontend/src/components/common/__tests__/NotebookCard.test.tsx` | **Create** | Unit tests for mode dot rendering and colour logic |
| `frontend/src/pages/HomePage.tsx` | Modify | Rename title; map `mode` from API; add `activeModes` state + filter bar; filter notebooks |
| `frontend/src/pages/__tests__/HomePage.test.tsx` | **Create** | Unit tests for title rename, filter logic, and filter UI interaction |

---

## Task 1: Add `mode` field + glowing dot to `NotebookCard`

**Files:**
- Modify: `frontend/src/components/common/NotebookCard.tsx`
- Create: `frontend/src/components/common/__tests__/NotebookCard.test.tsx`

---

- [ ] **Step 1.1 — Write the failing tests**

Create `frontend/src/components/common/__tests__/NotebookCard.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { NotebookCard, type Notebook } from '../NotebookCard';

const baseNotebook: Notebook = {
  id: 'nb-1',
  title: 'Test Notebook',
  updated_at: '2026-04-27T00:00:00Z',
};

describe('NotebookCard — mode dot', () => {
  it('renders no mode dot when mode is undefined', () => {
    render(
      <NotebookCard notebook={baseNotebook} onClick={() => {}} />
    );
    expect(screen.queryByTestId('mode-dot')).not.toBeInTheDocument();
  });

  it('renders a mode dot when mode is "fast"', () => {
    render(
      <NotebookCard notebook={{ ...baseNotebook, mode: 'fast' }} onClick={() => {}} />
    );
    const dot = screen.getByTestId('mode-dot');
    expect(dot).toBeInTheDocument();
    expect(dot).toHaveStyle({ background: '#f59e0b' });
  });

  it('renders a mode dot when mode is "deep_research"', () => {
    render(
      <NotebookCard notebook={{ ...baseNotebook, mode: 'deep_research' }} onClick={() => {}} />
    );
    const dot = screen.getByTestId('mode-dot');
    expect(dot).toBeInTheDocument();
    expect(dot).toHaveStyle({ background: '#6366f1' });
  });

  it('renders a mode dot when mode is "analyst"', () => {
    render(
      <NotebookCard notebook={{ ...baseNotebook, mode: 'analyst' }} onClick={() => {}} />
    );
    const dot = screen.getByTestId('mode-dot');
    expect(dot).toBeInTheDocument();
    expect(dot).toHaveStyle({ background: '#10b981' });
  });

  it('renders no dot for an unknown mode value', () => {
    render(
      <NotebookCard notebook={{ ...baseNotebook, mode: 'unknown_mode' }} onClick={() => {}} />
    );
    expect(screen.queryByTestId('mode-dot')).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 1.2 — Run tests to confirm they fail**

```bash
cd "frontend"
npx vitest run src/components/common/__tests__/NotebookCard.test.tsx
```

Expected: 5 failures — `mode` property does not exist on `Notebook` / `mode-dot` not found.

- [ ] **Step 1.3 — Implement: add `mode` to `Notebook` interface and `MODE_COLOURS` map**

In `frontend/src/components/common/NotebookCard.tsx`, replace the `Notebook` interface (lines 4–11) with:

```typescript
interface Notebook {
  id: string;
  title: string;
  updated_at: string;
  source_count?: number;
  thumbnail_icon?: string;
  domain?: string;
  mode?: string;
}

const MODE_COLOURS: Record<string, string> = {
  fast: '#f59e0b',
  deep_research: '#6366f1',
  analyst: '#10b981',
};
```

- [ ] **Step 1.4 — Implement: render glowing dot in the thumbnail**

In `NotebookCard.tsx`, inside the `<div className="notebook-card__thumb">` block, add the dot **after** the domain icon `<span>` and before the selection `{selectionMode && ...}` block:

```tsx
{notebook.mode && MODE_COLOURS[notebook.mode] && (
  <span
    data-testid="mode-dot"
    style={{
      position: 'absolute',
      top: '8px',
      right: '8px',
      width: '9px',
      height: '9px',
      borderRadius: '50%',
      background: MODE_COLOURS[notebook.mode],
      boxShadow: `0 0 6px ${MODE_COLOURS[notebook.mode]}`,
      pointerEvents: 'none',
    }}
  />
)}
```

- [ ] **Step 1.5 — Run tests to confirm they pass**

```bash
cd "frontend"
npx vitest run src/components/common/__tests__/NotebookCard.test.tsx
```

Expected: 5 tests pass, 0 failures.

- [ ] **Step 1.6 — Commit**

```bash
cd "frontend/.."
git add frontend/src/components/common/NotebookCard.tsx
git add frontend/src/components/common/__tests__/NotebookCard.test.tsx
git commit -m "feat: add mode field and glowing colour dot to NotebookCard

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: Rename title + map `mode` in `HomePage`

**Files:**
- Modify: `frontend/src/pages/HomePage.tsx`
- Create: `frontend/src/pages/__tests__/HomePage.test.tsx`

---

- [ ] **Step 2.1 — Write the failing tests**

Create `frontend/src/pages/__tests__/HomePage.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { API } from '../../lib/api';
import HomePage from '../HomePage';

vi.mock('../../lib/api', () => ({
  API: { get: vi.fn(), delete: vi.fn() },
}));

const mockConversations = [
  { id: 'c1', title: 'VAT Review',    updated_at: '2026-04-27T10:00:00Z', message_count: 2, source_count: 3, domain: 'vat',    mode: 'fast'          },
  { id: 'c2', title: 'Corp Tax Deep', updated_at: '2026-04-26T10:00:00Z', message_count: 4, source_count: 8, domain: 'corporate_tax', mode: 'deep_research' },
  { id: 'c3', title: 'IFRS Analyst',  updated_at: '2026-04-25T10:00:00Z', message_count: 3, source_count: 5, domain: 'audit',   mode: 'analyst'       },
];

function setup() {
  (API.get as any).mockResolvedValue({ data: mockConversations });
  return render(
    <MemoryRouter>
      <HomePage />
    </MemoryRouter>
  );
}

describe('HomePage — title', () => {
  it('shows "Compliance and Analysis Studio" as the page heading', async () => {
    setup();
    expect(await screen.findByText(/Compliance and Analysis Studio/i)).toBeInTheDocument();
  });

  it('does NOT show "Legal Studio" anywhere', async () => {
    setup();
    await screen.findByText(/Compliance and Analysis Studio/i);
    expect(screen.queryByText(/Legal Studio/i)).not.toBeInTheDocument();
  });
});

describe('HomePage — mode mapping', () => {
  it('maps mode from API response onto each notebook', async () => {
    setup();
    // All 3 notebooks render (by title)
    expect(await screen.findByText('VAT Review')).toBeInTheDocument();
    expect(screen.getByText('Corp Tax Deep')).toBeInTheDocument();
    expect(screen.getByText('IFRS Analyst')).toBeInTheDocument();
    // Mode dots — 3 expected
    const dots = await screen.findAllByTestId('mode-dot');
    expect(dots).toHaveLength(3);
  });
});

describe('HomePage — mode filter bar', () => {
  beforeEach(() => {
    (API.get as any).mockResolvedValue({ data: mockConversations });
  });

  it('renders all four filter tags', async () => {
    render(<MemoryRouter><HomePage /></MemoryRouter>);
    expect(await screen.findByRole('button', { name: /all modes/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /fast/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /deep research/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /analyst/i })).toBeInTheDocument();
  });

  it('shows all notebooks by default', async () => {
    render(<MemoryRouter><HomePage /></MemoryRouter>);
    expect(await screen.findByText('VAT Review')).toBeInTheDocument();
    expect(screen.getByText('Corp Tax Deep')).toBeInTheDocument();
    expect(screen.getByText('IFRS Analyst')).toBeInTheDocument();
  });

  it('filters to fast notebooks only when Fast tag is clicked', async () => {
    const { user } = render(<MemoryRouter><HomePage /></MemoryRouter>);
    const fastBtn = await screen.findByRole('button', { name: /fast/i });
    fastBtn.click();
    expect(await screen.findByText('VAT Review')).toBeInTheDocument();
    expect(screen.queryByText('Corp Tax Deep')).not.toBeInTheDocument();
    expect(screen.queryByText('IFRS Analyst')).not.toBeInTheDocument();
  });

  it('filters to analyst notebooks only when Analyst tag is clicked', async () => {
    render(<MemoryRouter><HomePage /></MemoryRouter>);
    const analystBtn = await screen.findByRole('button', { name: /analyst/i });
    analystBtn.click();
    expect(await screen.findByText('IFRS Analyst')).toBeInTheDocument();
    expect(screen.queryByText('VAT Review')).not.toBeInTheDocument();
    expect(screen.queryByText('Corp Tax Deep')).not.toBeInTheDocument();
  });

  it('clicking All Modes resets filter to show all', async () => {
    render(<MemoryRouter><HomePage /></MemoryRouter>);
    const fastBtn = await screen.findByRole('button', { name: /fast/i });
    fastBtn.click();
    const allBtn = screen.getByRole('button', { name: /all modes/i });
    allBtn.click();
    expect(await screen.findByText('VAT Review')).toBeInTheDocument();
    expect(screen.getByText('Corp Tax Deep')).toBeInTheDocument();
    expect(screen.getByText('IFRS Analyst')).toBeInTheDocument();
  });

  it('auto-resets to All when last active mode is deselected', async () => {
    render(<MemoryRouter><HomePage /></MemoryRouter>);
    const fastBtn = await screen.findByRole('button', { name: /fast/i });
    fastBtn.click(); // activate Fast
    fastBtn.click(); // deactivate Fast → should reset to All
    expect(await screen.findByText('Corp Tax Deep')).toBeInTheDocument();
    expect(screen.getByText('IFRS Analyst')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2.2 — Run tests to confirm they fail**

```bash
cd "frontend"
npx vitest run src/pages/__tests__/HomePage.test.tsx
```

Expected: failures — "Legal Studio" still in title, filter buttons not found.

- [ ] **Step 2.3 — Rename the title**

In `frontend/src/pages/HomePage.tsx` line 155, change:

```tsx
<h1 className="home-page__title">📚 Legal Studio</h1>
```

to:

```tsx
<h1 className="home-page__title">📚 Compliance and Analysis Studio</h1>
```

- [ ] **Step 2.4 — Map `mode` from the API response**

In `HomePage.tsx`, update the `useEffect` API mapping (around line 26–32) to include `mode`:

```typescript
setNotebooks(convos
  .filter((c: any) => (c.message_count ?? 1) > 0)
  .map((c: any) => ({
    id: c.id,
    title: c.title || 'Untitled Notebook',
    updated_at: c.updated_at || new Date().toISOString(),
    source_count: c.source_count,
    domain: c.domain,
    mode: c.mode,          // ← add this line
  })));
```

- [ ] **Step 2.5 — Add `activeModes` state and `toggleMode` handler**

At the top of the `HomePage` component function, after the existing `useState` declarations, add:

```typescript
type ModeFilter = 'all' | 'fast' | 'deep_research' | 'analyst';
const [activeModes, setActiveModes] = useState<Set<ModeFilter>>(new Set(['all']));

const toggleMode = (mode: ModeFilter) => {
  if (mode === 'all') {
    setActiveModes(new Set(['all']));
    return;
  }
  setActiveModes(prev => {
    const next = new Set(prev);
    next.delete('all');
    if (next.has(mode)) {
      next.delete(mode);
    } else {
      next.add(mode);
    }
    return next.size === 0 ? new Set<ModeFilter>(['all']) : next;
  });
};
```

- [ ] **Step 2.6 — Update the `filtered` array to respect `activeModes`**

Replace the existing `filtered` declaration (around line 74):

```typescript
// before:
const filtered = notebooks.filter(n =>
  n.title.toLowerCase().includes(search.toLowerCase()),
);
```

with:

```typescript
const filtered = notebooks
  .filter(n => n.title.toLowerCase().includes(search.toLowerCase()))
  .filter(n => activeModes.has('all') || activeModes.has((n.mode ?? 'fast') as ModeFilter));
```

- [ ] **Step 2.7 — Add the filter bar UI**

In `HomePage.tsx`, add the following block **between** the `<div className="home-page__header">` closing tag and the toolbar `<div style={toolbarStyle}>`. Add these style constants above the `return` and the JSX block below:

**Style constants** (add alongside existing style objects):

```typescript
const filterBarStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: '8px',
  flexWrap: 'wrap', marginBottom: '16px',
};

const filterLabelStyle: React.CSSProperties = {
  fontSize: '11px', fontWeight: 600, color: 'var(--s-text-2)',
  textTransform: 'uppercase', letterSpacing: '0.06em', marginRight: '4px',
};

const MODE_META: Record<string, { label: string; icon: string; colour: string }> = {
  fast:          { label: 'Fast',          icon: '⚡', colour: '#f59e0b' },
  deep_research: { label: 'Deep Research', icon: '🔬', colour: '#6366f1' },
  analyst:       { label: 'Analyst',       icon: '📊', colour: '#10b981' },
};

const filterTagStyle = (mode: ModeFilter): React.CSSProperties => {
  const isAll   = mode === 'all';
  const active  = activeModes.has(mode);
  const colour  = isAll ? '#ffffff' : (MODE_META[mode]?.colour ?? '#ffffff');
  return {
    display: 'inline-flex', alignItems: 'center', gap: '6px',
    padding: '5px 14px', borderRadius: '8px',
    fontSize: '12px', fontWeight: 600, cursor: 'pointer',
    transition: 'all 150ms ease',
    background:   active ? `${colour}26` : 'transparent',
    border:       active ? `1.5px solid ${colour}99` : '1.5px dashed rgba(255,255,255,0.12)',
    color:        active ? colour : 'rgba(255,255,255,0.3)',
  };
};
```

**JSX filter bar** (place after `</div>` that closes `home-page__header`, before the toolbar div):

```tsx
{/* Mode filter bar */}
<div style={filterBarStyle}>
  <span style={filterLabelStyle}>Filter</span>

  <button
    type="button"
    role="button"
    aria-label="All Modes"
    style={filterTagStyle('all')}
    onClick={() => toggleMode('all')}
  >
    All Modes
  </button>

  {(['fast', 'deep_research', 'analyst'] as ModeFilter[]).map(mode => {
    const meta = MODE_META[mode];
    return (
      <button
        key={mode}
        type="button"
        role="button"
        aria-label={meta.label}
        style={filterTagStyle(mode)}
        onClick={() => toggleMode(mode)}
      >
        <span style={{
          width: '7px', height: '7px', borderRadius: '50%',
          background: meta.colour, flexShrink: 0,
          boxShadow: activeModes.has(mode) ? `0 0 5px ${meta.colour}` : 'none',
        }} />
        {meta.icon} {meta.label}
      </button>
    );
  })}
</div>
```

- [ ] **Step 2.8 — Run tests to confirm they pass**

```bash
cd "frontend"
npx vitest run src/pages/__tests__/HomePage.test.tsx
```

Expected: all tests pass. If any fail, check that `aria-label` values on buttons exactly match the test queries (case-insensitive).

- [ ] **Step 2.9 — Run full test suite to check for regressions**

```bash
cd "frontend"
npx vitest run
```

Expected: all pre-existing tests still pass. Zero regressions.

- [ ] **Step 2.10 — Commit**

```bash
cd "frontend/.."
git add frontend/src/pages/HomePage.tsx
git add frontend/src/pages/__tests__/HomePage.test.tsx
git commit -m "feat: rename to Compliance and Analysis Studio, add mode filter bar

- Title updated: Legal Studio → Compliance and Analysis Studio
- API mapping now passes mode field to Notebook
- Multi-select colour filter: Fast / Deep Research / Analyst
- auto-reset to All when last active mode deselected

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: Final verification

- [ ] **Step 3.1 — Run full test suite one final time**

```bash
cd "frontend"
npx vitest run
```

Expected: all tests pass (pre-existing + 10 new).

- [ ] **Step 3.2 — Start dev server and manual smoke test**

```bash
cd "frontend"
npm run dev
```

Open `http://localhost:5173` (or wherever Vite binds).

Verify:
1. Page title reads "📚 Compliance and Analysis Studio"
2. Filter bar appears below the title with 4 buttons: All Modes / ⚡ Fast / 🔬 Deep Research / 📊 Analyst
3. Clicking "Fast" hides non-fast notebooks; clicking "All Modes" restores them
4. Each notebook card shows a glowing dot in the top-right of its thumbnail (colour matches mode)
5. No "Legal Studio" text visible anywhere on the home page

- [ ] **Step 3.3 — Final commit if any fixups needed, then push**

```bash
git push origin main
```
