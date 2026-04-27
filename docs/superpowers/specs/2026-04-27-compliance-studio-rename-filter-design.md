# Design: Compliance and Analysis Studio — Rename + Mode Filter

**Date:** 2026-04-27  
**Status:** Approved

---

## Problem

The homepage is titled "Legal Studio" which no longer reflects the full scope of the app (accounting, tax, compliance, analyst modes). History has no way to filter by conversation mode — all notebooks are shown in one unsorted list regardless of whether they were Fast, Deep Research, or Analyst sessions.

## Proposed Changes

### 1. Studio Rename

`📚 Legal Studio` → `📚 Compliance and Analysis Studio`

Only one source location: `frontend/src/pages/HomePage.tsx` line 155.  
No backend changes. Docs and session files retain their original names (they are historical records).

---

### 2. Homepage Mode Filter

A multi-select colour-coded filter bar added to the hero header area, above the toolbar. Lets users show only notebooks from specific chat modes.

#### Filter tags

| Tag | Colour | Mode value |
|-----|--------|------------|
| All Modes | white/neutral | (no filter — default) |
| ⚡ Fast | Amber `#f59e0b` | `fast` |
| 🔬 Deep Research | Indigo `#6366f1` | `deep_research` |
| 📊 Analyst | Emerald `#10b981` | `analyst` |

#### Interaction rules

- **Default state:** "All Modes" active, others off.
- Clicking a mode tag **toggles** it on/off (multi-select — you can show Fast + Analyst together).
- Clicking "All Modes" clears all mode filters and resets to show everything.
- If all mode tags are deselected, auto-reset to "All Modes" (never show empty).
- Active tags render with their colour background + border; inactive render transparent with faint dashed border.

#### Filter logic (frontend-only)

The `mode` field is already returned by `GET /api/chat/conversations` in `ConversationResponse`. No backend change needed. Filter is pure client-side state — `activeModes: Set<ChatMode | 'all'>`.

```
filteredNotebooks = activeModes.has('all')
  ? notebooks
  : notebooks.filter(n => activeModes.has(n.mode))
```

---

### 3. Mode Dot on Notebook Cards

Each notebook card gets a small glowing colour dot (9 px, `box-shadow: 0 0 6px <colour>`) in the top-right corner of the thumbnail — same colour scheme as the filter tags. This lets users scan the grid by mode at a glance, even without the filter active.

The `Notebook` interface in `NotebookCard.tsx` gains a `mode?: string` field.  
`HomePage.tsx` already maps `c.domain` — it will also map `c.mode`.

---

## Data Flow

```
GET /api/chat/conversations
  └─ ConversationResponse.mode  (already exists, default "fast")
       └─ HomePage maps → Notebook.mode
            ├─ Filter bar reads activeModes state → filters array
            └─ NotebookCard renders coloured dot from mode
```

No migration, no new API endpoints, no backend changes.

---

## Files Changed

| File | Change |
|------|--------|
| `frontend/src/pages/HomePage.tsx` | Rename title · add filter state + UI · pass `mode` to NotebookCard |
| `frontend/src/components/common/NotebookCard.tsx` | Add `mode` to `Notebook` interface · render mode dot on thumb |

---

## Out of Scope

- Renaming the `LegalStudio/` component folder (internal, no user-visible impact)
- Changing the sidebar nav label (separate task)
- Backend filtering / pagination by mode (overkill for current notebook count)
