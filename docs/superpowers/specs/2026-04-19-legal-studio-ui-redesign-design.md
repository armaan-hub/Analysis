# Legal Studio UI Redesign — Design Spec

**Date:** 2026-04-19  
**Status:** Draft  
**Scope:** Complete UI/UX overhaul of the Legal Intelligence Studio frontend

---

## 1. Problem Statement

The current Legal Studio UI has 8 critical issues identified from user testing:

1. **Mode dropdown looks like a button** — not discoverable as a selector
2. **Oversized upload banner** — takes too much vertical space in Sources panel
3. **Cluttered sources panel** — no type indicators, no search, hard to scan
4. **Broken attachment in audit mode** — nothing works when attaching files
5. **Too many panes (4-5 columns)** — should be strictly 3 columns
6. **Bad empty state design** — not inviting, poor UX
7. **Missing template preview for audit format** — can't see format before export
8. **Inconsistent layout across modes** — layout shifts when switching modes

## 2. Design Decisions (User-Confirmed)

| Decision | Choice |
|---|---|
| Attachment model | Both: `+` in chat input (quick-attach) AND Sources panel (permanent library) |
| Finance Studio | Separate app with handoff from Legal Studio |
| Report location | Right-side Studio panel; chat + analysis in middle |
| Landing page | Card grid of notebooks (NotebookLM-style) |
| Layout constraint | **Strictly 3-column**: Sources \| Chat \| Studio |
| Mode selector style | Pill chips below the input box (like Google Gemini) |
| Notebook card info | Title + date + thumbnail preview of first source |
| Studio panel content | Report type cards + auditor format grid + export |
| Source upload | Multi-select file picker (select multiple files at once) |

## 3. Architecture

### 3.1 Page Structure

```
App
├── HomePage (route: /)
│   └── NotebookGrid — card grid of notebooks
│       ├── NotebookCard — title, date, thumbnail
│       └── CreateNotebookCard — dashed "+" card
│
└── NotebookPage (route: /notebook/:id)
    └── ThreePaneLayout
        ├── SourcesPanel (left, 260px)
        ├── ChatPanel (middle, flex-1)
        └── StudioPanel (right, 300px)
```

### 3.2 Component Tree

```
ThreePaneLayout
├── SourcesPanel
│   ├── SourcesHeader (title + count + add button)
│   ├── SourceSearch
│   ├── SourceList
│   │   └── SourceItem[] (icon + name + meta + checkbox)
│   ├── AddSourcesOverlay (drag-drop + browse + URL)
│   └── EmptySourcesState
│
├── ChatPanel
│   ├── ChatMessages
│   │   └── MessageBubble[] (user/ai)
│   └── ChatInputArea
│       ├── AttachButton (+)
│       ├── TextInput
│       ├── SendButton
│       ├── AttachedFileChips[]
│       └── ModePills (Normal / Deep Research / Analyst)
│
└── StudioPanel
    ├── StudioCards (default view)
    │   ├── ReportCard (Audit Report)
    │   ├── ReportCard (Case Summary)
    │   ├── ReportCard (Analysis Report)
    │   ├── AuditorFormatGrid
    │   │   └── FormatOption[] (Standard / Big 4 / Legal Brief / Compliance)
    │   └── ExportButton
    └── ReportPreview (after generating)
        ├── BackButton
        ├── FormatBadge
        ├── PreviewContent (live-updating)
        └── ExportButton
```

## 4. Component Specifications

### 4.1 HomePage — NotebookGrid

**Purpose:** Landing page showing all user notebooks as cards, like NotebookLM's home page.

**Layout:** CSS Grid, `grid-template-columns: repeat(auto-fill, minmax(220px, 1fr))`, gap 16px.

**NotebookCard contents:**
- Thumbnail area (100px height) — preview of first source or type icon
- Title (0.9rem, single line, ellipsis overflow)
- Meta line: date + source count (0.72rem, muted)

**CreateNotebookCard:**
- Dashed border, `+` icon, "Create New Notebook" label
- On click: creates new notebook, navigates to NotebookPage

**Interactions:**
- Click card → navigate to `/notebook/:id`
- Hover → border highlight (blue)

### 4.2 SourcesPanel (Left, 260px)

**Purpose:** Manage document sources for the current notebook. Sources are permanent (persisted to backend).

**Header:** "Sources" title + count badge + circular blue `+` button.

**Search:** Small search input with magnifier icon. Filters source list by name.

**Source list:** Scrollable. Each SourceItem has:
- **Type icon** (28×28px, colored by type):
  - PDF → red bg, "PDF"
  - DOC → blue bg, "DOC"
  - TXT → purple bg, "TXT"
  - URL → green bg, "URL"
  - CSV → yellow bg, "CSV"
- **Name** (0.78rem, ellipsis on overflow)
- **Meta** (file size + date, 0.62rem, muted)
- **Checkbox** (16×16px) — select for chat context

**"Select all" link:** Toggles all checkboxes.

**Add Sources overlay** (appears when `+` clicked):
- Replaces source list with drag-drop zone
- "Browse Files" button opens OS file picker with `multiple` attribute
- "Paste a URL" option below the drop zone
- `✕` button closes overlay, returns to source list
- Supported formats: PDF, DOCX, TXT, CSV, URL

**Empty state:** Centered icon + "No sources yet" + "Add documents, URLs, or files to start your analysis" + "Add Sources" button.

### 4.3 ChatPanel (Middle, flex-1)

**Purpose:** Main conversation area for all modes (Normal, Deep Research, Analyst).

**ChatMessages:**
- Scrollable message list, auto-scroll on new messages
- User messages: right-aligned, blue-tinted bubble, bottom-right radius reduced
- AI messages: left-aligned, dark bubble, bottom-left radius reduced
- Max width 75% per bubble

**ChatInputArea:**

**Layout:** Rounded container (border-radius 18px) with internal column flex.

**Row 1 (input row):** Horizontal flex:
- `+` attach button (32×32px circle, transparent bg, border on hover turns blue)
  - Opens OS file picker with `multiple` attribute
  - Attached files are "quick-attach" (sent with message only, NOT added to Sources panel)
- Text input (flex-1, auto-resize textarea)
  - Placeholder changes per mode:
    - Normal: "Ask about your sources..."
    - Deep Research: "What would you like to research?"
    - Analyst: "What should I analyze?"
- Send button (32×32px circle)
  - Grayed out when input is empty
  - Blue when text is present
  - Keyboard: Enter to send, Shift+Enter for newline

**Row 2 (attached files):** Shown only when files are attached.
- Horizontal flex-wrap of file chips
- Each chip: file icon + filename + `✕` remove button
- Left-padded 42px to align with text input (past the `+` button)

**Row 3 (mode pills):** Always visible below input.
- Horizontal flex of pill buttons
- Left-padded 42px to align with text input
- Pills: "Normal" | "🔬 Deep Research" | "📊 Analyst"
- Active pill: blue-tinted background, blue border
- Inactive: transparent, gray border, hover highlights

**Deep Research info box:** Shown only when Deep Research pill is active.
- Blue-tinted panel below pills
- Shows mode description: "AI will search across all sources, cross-reference citations, and produce a comprehensive research report."

### 4.4 StudioPanel (Right, 300px)

**Purpose:** Report generation, format selection, and preview.

**Default view (StudioCards):**

Report action cards (vertical stack):
- **Audit Report** — 📋 icon, "Generate compliance audit from sources"
- **Case Summary** — 📑 icon, "AI brief of key findings and risks"
- **Analysis Report** — 📊 icon, "Deep analysis with citations"

Each card: horizontal layout (icon left + title/desc right), hover border highlight.

**Auditor Format Grid:** 2×2 grid of format options:
- **Standard** (📄) — Default format
- **Big 4** (🏛️) — Deloitte/PwC style
- **Legal Brief** (⚖️) — Court format
- **Compliance** (🔒) — SOX/GDPR

Selected format: blue border + tinted background. Selection persists across reports.

**Export PDF button:** Full-width blue button at bottom.

**Report Preview view** (after clicking a report card):
- **Back arrow** (←) + report type title in header
- **Format badge** showing selected format (e.g., "Standard Format")
- **Preview content area** (flex-1, scrollable)
  - Structured preview with headings, fields, content
  - Updates live as AI generates the report
- **Export button** pinned at bottom

**Transition:** Clicking a report card triggers generation and transitions to preview view. Back arrow returns to cards view.

### 4.5 ThreePaneLayout

**CSS Grid:** `grid-template-columns: 260px 1fr 300px`  
**Height:** Full viewport minus any top nav.  
**Borders:** 1px solid separator between panes.  
**Background:** Dark theme (#0f0f14 base, #13131c panels, #0f0f18 chat).

**The layout does NOT change between modes.** All three panes remain visible regardless of whether Normal, Deep Research, or Analyst mode is active. Mode only affects:
- Chat placeholder text
- Backend API behavior (different endpoints/models)
- Optional info box in chat input area

## 5. Data Flow

### 5.1 Sources

```
User clicks + → File picker (multi-select) → Upload to backend API
                                            → Add to SourcesPanel list
                                            → Backend indexes for RAG

User checks/unchecks source → Update selected source IDs in state
                            → Send selected IDs with each chat message
```

### 5.2 Chat Messages

```
User types + selects mode + (optional attached files) → Send to backend
    Normal mode   → POST /api/chat       (standard RAG)
    Deep Research → POST /api/research    (multi-step research)
    Analyst mode  → POST /api/analyze     (structured analysis)

Backend streams response → ChatMessages renders incrementally
```

### 5.3 Report Generation

```
User selects auditor format → Stored in StudioPanel state
User clicks report card     → POST /api/reports/generate
                               { type: "audit"|"summary"|"analysis",
                                 format: "standard"|"big4"|"legal"|"compliance",
                                 source_ids: [...] }
                            → StudioPanel transitions to preview
                            → Response streams into preview content

User clicks Export PDF      → POST /api/reports/export
                            → Download PDF file
```

## 6. Styling

**Theme:** Dark mode matching the current app.

**Color palette:**
- Background: `#0f0f14` (base), `#13131c` (panels), `#1a1a28` (cards/inputs)
- Borders: `#2a2a38` (panels), `#333348` (inputs), `#2a2a3a` (cards)
- Accent: `#2563eb` (primary blue), `#4a6cf7` (hover/active blue)
- Text: `#e0e0e6` (primary), `#888` (secondary), `#555` (muted)

**Type icons by source type:**
| Type | Background | Text Color |
|---|---|---|
| PDF | `#3a1a1a` | `#f87171` (red) |
| DOC | `#1a2a3a` | `#60a5fa` (blue) |
| TXT | `#2a1a2a` | `#c084fc` (purple) |
| URL | `#1a3a2a` | `#4ade80` (green) |
| CSV | `#2a2a1a` | `#facc15` (yellow) |

**Border radius:** 14px (panels), 10px (cards), 16-18px (inputs/pills), 8px (items).

## 7. Error Handling

- **Upload failure:** Toast notification with retry option. File chip shows error state (red border).
- **Chat send failure:** Message shows retry button inline. Previous messages remain.
- **Report generation failure:** Preview area shows error message with "Try Again" button.
- **Empty sources warning:** If user tries to chat with 0 sources selected, show inline hint: "Select at least one source to get started."

## 8. Testing Strategy

### Unit Tests
- Each component renders correctly in all states
- Mode pills switch correctly and update placeholder text
- Source checkboxes toggle and "Select all" works
- Attached file chips appear/remove correctly
- Report card click triggers generation
- Format selection persists

### Integration Tests
- Full flow: add source → select → chat → get response
- Full flow: select format → click report → see preview → export
- Mode switching doesn't break layout
- Source upload with multi-select

### Visual Tests
- 3-pane layout renders at various viewport widths
- Home page card grid wraps correctly
- Empty states display correctly

## 9. Files to Create/Modify

### New Files
| File | Purpose |
|---|---|
| `frontend/src/pages/HomePage.tsx` | Landing page with notebook grid |
| `frontend/src/pages/NotebookPage.tsx` | 3-pane notebook layout |
| `frontend/src/components/studios/LegalStudio/ThreePaneLayout.tsx` | Grid layout wrapper |
| `frontend/src/components/studios/LegalStudio/StudioPanel.tsx` | Right panel with cards + preview |
| `frontend/src/components/studios/LegalStudio/StudioCards.tsx` | Report action cards |
| `frontend/src/components/studios/LegalStudio/ReportPreview.tsx` | Report preview with live content |
| `frontend/src/components/studios/LegalStudio/AuditorFormatGrid.tsx` | 2×2 format selector |
| `frontend/src/components/studios/LegalStudio/ModePills.tsx` | Mode pill chips |
| `frontend/src/components/studios/LegalStudio/AttachButton.tsx` | `+` attach button with file picker |
| `frontend/src/components/studios/LegalStudio/AttachedFileChips.tsx` | Removable file chip list |
| `frontend/src/components/studios/LegalStudio/SourceSearch.tsx` | Search input for sources |
| `frontend/src/components/studios/LegalStudio/EmptySourcesState.tsx` | Empty state for sources panel |
| `frontend/src/components/studios/LegalStudio/AddSourcesOverlay.tsx` | Drag-drop + browse + URL overlay |
| `frontend/src/components/common/NotebookCard.tsx` | Notebook card component |

### Modified Files
| File | Changes |
|---|---|
| `frontend/src/components/studios/LegalStudio/LegalStudio.tsx` | Rewrite to use ThreePaneLayout; remove old 4/5-pane logic |
| `frontend/src/components/studios/LegalStudio/ChatInput.tsx` | Integrate AttachButton, ModePills, AttachedFileChips |
| `frontend/src/components/studios/LegalStudio/SourcesSidebar.tsx` | Add type icons, search, checkboxes, multi-select upload, empty state |
| `frontend/src/components/studios/LegalStudio/ModeDropdown.tsx` | Replace with ModePills (can delete or deprecate) |
| `frontend/src/components/studios/LegalStudio/PreviewPane.tsx` | Merge into StudioPanel's ReportPreview |
| `frontend/src/App.tsx` | Change `/` route to `HomePage`; add `/notebook/:id` route for `NotebookPage` with `LegalStudio` inside `ThreePaneLayout`. Uses React Router v6 (`BrowserRouter`, `Routes`, `Route`). Existing routes (`/finance`, `/monitoring`, `/templates`, `/settings`) remain unchanged. |

### Backend (verify existing endpoints)
| File | Status |
|---|---|
| `backend/api/reports.py` | Already exists — verify `generate` and `export` endpoints; add if missing |
| `backend/api/documents.py` | Already exists — verify multi-file upload support; add `multiple` if needed |

## 10. Out of Scope

- Finance Studio redesign (stays separate)
- Backend AI model changes
- Authentication/authorization
- Mobile responsive design (desktop-first)
- Dark/light theme toggle (dark only for now)
