# Legal Studio UI Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the Legal Studio frontend to a NotebookLM-inspired 3-pane layout, fixing 8 critical UI issues (broken mode selector, oversized upload, cluttered sources, broken attachment, too many panes, bad empty state, missing template preview, inconsistent layout).

**Architecture:** Replace current flex-based multi-pane layout with a fixed CSS Grid 3-column layout (`260px | 1fr | 300px`). Decompose the monolithic `LegalStudio.tsx` into focused sub-components. Add a NotebookLM-style home page with notebook cards. Redesign chat input with Gemini-style mode pills and inline attach button.

**Tech Stack:** React 19, TypeScript 6, Vite 8, react-router-dom v7, CSS custom properties (`--s-*` tokens), lucide-react icons, axios.

**Design Spec:** `docs/superpowers/specs/2026-04-19-legal-studio-ui-redesign-design.md`

---

## File Map

### New Files

| File | Responsibility |
|---|---|
| `frontend/src/components/studios/LegalStudio/ModePills.tsx` | Gemini-style pill buttons for chat mode selection |
| `frontend/src/components/studios/LegalStudio/AttachButton.tsx` | `+` attach button with hidden file input (multi-select) |
| `frontend/src/components/studios/LegalStudio/AttachedFileChips.tsx` | Removable file chips for quick-attached files |
| `frontend/src/components/studios/LegalStudio/SourceSearch.tsx` | Search input for filtering sources list |
| `frontend/src/components/studios/LegalStudio/EmptySourcesState.tsx` | Empty state CTA for Sources panel |
| `frontend/src/components/studios/LegalStudio/AddSourcesOverlay.tsx` | Drag-drop + browse + URL upload overlay |
| `frontend/src/components/studios/LegalStudio/SourceTypeIcon.tsx` | Colored type badge icon (PDF/DOC/TXT/URL/CSV) |
| `frontend/src/components/studios/LegalStudio/StudioPanel.tsx` | Right panel: report cards + format grid + preview |
| `frontend/src/components/studios/LegalStudio/StudioCards.tsx` | Report action cards (Audit, Summary, Analysis) |
| `frontend/src/components/studios/LegalStudio/AuditorFormatGrid.tsx` | 2×2 auditor format selector |
| `frontend/src/components/studios/LegalStudio/ReportPreview.tsx` | Live report preview with export |
| `frontend/src/components/studios/LegalStudio/ThreePaneLayout.tsx` | CSS Grid wrapper for 3-column layout |
| `frontend/src/components/common/NotebookCard.tsx` | Notebook card for home page grid |
| `frontend/src/pages/HomePage.tsx` | Landing page with notebook card grid |

### Modified Files

| File | Changes |
|---|---|
| `frontend/src/index.css` | Add CSS classes for new components |
| `frontend/src/components/studios/LegalStudio/ChatInput.tsx` | Integrate AttachButton, ModePills, AttachedFileChips |
| `frontend/src/components/studios/LegalStudio/SourcesSidebar.tsx` | Add SourceTypeIcon, SourceSearch, AddSourcesOverlay, EmptySourcesState |
| `frontend/src/components/studios/LegalStudio/LegalStudio.tsx` | Rewrite layout to use ThreePaneLayout + StudioPanel |
| `frontend/src/App.tsx` | Add HomePage route, wrap LegalStudio in NotebookPage route |

### Deprecated (no longer imported after redesign)

| File | Reason |
|---|---|
| `frontend/src/components/studios/LegalStudio/ModeDropdown.tsx` | Replaced by ModePills |
| `frontend/src/components/studios/LegalStudio/PreviewPane.tsx` | Merged into StudioPanel |

---

## Task 1: Add CSS Classes for New Components

**Files:**
- Modify: `frontend/src/index.css` (append after line ~1172)

- [ ] **Step 1: Add mode pills CSS**

Append to `frontend/src/index.css` after the `.chat-input-send:disabled` rule (around line 1172):

```css
/* ── Mode Pills ── */
.mode-pills {
  display: flex;
  gap: 6px;
  padding-left: 50px;
}
.mode-pill {
  padding: 4px 14px;
  border-radius: 14px;
  font-size: 12px;
  cursor: pointer;
  border: 1px solid var(--s-border);
  background: transparent;
  color: var(--s-text-2);
  font-family: var(--s-font-ui);
  transition: var(--s-ease);
  user-select: none;
}
.mode-pill:hover {
  border-color: var(--s-text-3);
  color: var(--s-text-1);
}
.mode-pill--active {
  background: var(--s-accent-dim);
  border-color: var(--s-accent);
  color: var(--s-accent);
}
```

- [ ] **Step 2: Add attach button and file chips CSS**

Append:

```css
/* ── Attach Button ── */
.attach-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: transparent;
  border: 1px solid var(--s-border);
  color: var(--s-text-2);
  font-size: 18px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: var(--s-ease);
}
.attach-btn:hover {
  border-color: var(--s-accent);
  color: var(--s-accent);
  background: var(--s-accent-dim);
}

/* ── Attached File Chips ── */
.attached-chips {
  display: flex;
  gap: 6px;
  padding-left: 50px;
  flex-wrap: wrap;
}
.file-chip {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: 6px;
  background: var(--s-accent-dim);
  border: 1px solid rgba(107, 140, 255, 0.2);
  font-size: 12px;
  color: var(--s-accent);
  font-family: var(--s-font-ui);
}
.file-chip__remove {
  cursor: pointer;
  color: var(--s-text-3);
  background: none;
  border: none;
  font-size: 12px;
  padding: 0;
  margin-left: 2px;
  line-height: 1;
}
.file-chip__remove:hover {
  color: var(--s-danger);
}
```

- [ ] **Step 3: Add chat input container CSS (replaces old bar style)**

Append:

```css
/* ── Chat Input Area (redesigned) ── */
.chat-input-area {
  padding: 12px 40px 20px;
  border-top: 1px solid var(--s-border);
  background: var(--s-bg);
}
.chat-input-container {
  background: var(--s-surface);
  border: 1px solid var(--s-border);
  border-radius: 18px;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  transition: border-color var(--s-ease);
}
.chat-input-container:focus-within {
  border-color: var(--s-accent);
}
.chat-input-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.chat-input-textarea {
  flex: 1;
  background: transparent;
  border: none;
  color: var(--s-text-1);
  font-family: var(--s-font-ui);
  font-size: 14px;
  resize: none;
  min-height: 22px;
  max-height: 120px;
  line-height: 1.5;
  outline: none;
}
.chat-input-textarea::placeholder {
  color: var(--s-text-3);
}
.chat-send-btn {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: none;
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: var(--s-ease);
}
.chat-send-btn--active {
  background: var(--s-accent);
}
.chat-send-btn--inactive {
  background: var(--s-text-3);
  cursor: not-allowed;
}
.deep-research-info {
  background: var(--s-accent-dim);
  border: 1px solid rgba(107, 140, 255, 0.2);
  border-radius: 10px;
  padding: 8px 12px;
  margin-left: 50px;
}
.deep-research-info__label {
  font-size: 12px;
  color: var(--s-accent);
  font-weight: 600;
  margin-bottom: 4px;
  font-family: var(--s-font-ui);
}
.deep-research-info__desc {
  font-size: 12px;
  color: var(--s-text-2);
  line-height: 1.4;
  font-family: var(--s-font-ui);
}
```

- [ ] **Step 4: Add source panel CSS**

Append:

```css
/* ── Sources Panel (redesigned) ── */
.sources-panel {
  width: 260px;
  border-right: 1px solid var(--s-border);
  display: flex;
  flex-direction: column;
  background: var(--s-surface);
  overflow: hidden;
}
.sources-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px;
  border-bottom: 1px solid var(--s-border);
}
.sources-header__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--s-text-1);
  font-family: var(--s-font-ui);
}
.sources-header__count {
  font-size: 12px;
  color: var(--s-text-2);
  margin-left: 6px;
}
.sources-add-btn {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--s-accent);
  color: #fff;
  border: none;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.sources-add-btn:hover {
  opacity: 0.85;
}
.source-search {
  padding: 8px 14px;
}
.source-search__input {
  width: 100%;
  padding: 6px 10px 6px 30px;
  background: var(--s-bg);
  border: 1px solid var(--s-border);
  border-radius: var(--s-r-md);
  color: var(--s-text-1);
  font-size: 12px;
  font-family: var(--s-font-ui);
  outline: none;
}
.source-search__input:focus {
  border-color: var(--s-accent);
}
.source-search__input::placeholder {
  color: var(--s-text-3);
}
.source-search__wrapper {
  position: relative;
}
.source-search__icon {
  position: absolute;
  left: 8px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--s-text-3);
  pointer-events: none;
}
.sources-select-all {
  font-size: 12px;
  color: var(--s-accent);
  cursor: pointer;
  padding: 4px 14px;
  background: none;
  border: none;
  text-align: left;
  font-family: var(--s-font-ui);
}
.sources-select-all:hover {
  text-decoration: underline;
}
.source-list {
  flex: 1;
  overflow-y: auto;
  list-style: none;
  margin: 0;
  padding: 0;
}
.source-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  cursor: pointer;
  transition: background var(--s-ease);
}
.source-item:hover {
  background: var(--s-accent-dim);
}
.source-item--selected {
  background: var(--s-accent-dim);
  border-left: 2px solid var(--s-accent);
}
.source-type-icon {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
  flex-shrink: 0;
  font-family: var(--s-font-mono);
}
.source-type-icon--pdf { background: rgba(248, 113, 113, 0.15); color: #f87171; }
.source-type-icon--doc { background: rgba(96, 165, 250, 0.15); color: #60a5fa; }
.source-type-icon--txt { background: rgba(192, 132, 252, 0.15); color: #c084fc; }
.source-type-icon--url { background: rgba(74, 222, 128, 0.15); color: #4ade80; }
.source-type-icon--csv { background: rgba(250, 204, 21, 0.15); color: #facc15; }
.source-type-icon--xls { background: rgba(74, 222, 128, 0.15); color: #4ade80; }
.source-info {
  flex: 1;
  min-width: 0;
}
.source-info__name {
  font-size: 13px;
  color: var(--s-text-1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: var(--s-font-ui);
}
.source-info__meta {
  font-size: 11px;
  color: var(--s-text-3);
  margin-top: 2px;
  font-family: var(--s-font-ui);
}
.source-checkbox {
  width: 16px;
  height: 16px;
  accent-color: var(--s-accent);
  flex-shrink: 0;
}
```

- [ ] **Step 5: Add sources overlay, empty state, studio panel CSS**

Append:

```css
/* ── Add Sources Overlay ── */
.add-sources-overlay {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 14px;
  gap: 12px;
}
.add-sources-dropzone {
  flex: 1;
  border: 2px dashed var(--s-accent);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: var(--s-accent-dim);
  transition: var(--s-ease);
}
.add-sources-dropzone--dragover {
  background: rgba(107, 140, 255, 0.2);
  border-color: var(--s-accent);
}
.add-sources-dropzone__icon {
  font-size: 28px;
  color: var(--s-accent);
}
.add-sources-dropzone__title {
  font-size: 13px;
  color: var(--s-text-1);
  font-family: var(--s-font-ui);
}
.add-sources-dropzone__desc {
  font-size: 12px;
  color: var(--s-text-2);
  font-family: var(--s-font-ui);
}
.add-sources-browse-btn {
  padding: 8px 20px;
  border-radius: 8px;
  background: var(--s-accent);
  color: #fff;
  border: none;
  font-size: 13px;
  cursor: pointer;
  font-family: var(--s-font-ui);
}
.add-sources-browse-btn:hover {
  opacity: 0.85;
}
.add-sources-formats {
  font-size: 11px;
  color: var(--s-text-3);
  font-family: var(--s-font-ui);
}
.add-sources-url-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  border: 1px dashed var(--s-border);
  border-radius: 8px;
  cursor: pointer;
  background: none;
  color: var(--s-accent);
  font-size: 13px;
  font-family: var(--s-font-ui);
  width: 100%;
}
.add-sources-url-btn:hover {
  border-color: var(--s-accent);
  background: var(--s-accent-dim);
}

/* ── Empty Sources State ── */
.empty-sources {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 20px;
}
.empty-sources__icon {
  font-size: 36px;
  opacity: 0.3;
}
.empty-sources__title {
  font-size: 14px;
  color: var(--s-text-2);
  font-family: var(--s-font-ui);
}
.empty-sources__desc {
  font-size: 12px;
  color: var(--s-text-3);
  text-align: center;
  line-height: 1.5;
  font-family: var(--s-font-ui);
}
.empty-sources__btn {
  padding: 8px 16px;
  border-radius: 8px;
  background: var(--s-accent);
  color: #fff;
  border: none;
  font-size: 13px;
  cursor: pointer;
  font-family: var(--s-font-ui);
}
.empty-sources__btn:hover {
  opacity: 0.85;
}

/* ── Studio Panel (right) ── */
.studio-panel {
  width: 300px;
  border-left: 1px solid var(--s-border);
  display: flex;
  flex-direction: column;
  background: var(--s-surface);
  overflow-y: auto;
  padding: 14px;
  gap: 10px;
}
.studio-panel__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--s-text-1);
  font-family: var(--s-font-ui);
}
.studio-card {
  background: var(--s-bg);
  border: 1px solid var(--s-border);
  border-radius: 10px;
  padding: 12px 14px;
  cursor: pointer;
  transition: var(--s-ease);
  display: flex;
  gap: 12px;
  align-items: flex-start;
}
.studio-card:hover {
  border-color: var(--s-accent);
  background: var(--s-elevated);
}
.studio-card__icon {
  font-size: 20px;
  flex-shrink: 0;
  margin-top: 2px;
}
.studio-card__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--s-text-1);
  margin-bottom: 2px;
  font-family: var(--s-font-ui);
}
.studio-card__desc {
  font-size: 12px;
  color: var(--s-text-2);
  line-height: 1.4;
  font-family: var(--s-font-ui);
}

/* ── Auditor Format Grid ── */
.format-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.format-option {
  padding: 10px;
  border: 1px solid var(--s-border);
  border-radius: 8px;
  text-align: center;
  cursor: pointer;
  transition: var(--s-ease);
  background: transparent;
}
.format-option:hover {
  border-color: var(--s-text-3);
}
.format-option--selected {
  border-color: var(--s-accent);
  background: var(--s-accent-dim);
}
.format-option__icon {
  font-size: 18px;
  margin-bottom: 4px;
}
.format-option__name {
  font-size: 12px;
  color: var(--s-text-1);
  font-family: var(--s-font-ui);
}
.format-option__desc {
  font-size: 10px;
  color: var(--s-text-3);
  margin-top: 2px;
  font-family: var(--s-font-ui);
}

/* ── Report Preview ── */
.report-preview {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.report-preview__header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.report-preview__back {
  cursor: pointer;
  color: var(--s-accent);
  background: none;
  border: none;
  font-size: 16px;
  padding: 0;
}
.report-preview__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--s-text-1);
  font-family: var(--s-font-ui);
}
.report-preview__badge {
  font-size: 11px;
  background: var(--s-accent-dim);
  color: var(--s-accent);
  padding: 2px 8px;
  border-radius: 10px;
  font-family: var(--s-font-ui);
}
.report-preview__content {
  flex: 1;
  overflow-y: auto;
  border-left: 3px solid var(--s-border);
  padding-left: 12px;
  font-size: 13px;
  color: var(--s-text-2);
  line-height: 1.6;
  font-family: var(--s-font-ui);
}
.export-btn {
  width: 100%;
  padding: 10px;
  border-radius: 10px;
  background: var(--s-accent);
  color: #fff;
  border: none;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  font-family: var(--s-font-ui);
}
.export-btn:hover {
  opacity: 0.85;
}
.export-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

/* ── Three-Pane Layout ── */
.three-pane-layout {
  display: grid;
  grid-template-columns: 260px 1fr 300px;
  height: 100%;
  overflow: hidden;
}
.three-pane-layout__center {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
  background: var(--s-bg);
}

/* ── App Shell: hide ContextualSidebar on legal routes ── */
.app-shell--legal {
  grid-template-columns: 60px 1fr;
}
.app-shell--legal .contextual-sidebar {
  display: none;
}

/* ── Home Page ── */
.home-page {
  flex: 1;
  overflow-y: auto;
  padding: 32px 40px;
}
.home-page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}
.home-page__title {
  font-size: 22px;
  font-weight: 600;
  color: var(--s-text-1);
  font-family: var(--s-font-ui);
}
.home-page__new-btn {
  padding: 8px 20px;
  border-radius: 20px;
  background: var(--s-accent);
  color: #fff;
  border: none;
  font-size: 13px;
  cursor: pointer;
  font-family: var(--s-font-ui);
}
.home-page__new-btn:hover {
  opacity: 0.85;
}
.home-page__section-label {
  font-size: 12px;
  color: var(--s-text-3);
  text-transform: uppercase;
  letter-spacing: 1.5px;
  margin-bottom: 12px;
  font-family: var(--s-font-ui);
}
.notebook-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}

/* ── Notebook Card ── */
.notebook-card {
  background: var(--s-surface);
  border: 1px solid var(--s-border);
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  transition: var(--s-ease);
}
.notebook-card:hover {
  border-color: var(--s-accent);
}
.notebook-card--create {
  border-style: dashed;
  border-color: var(--s-text-3);
}
.notebook-card--create:hover {
  border-color: var(--s-accent);
}
.notebook-card__thumb {
  height: 100px;
  background: var(--s-elevated);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--s-text-3);
  font-size: 28px;
}
.notebook-card__info {
  padding: 12px 14px;
}
.notebook-card__title {
  font-size: 14px;
  color: var(--s-text-1);
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: var(--s-font-ui);
}
.notebook-card__meta {
  font-size: 12px;
  color: var(--s-text-3);
  font-family: var(--s-font-ui);
}

/* ── Studio Divider ── */
.studio-divider {
  border: none;
  border-top: 1px solid var(--s-border);
  margin: 4px 0;
}
```

- [ ] **Step 6: Verify CSS compiles**

Run: `cd "C:\Users\Armaan\OneDrive - The Era Corporations\Study\Armaan\AI Class\Data Science Class\35. 11-Apr-2026\Project_AccountingLegalChatbot\frontend" && npx tsc -b --noEmit 2>&1 | Select-Object -First 5`

Expected: No CSS-related errors (TS won't check CSS, but build will).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/index.css
git commit -m "style: add CSS classes for Legal Studio UI redesign

Add classes for mode pills, attach button, file chips, redesigned
chat input, sources panel, add sources overlay, empty state,
studio panel, format grid, report preview, three-pane layout,
home page, and notebook cards."
```

---

## Task 2: Create SourceTypeIcon Component

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/SourceTypeIcon.tsx`

- [ ] **Step 1: Create SourceTypeIcon.tsx**

```tsx
function getTypeFromFilename(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase() ?? '';
  if (ext === 'pdf') return 'pdf';
  if (ext === 'doc' || ext === 'docx') return 'doc';
  if (ext === 'txt') return 'txt';
  if (ext === 'csv') return 'csv';
  if (ext === 'xls' || ext === 'xlsx') return 'xls';
  if (filename.startsWith('http') || ext === 'url') return 'url';
  return 'txt';
}

const LABELS: Record<string, string> = {
  pdf: 'PDF',
  doc: 'DOC',
  txt: 'TXT',
  url: 'URL',
  csv: 'CSV',
  xls: 'XLS',
};

interface Props {
  filename: string;
}

export function SourceTypeIcon({ filename }: Props) {
  const type = getTypeFromFilename(filename);
  return (
    <div className={`source-type-icon source-type-icon--${type}`}>
      {LABELS[type] ?? 'TXT'}
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc -b --noEmit`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/SourceTypeIcon.tsx
git commit -m "feat: add SourceTypeIcon component with colored type badges"
```

---

## Task 3: Create ModePills Component

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/ModePills.tsx`

- [ ] **Step 1: Create ModePills.tsx**

```tsx
export type ChatMode = 'normal' | 'deep_research' | 'analyst';

const MODE_OPTIONS: { value: ChatMode; label: string; icon: string }[] = [
  { value: 'normal', label: 'Normal', icon: '⚡' },
  { value: 'deep_research', label: 'Deep Research', icon: '🔬' },
  { value: 'analyst', label: 'Analyst', icon: '📊' },
];

const PLACEHOLDERS: Record<ChatMode, string> = {
  normal: 'Ask about your sources…',
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

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc -b --noEmit`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/ModePills.tsx
git commit -m "feat: add ModePills component for Gemini-style mode selection"
```

---

## Task 4: Create AttachButton Component

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/AttachButton.tsx`

- [ ] **Step 1: Create AttachButton.tsx**

```tsx
import { useRef } from 'react';
import { Plus } from 'lucide-react';

interface Props {
  onAttach: (files: FileList) => void;
  disabled?: boolean;
}

export function AttachButton({ onAttach, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        multiple
        style={{ display: 'none' }}
        onChange={e => {
          if (e.target.files && e.target.files.length > 0) {
            onAttach(e.target.files);
            e.target.value = '';
          }
        }}
      />
      <button
        type="button"
        className="attach-btn"
        onClick={() => inputRef.current?.click()}
        disabled={disabled}
        aria-label="Attach files"
        title="Attach files"
      >
        <Plus size={18} />
      </button>
    </>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc -b --noEmit`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/AttachButton.tsx
git commit -m "feat: add AttachButton component with multi-select file picker"
```

---

## Task 5: Create AttachedFileChips Component

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/AttachedFileChips.tsx`

- [ ] **Step 1: Create AttachedFileChips.tsx**

```tsx
interface AttachedFile {
  id: string;
  name: string;
}

interface Props {
  files: AttachedFile[];
  onRemove: (id: string) => void;
}

export function AttachedFileChips({ files, onRemove }: Props) {
  if (files.length === 0) return null;

  return (
    <div className="attached-chips">
      {files.map(f => (
        <div key={f.id} className="file-chip">
          <span>📄</span>
          <span>{f.name}</span>
          <button
            type="button"
            className="file-chip__remove"
            onClick={() => onRemove(f.id)}
            aria-label={`Remove ${f.name}`}
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}

export type { AttachedFile };
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc -b --noEmit`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/AttachedFileChips.tsx
git commit -m "feat: add AttachedFileChips component for quick-attach display"
```

---

## Task 6: Redesign ChatInput Component

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/ChatInput.tsx`

- [ ] **Step 1: Rewrite ChatInput.tsx**

Replace the entire contents of `ChatInput.tsx` with:

```tsx
import { useState, useRef, useEffect, useCallback, type KeyboardEvent } from 'react';
import { Send } from 'lucide-react';
import { ModePills, MODE_PLACEHOLDERS, type ChatMode } from './ModePills';
import { AttachButton } from './AttachButton';
import { AttachedFileChips, type AttachedFile } from './AttachedFileChips';

interface Props {
  onSend: (text: string, attachedFiles?: File[]) => void;
  disabled?: boolean;
  initialValue?: string;
  mode?: ChatMode;
  onModeChange?: (m: ChatMode) => void;
}

export function ChatInput({ onSend, disabled, initialValue = '', mode = 'normal', onModeChange }: Props) {
  const [value, setValue] = useState(initialValue);
  const [attachedFiles, setAttachedFiles] = useState<Array<AttachedFile & { file: File }>>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const idCounter = useRef(0);

  useEffect(() => {
    const handler = (e: Event) => {
      const text = (e as CustomEvent<string>).detail;
      setValue(text);
      textareaRef.current?.focus();
    };
    window.addEventListener('studio:suggest', handler);
    return () => window.removeEventListener('studio:suggest', handler);
  }, []);

  const autoResize = useCallback(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = 'auto';
      ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
    }
  }, []);

  const submit = useCallback(() => {
    const text = value.trim();
    if (!text || disabled) return;
    const files = attachedFiles.map(f => f.file);
    onSend(text, files.length > 0 ? files : undefined);
    setValue('');
    setAttachedFiles([]);
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  }, [value, disabled, attachedFiles, onSend]);

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const handleAttach = useCallback((fileList: FileList) => {
    const newFiles = Array.from(fileList).map(file => ({
      id: `attach-${++idCounter.current}`,
      name: file.name,
      file,
    }));
    setAttachedFiles(prev => [...prev, ...newFiles]);
  }, []);

  const handleRemoveAttach = useCallback((id: string) => {
    setAttachedFiles(prev => prev.filter(f => f.id !== id));
  }, []);

  const hasContent = value.trim().length > 0;

  return (
    <div className="chat-input-area">
      <div className="chat-input-container">
        <div className="chat-input-row">
          <AttachButton onAttach={handleAttach} disabled={disabled} />
          <textarea
            ref={textareaRef}
            className="chat-input-textarea"
            value={value}
            onChange={e => { setValue(e.target.value); autoResize(); }}
            onKeyDown={handleKeyDown}
            placeholder={MODE_PLACEHOLDERS[mode]}
            disabled={disabled}
            rows={1}
          />
          <button
            type="button"
            className={`chat-send-btn ${hasContent ? 'chat-send-btn--active' : 'chat-send-btn--inactive'}`}
            onClick={submit}
            disabled={disabled || !hasContent}
            aria-label="Send message"
            title="Send"
          >
            <Send size={16} />
          </button>
        </div>
        <AttachedFileChips files={attachedFiles} onRemove={handleRemoveAttach} />
        {onModeChange && (
          <ModePills value={mode} onChange={onModeChange} />
        )}
        {mode === 'deep_research' && (
          <div className="deep-research-info">
            <div className="deep-research-info__label">🔬 Deep Research Mode</div>
            <div className="deep-research-info__desc">
              AI will search across all sources, cross-reference citations, and produce a comprehensive research report.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export type { ChatMode };
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc -b --noEmit`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/ChatInput.tsx
git commit -m "feat: redesign ChatInput with attach button, mode pills, file chips"
```

---

## Task 7: Create SourceSearch Component

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/SourceSearch.tsx`

- [ ] **Step 1: Create SourceSearch.tsx**

```tsx
import { Search } from 'lucide-react';

interface Props {
  value: string;
  onChange: (value: string) => void;
}

export function SourceSearch({ value, onChange }: Props) {
  return (
    <div className="source-search">
      <div className="source-search__wrapper">
        <Search size={14} className="source-search__icon" />
        <input
          className="source-search__input"
          type="text"
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder="Search sources…"
          aria-label="Search sources"
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc -b --noEmit`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/SourceSearch.tsx
git commit -m "feat: add SourceSearch component for filtering sources"
```

---

## Task 8: Create EmptySourcesState Component

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/EmptySourcesState.tsx`

- [ ] **Step 1: Create EmptySourcesState.tsx**

```tsx
interface Props {
  onAddSources: () => void;
}

export function EmptySourcesState({ onAddSources }: Props) {
  return (
    <div className="empty-sources">
      <div className="empty-sources__icon">📚</div>
      <div className="empty-sources__title">No sources yet</div>
      <div className="empty-sources__desc">
        Add documents, URLs, or files<br />to start your analysis
      </div>
      <button
        type="button"
        className="empty-sources__btn"
        onClick={onAddSources}
      >
        + Add Sources
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc -b --noEmit`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/EmptySourcesState.tsx
git commit -m "feat: add EmptySourcesState component for empty sources panel"
```

---

## Task 9: Create AddSourcesOverlay Component

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/AddSourcesOverlay.tsx`

- [ ] **Step 1: Create AddSourcesOverlay.tsx**

```tsx
import { useState, useRef, type DragEvent } from 'react';

interface Props {
  onUpload: (files: FileList) => void;
  onClose: () => void;
}

export function AddSourcesOverlay({ onUpload, onClose }: Props) {
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length > 0) {
      onUpload(e.dataTransfer.files);
      onClose();
    }
  };

  const handleBrowse = () => {
    fileRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onUpload(e.target.files);
      onClose();
    }
  };

  return (
    <div className="add-sources-overlay">
      <input
        ref={fileRef}
        type="file"
        multiple
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />
      <div
        className={`add-sources-dropzone${dragOver ? ' add-sources-dropzone--dragover' : ''}`}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        <div className="add-sources-dropzone__icon">📁</div>
        <div className="add-sources-dropzone__title">Drop files here or browse</div>
        <div className="add-sources-dropzone__desc">Select multiple files at once</div>
        <button
          type="button"
          className="add-sources-browse-btn"
          onClick={handleBrowse}
        >
          Browse Files
        </button>
        <div className="add-sources-formats">PDF · DOCX · TXT · CSV · XLSX</div>
      </div>
      <button
        type="button"
        className="add-sources-url-btn"
        onClick={() => { /* URL paste modal - future */ }}
      >
        🔗 Paste a URL
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc -b --noEmit`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/AddSourcesOverlay.tsx
git commit -m "feat: add AddSourcesOverlay with drag-drop and multi-select browse"
```

---

## Task 10: Redesign SourcesSidebar Component

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/SourcesSidebar.tsx`

- [ ] **Step 1: Rewrite SourcesSidebar.tsx**

Replace the entire contents with:

```tsx
import { useState, useMemo, useCallback } from 'react';
import { SourceTypeIcon } from './SourceTypeIcon';
import { SourceSearch } from './SourceSearch';
import { EmptySourcesState } from './EmptySourcesState';
import { AddSourcesOverlay } from './AddSourcesOverlay';

export interface SourceDoc {
  id: string;
  filename: string;
  summary?: string;
  key_terms?: string[];
  source: string;
  status?: 'uploading' | 'processing' | 'summarizing' | 'ready' | 'error';
  file_size?: number;
  created_at?: string;
}

interface Props {
  docs: SourceDoc[];
  selectedIds: string[];
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onUpload: (files: FileList) => void;
  onPreview: (id: string) => void;
}

function formatFileSize(bytes?: number): string {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function SourcesSidebar({ docs, selectedIds, onSelect, onDelete, onUpload, onPreview }: Props) {
  const [search, setSearch] = useState('');
  const [showOverlay, setShowOverlay] = useState(false);

  const filteredDocs = useMemo(() => {
    if (!search.trim()) return docs;
    const q = search.toLowerCase();
    return docs.filter(d => d.filename.toLowerCase().includes(q));
  }, [docs, search]);

  const allSelected = docs.length > 0 && docs.every(d => selectedIds.includes(d.id));

  const handleSelectAll = useCallback(() => {
    if (allSelected) {
      docs.forEach(d => {
        if (selectedIds.includes(d.id)) onSelect(d.id);
      });
    } else {
      docs.forEach(d => {
        if (!selectedIds.includes(d.id)) onSelect(d.id);
      });
    }
  }, [docs, selectedIds, allSelected, onSelect]);

  const handleUpload = useCallback((files: FileList) => {
    onUpload(files);
    setShowOverlay(false);
  }, [onUpload]);

  return (
    <aside className="sources-panel">
      <div className="sources-header">
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <span className="sources-header__title">
            {showOverlay ? 'Add Sources' : 'Sources'}
          </span>
          {!showOverlay && (
            <span className="sources-header__count">({docs.length})</span>
          )}
        </div>
        <button
          type="button"
          className="sources-add-btn"
          onClick={() => setShowOverlay(!showOverlay)}
          aria-label={showOverlay ? 'Close' : 'Add sources'}
          title={showOverlay ? 'Close' : 'Add sources'}
        >
          {showOverlay ? '✕' : '+'}
        </button>
      </div>

      {showOverlay ? (
        <AddSourcesOverlay onUpload={handleUpload} onClose={() => setShowOverlay(false)} />
      ) : docs.length === 0 ? (
        <EmptySourcesState onAddSources={() => setShowOverlay(true)} />
      ) : (
        <>
          <SourceSearch value={search} onChange={setSearch} />
          <button
            type="button"
            className="sources-select-all"
            onClick={handleSelectAll}
          >
            {allSelected ? 'Deselect all' : 'Select all'}
          </button>
          <ul className="source-list">
            {filteredDocs.map(d => (
              <li
                key={d.id}
                className={`source-item${selectedIds.includes(d.id) ? ' source-item--selected' : ''}`}
                onClick={() => onPreview(d.id)}
              >
                <input
                  type="checkbox"
                  className="source-checkbox"
                  checked={selectedIds.includes(d.id)}
                  onChange={e => { e.stopPropagation(); onSelect(d.id); }}
                  onClick={e => e.stopPropagation()}
                  aria-label={`Select ${d.filename}`}
                />
                <SourceTypeIcon filename={d.filename} />
                <div className="source-info">
                  <div className="source-info__name">{d.filename}</div>
                  <div className="source-info__meta">
                    {formatFileSize(d.file_size)}
                    {d.status && d.status !== 'ready' && (
                      <span style={{ color: 'var(--s-warning)', marginLeft: 6 }}>
                        {d.status}…
                      </span>
                    )}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={e => { e.stopPropagation(); onDelete(d.id); }}
                  aria-label={`Delete ${d.filename}`}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--s-text-3)',
                    cursor: 'pointer',
                    fontSize: 14,
                    padding: 0,
                    flexShrink: 0,
                  }}
                  title="Delete"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </aside>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc -b --noEmit`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/SourcesSidebar.tsx
git commit -m "feat: redesign SourcesSidebar with type icons, search, overlay, empty state"
```

---

## Task 11: Create AuditorFormatGrid Component

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/AuditorFormatGrid.tsx`

- [ ] **Step 1: Create AuditorFormatGrid.tsx**

```tsx
export type AuditorFormat = 'standard' | 'big4' | 'legal' | 'compliance';

const FORMAT_OPTIONS: { value: AuditorFormat; label: string; icon: string; desc: string }[] = [
  { value: 'standard', label: 'Standard', icon: '📄', desc: 'Default format' },
  { value: 'big4', label: 'Big 4', icon: '🏛️', desc: 'Deloitte/PwC style' },
  { value: 'legal', label: 'Legal Brief', icon: '⚖️', desc: 'Court format' },
  { value: 'compliance', label: 'Compliance', icon: '🔒', desc: 'SOX/GDPR' },
];

interface Props {
  value: AuditorFormat;
  onChange: (format: AuditorFormat) => void;
}

export function AuditorFormatGrid({ value, onChange }: Props) {
  return (
    <div>
      <div style={{
        fontSize: 13,
        fontWeight: 600,
        color: 'var(--s-text-1)',
        marginBottom: 8,
        fontFamily: 'var(--s-font-ui)',
        display: 'flex',
        alignItems: 'center',
        gap: 6,
      }}>
        📎 Auditor Format
      </div>
      <div className="format-grid">
        {FORMAT_OPTIONS.map(opt => (
          <button
            key={opt.value}
            type="button"
            className={`format-option${opt.value === value ? ' format-option--selected' : ''}`}
            onClick={() => onChange(opt.value)}
            aria-pressed={opt.value === value}
          >
            <div className="format-option__icon">{opt.icon}</div>
            <div className="format-option__name">{opt.label}</div>
            <div className="format-option__desc">{opt.desc}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc -b --noEmit`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/AuditorFormatGrid.tsx
git commit -m "feat: add AuditorFormatGrid component for audit template selection"
```

---

## Task 12: Create StudioCards Component

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/StudioCards.tsx`

- [ ] **Step 1: Create StudioCards.tsx**

```tsx
export type ReportType = 'audit' | 'summary' | 'analysis';

const CARDS: { type: ReportType; icon: string; title: string; desc: string }[] = [
  { type: 'audit', icon: '📋', title: 'Audit Report', desc: 'Generate compliance audit from sources' },
  { type: 'summary', icon: '📑', title: 'Case Summary', desc: 'AI brief of key findings and risks' },
  { type: 'analysis', icon: '📊', title: 'Analysis Report', desc: 'Deep analysis with citations' },
];

interface Props {
  onSelect: (type: ReportType) => void;
  disabled?: boolean;
}

export function StudioCards({ onSelect, disabled }: Props) {
  return (
    <>
      {CARDS.map(card => (
        <button
          key={card.type}
          type="button"
          className="studio-card"
          onClick={() => onSelect(card.type)}
          disabled={disabled}
        >
          <div className="studio-card__icon">{card.icon}</div>
          <div>
            <div className="studio-card__title">{card.title}</div>
            <div className="studio-card__desc">{card.desc}</div>
          </div>
        </button>
      ))}
    </>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc -b --noEmit`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/StudioCards.tsx
git commit -m "feat: add StudioCards component for report type selection"
```

---

## Task 13: Create ReportPreview Component

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/ReportPreview.tsx`

- [ ] **Step 1: Create ReportPreview.tsx**

```tsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { AuditorFormat } from './AuditorFormatGrid';
import type { ReportType } from './StudioCards';

const FORMAT_LABELS: Record<AuditorFormat, string> = {
  standard: 'Standard Format',
  big4: 'Big 4 Format',
  legal: 'Legal Brief Format',
  compliance: 'Compliance Format',
};

const REPORT_LABELS: Record<ReportType, string> = {
  audit: 'Audit Report',
  summary: 'Case Summary',
  analysis: 'Analysis Report',
};

interface Props {
  reportType: ReportType;
  format: AuditorFormat;
  content: string;
  loading: boolean;
  onBack: () => void;
  onExport: () => void;
}

export function ReportPreview({ reportType, format, content, loading, onBack, onExport }: Props) {
  return (
    <div className="report-preview">
      <div className="report-preview__header">
        <button
          type="button"
          className="report-preview__back"
          onClick={onBack}
          aria-label="Back to studio cards"
        >
          ←
        </button>
        <span className="report-preview__title">{REPORT_LABELS[reportType]}</span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span className="report-preview__badge">{FORMAT_LABELS[format]}</span>
      </div>

      <div className="report-preview__content">
        {loading && !content ? (
          <div style={{ color: 'var(--s-text-3)', fontStyle: 'italic' }}>
            Generating report…
          </div>
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {content || 'No content generated yet.'}
          </ReactMarkdown>
        )}
      </div>

      <button
        type="button"
        className="export-btn"
        onClick={onExport}
        disabled={loading || !content}
      >
        📥 Export as PDF
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc -b --noEmit`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/ReportPreview.tsx
git commit -m "feat: add ReportPreview component with markdown rendering and export"
```

---

## Task 14: Create StudioPanel Component

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/StudioPanel.tsx`

- [ ] **Step 1: Create StudioPanel.tsx**

```tsx
import { useState, useCallback } from 'react';
import { API } from '../../../lib/api';
import { StudioCards, type ReportType } from './StudioCards';
import { AuditorFormatGrid, type AuditorFormat } from './AuditorFormatGrid';
import { ReportPreview } from './ReportPreview';

interface Props {
  sourceIds: string[];
}

export function StudioPanel({ sourceIds }: Props) {
  const [format, setFormat] = useState<AuditorFormat>('standard');
  const [activeReport, setActiveReport] = useState<ReportType | null>(null);
  const [reportContent, setReportContent] = useState('');
  const [generating, setGenerating] = useState(false);

  const handleGenerateReport = useCallback(async (type: ReportType) => {
    setActiveReport(type);
    setReportContent('');
    setGenerating(true);

    try {
      const backendFormat = format === 'legal' ? 'isa' : format === 'compliance' ? 'fta' : format;
      const res = await API.post(`/api/reports/generate/${type}`, {
        mapped_data: [],
        requirements: {},
        source_ids: sourceIds,
        auditor_format: backendFormat,
        company_name: 'Analysis',
      });
      setReportContent(res.data.report_text ?? res.data.draft ?? 'Report generated.');
    } catch (err) {
      setReportContent('Error generating report. Please try again.');
    } finally {
      setGenerating(false);
    }
  }, [format, sourceIds]);

  const handleExport = useCallback(async () => {
    if (!reportContent) return;
    try {
      const res = await API.post('/api/reports/format', {
        draft: reportContent,
        format: format === 'legal' ? 'isa' : format === 'compliance' ? 'fta' : format,
      }, { responseType: 'blob' });
      const url = URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `report-${activeReport}-${format}.md`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      const blob = new Blob([reportContent], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report-${activeReport}-${format}.md`;
      a.click();
      URL.revokeObjectURL(url);
    }
  }, [reportContent, activeReport, format]);

  if (activeReport) {
    return (
      <aside className="studio-panel">
        <ReportPreview
          reportType={activeReport}
          format={format}
          content={reportContent}
          loading={generating}
          onBack={() => { setActiveReport(null); setReportContent(''); }}
          onExport={handleExport}
        />
      </aside>
    );
  }

  return (
    <aside className="studio-panel">
      <div className="studio-panel__title">Studio</div>
      <StudioCards onSelect={handleGenerateReport} disabled={generating} />
      <hr className="studio-divider" />
      <AuditorFormatGrid value={format} onChange={setFormat} />
      <button
        type="button"
        className="export-btn"
        disabled={sourceIds.length === 0}
        onClick={() => handleGenerateReport('audit')}
      >
        📥 Export PDF
      </button>
    </aside>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc -b --noEmit`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/StudioPanel.tsx
git commit -m "feat: add StudioPanel with report cards, format grid, and preview"
```

---

## Task 15: Create ThreePaneLayout Component

**Files:**
- Create: `frontend/src/components/studios/LegalStudio/ThreePaneLayout.tsx`

- [ ] **Step 1: Create ThreePaneLayout.tsx**

```tsx
import type { ReactNode } from 'react';

interface Props {
  left: ReactNode;
  center: ReactNode;
  right: ReactNode;
}

export function ThreePaneLayout({ left, center, right }: Props) {
  return (
    <div className="three-pane-layout">
      {left}
      <div className="three-pane-layout__center">
        {center}
      </div>
      {right}
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc -b --noEmit`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/ThreePaneLayout.tsx
git commit -m "feat: add ThreePaneLayout CSS Grid wrapper component"
```

---

## Task 16: Rewrite LegalStudio to Use ThreePaneLayout

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/LegalStudio.tsx`

This is the largest task. It rewrites the main layout from the old flex-based approach to the new 3-pane grid, integrating all new components.

- [ ] **Step 1: Rewrite LegalStudio.tsx**

Replace the entire contents of `LegalStudio.tsx` with:

```tsx
import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { API_BASE, API, fmtTime, type Message, type Source } from '../../../lib/api';
import { ChatMessages } from './ChatMessages';
import { ChatInput } from './ChatInput';
import { SourcePeeker } from './SourcePeeker';
import { SourcesSidebar, type SourceDoc } from './SourcesSidebar';
import { StudioPanel } from './StudioPanel';
import { ThreePaneLayout } from './ThreePaneLayout';
import { type ChatMode } from './ModePills';
import { DomainChip, type DomainLabel } from './DomainChip';
import { AuditorResultBubble } from './AuditorResultBubble';
import { ResearchBubble } from './ResearchBubble';

type Domain = 'general' | 'finance' | 'law' | 'audit' | 'vat' | 'aml' | 'legal' | 'corporate_tax';

const DOMAIN_KEYWORDS: Array<{ keywords: string[]; domain: Domain }> = [
  { keywords: ['vat', 'trn', 'fta', '5%', 'zero-rated', 'zero rated', 'exempt supply', 'input tax', 'output tax', 'export service', 'export of services', 'zero-rated supply', 'zero rated export', 'place of supply', 'recipient outside uae', 'import of services', 'designated zone', 'reverse charge', 'article 29', 'article 31'], domain: 'vat' },
  { keywords: ['corporate tax', 'ct ', '9%', 'taxable income', 'decree-law 47', 'small business relief'], domain: 'corporate_tax' },
  { keywords: ['aml', 'kyc', ' str ', 'cft', 'suspicious', 'beneficial owner'], domain: 'aml' },
  { keywords: ['audit', 'isa ', 'internal control', 'assurance', 'auditor'], domain: 'audit' },
  { keywords: ['ifrs', 'balance sheet', 'financial statement', 'revenue recognition'], domain: 'finance' },
  { keywords: ['legal', 'contract', 'civil law', 'employment law', 'company law'], domain: 'legal' },
];

function detectDomain(text: string): Domain | null {
  const lower = text.toLowerCase();
  for (const { keywords, domain } of DOMAIN_KEYWORDS) {
    if (keywords.some(kw => lower.includes(kw))) return domain;
  }
  return null;
}

interface Conversation { id: string; title: string; updated_at: string; }
interface LegalStudioProps {
  onConversationsChange?: (convos: Conversation[]) => void;
  initialConversationId?: string;
}

export function LegalStudio({ onConversationsChange, initialConversationId }: LegalStudioProps = {}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeSource, setActiveSource] = useState<Source | null>(null);
  const [sourcePanelOpen, setSourcePanelOpen] = useState(false);
  const [webSearching, setWebSearching] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(initialConversationId ?? null);
  const [domain, setDomain] = useState<Domain>('law');
  const [mode, setMode] = useState<ChatMode>('normal');
  const [detectedDomain, setDetectedDomain] = useState<DomainLabel | null>(null);
  const [searchParams] = useSearchParams();

  const [docs, setDocs] = useState<SourceDoc[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);

  const [researchPhases, setResearchPhases] = useState<Array<{
    phase: string; message: string; sub_questions?: string[];
    progress?: number; total?: number; report?: string;
  }>>([]);
  const [researchReport, setResearchReport] = useState<string | null>(null);
  const [researching, setResearching] = useState(false);

  const [auditResult, setAuditResult] = useState<{
    risk_flags: { severity: string; document: string; finding: string }[];
    anomalies: { severity: string; document: string; finding: string }[];
    compliance_gaps: { severity: string; document: string; finding: string }[];
    summary: string;
  } | null>(null);
  const [auditing, setAuditing] = useState(false);
  const [handingOff, setHandingOff] = useState(false);

  const initialValue = searchParams.get('q') ?? '';

  // --- Document handlers ---
  const handleDocSelect = useCallback((id: string) => {
    setSelectedDocIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  }, []);

  const handleDocDelete = useCallback(async (id: string) => {
    try {
      await API.delete(`/api/documents/${id}`);
      setDocs(prev => prev.filter(d => d.id !== id));
      setSelectedDocIds(prev => prev.filter(x => x !== id));
    } catch { /* ignore */ }
  }, []);

  const handleDocUpload = useCallback(async (files: FileList) => {
    for (const file of Array.from(files)) {
      const tempId = `uploading-${Date.now()}-${file.name}`;
      setDocs(prev => [...prev, {
        id: tempId, filename: file.name, source: file.name,
        status: 'uploading',
      }]);
      const fd = new FormData();
      fd.append('file', file);
      try {
        const res = await API.post('/api/documents/upload', fd);
        const doc = res.data;
        setDocs(prev => prev.map(d =>
          d.id === tempId ? {
            id: doc.id, filename: doc.original_name ?? doc.filename,
            source: doc.source ?? doc.filename, status: 'ready',
            summary: doc.summary, key_terms: doc.key_terms,
            file_size: doc.file_size,
          } : d
        ));
        setSelectedDocIds(prev => [...prev, doc.id]);
      } catch {
        setDocs(prev => prev.map(d =>
          d.id === tempId ? { ...d, status: 'error' } : d
        ));
      }
    }
  }, []);

  const handleDocPreview = useCallback((_id: string) => {
    // Preview handled by SourcePeeker or StudioPanel now
  }, []);

  // --- Load docs + conversations on mount ---
  useEffect(() => {
    API.get('/api/documents/').then(r => {
      const list = Array.isArray(r.data) ? r.data : (r.data.documents ?? []);
      setDocs(list.map((d: any) => ({
        id: d.id, filename: d.original_name ?? d.filename,
        source: d.source ?? d.filename, status: d.status === 'indexed' ? 'ready' : d.status,
        summary: d.summary, key_terms: d.key_terms,
        file_size: d.file_size,
      })));
    }).catch(() => {});
    API.get('/api/chat/conversations').then(r => {
      onConversationsChange?.(r.data ?? []);
    }).catch(() => {});
  }, [onConversationsChange]);

  // --- Load messages for existing conversation ---
  useEffect(() => {
    if (!initialConversationId) return;
    setConversationId(initialConversationId);
    API.get(`/api/chat/conversations/${initialConversationId}/messages`)
      .then(r => {
        const msgs = (r.data ?? []).map((m: any) => ({
          role: m.role === 'user' ? 'user' as const : 'ai' as const,
          text: m.content,
          time: fmtTime(),
          sources: m.sources ?? [],
          id: m.id,
        }));
        setMessages(msgs);
      })
      .catch(() => {});
  }, [initialConversationId]);

  // --- Audit handler ---
  const handleRunAudit = useCallback(async () => {
    if (selectedDocIds.length === 0) return;
    setAuditing(true);
    setAuditResult(null);
    try {
      const res = await API.post('/api/legal-studio/auditor', { document_ids: selectedDocIds });
      setAuditResult(res.data);
    } catch { /* ignore */ }
    setAuditing(false);
  }, [selectedDocIds]);

  // --- Analyst handoff ---
  const handleAnalystHandoff = useCallback(async () => {
    setHandingOff(true);
    try {
      const summary = messages.slice(-6).map(m => `${m.role}: ${m.text.slice(0, 200)}`).join('\n');
      await API.post('/api/legal-studio/sessions', {
        title: 'Legal → Finance Handoff',
        domain: 'finance',
        context_summary: summary,
      });
      window.location.href = '/finance';
    } catch { /* ignore */ }
    setHandingOff(false);
  }, [messages]);

  // --- Chat send ---
  const sendMessage = useCallback(async (text: string, attachedFiles?: File[]) => {
    // Pre-upload any quick-attached files
    if (attachedFiles && attachedFiles.length > 0) {
      for (const file of attachedFiles) {
        const fd = new FormData();
        fd.append('file', file);
        try {
          const res = await API.post('/api/documents/upload', fd);
          const doc = res.data;
          setDocs(prev => [...prev, {
            id: doc.id, filename: doc.original_name ?? doc.filename,
            source: doc.source ?? doc.filename, status: 'ready',
            summary: doc.summary, key_terms: doc.key_terms,
            file_size: doc.file_size,
          }]);
          setSelectedDocIds(prev => [...prev, doc.id]);
        } catch { /* upload error — continue with chat */ }
      }
    }

    const userDomain = detectDomain(text);
    if (userDomain) { setDomain(userDomain); }

    const userMsg: Message = { role: 'user', text, time: fmtTime() };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);
    setWebSearching(false);

    if (mode === 'deep_research') {
      setResearching(true);
      setResearchPhases([]);
      setResearchReport(null);
      try {
        const res = await API.post('/api/legal-studio/research', { query: text });
        const jobId = res.data.job_id;
        const evtSource = new EventSource(`${API_BASE}/api/legal-studio/research/${jobId}/stream`);
        evtSource.onmessage = (e) => {
          const data = JSON.parse(e.data);
          if (data.phase === 'done') {
            setResearchReport(data.report ?? '');
            setResearching(false);
            setLoading(false);
            evtSource.close();
            return;
          }
          setResearchPhases(prev => [...prev, data]);
        };
        evtSource.onerror = () => { evtSource.close(); setResearching(false); setLoading(false); };
      } catch {
        setResearching(false);
        setLoading(false);
      }
      return;
    }

    try {
      const body: any = {
        message: text, conversation_id: conversationId,
        stream: true, domain: userDomain ?? domain, mode,
      };
      const response = await fetch(`${API_BASE}/api/chat/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const reader = response.body?.getReader();
      if (!reader) { setLoading(false); return; }

      let aiText = '';
      let sources: Source[] = [];
      const decoder = new TextDecoder();

      const aiMsg: Message = { role: 'ai', text: '', time: fmtTime() };
      setMessages(prev => [...prev, aiMsg]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const evt = JSON.parse(line.slice(6));
            if (evt.event === 'chunk' || evt.type === 'chunk') {
              aiText += evt.content ?? evt.data ?? '';
              setMessages(prev => {
                const copy = [...prev];
                copy[copy.length - 1] = { ...copy[copy.length - 1], text: aiText };
                return copy;
              });
            } else if (evt.event === 'meta' || evt.type === 'meta') {
              if (evt.conversation_id) setConversationId(evt.conversation_id);
              if (evt.detected_domain) {
                const d = evt.detected_domain as DomainLabel;
                setDetectedDomain(d);
              }
            } else if (evt.event === 'sources' || evt.type === 'sources') {
              sources = evt.sources ?? evt.data ?? [];
              setMessages(prev => {
                const copy = [...prev];
                copy[copy.length - 1] = { ...copy[copy.length - 1], sources };
                return copy;
              });
            } else if (evt.event === 'status' && evt.data === 'searching_web') {
              setWebSearching(true);
            } else if (evt.event === 'queries_run') {
              setMessages(prev => {
                const copy = [...prev];
                copy[copy.length - 1] = { ...copy[copy.length - 1], queriesRun: evt.queries ?? evt.data };
                return copy;
              });
            } else if (evt.event === 'done' || evt.type === 'done') {
              if (evt.message_id) {
                setMessages(prev => {
                  const copy = [...prev];
                  copy[copy.length - 1] = { ...copy[copy.length - 1], id: evt.message_id };
                  return copy;
                });
              }
            }
          } catch { /* skip unparseable lines */ }
        }
      }
    } catch { /* ignore */ }

    setLoading(false);
    setWebSearching(false);

    // Refresh conversations
    API.get('/api/chat/conversations').then(r => {
      onConversationsChange?.(r.data ?? []);
    }).catch(() => {});
  }, [conversationId, domain, mode, onConversationsChange]);

  // --- Source click handler ---
  const handleSourceClick = useCallback((source: Source) => {
    setActiveSource(source);
    setSourcePanelOpen(true);
  }, []);

  // Latest sources for SourcePeeker
  const activeSources = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].sources && messages[i].sources!.length > 0) {
        return messages[i].sources!;
      }
    }
    return [];
  }, [messages]);

  // Auto-open source peeker when response finishes with sources
  const prevLoadingRef = useRef(false);
  const activeSourcesRef = useRef(activeSources);
  activeSourcesRef.current = activeSources;
  useEffect(() => {
    if (prevLoadingRef.current && !loading && activeSourcesRef.current.length > 0) {
      setSourcePanelOpen(true);
    }
    prevLoadingRef.current = loading;
  }, [loading]);

  // --- Render ---
  const centerContent = (
    <>
      {detectedDomain && (
        <div style={{ padding: '16px 40px 0', flexShrink: 0 }}>
          <DomainChip
            value={detectedDomain}
            editable
            onChange={(d) => { setDetectedDomain(d); setDomain(d); }}
          />
        </div>
      )}

      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 40px 0', flexShrink: 0 }}>
        {mode === 'analyst' && (
          <button
            type="button"
            onClick={handleAnalystHandoff}
            disabled={handingOff}
            aria-label="Hand off conversation to Finance Studio"
            style={{
              padding: '6px 14px', borderRadius: 'var(--s-r-sm)',
              background: 'rgba(168, 85, 247, 0.15)', color: '#a78bfa',
              border: '1px solid rgba(168, 85, 247, 0.3)', fontSize: 12,
              cursor: handingOff ? 'default' : 'pointer',
              opacity: handingOff ? 0.5 : 1, fontFamily: 'var(--s-font-ui)',
            }}
          >
            {handingOff ? '⏳ Handing off…' : '📊 Hand off to Finance Studio'}
          </button>
        )}
        <button
          type="button"
          onClick={handleRunAudit}
          disabled={selectedDocIds.length === 0 || auditing}
          aria-label={`Run audit on ${selectedDocIds.length} selected documents`}
          style={{
            padding: '6px 14px', borderRadius: 'var(--s-r-sm)',
            background: selectedDocIds.length > 0 ? 'var(--s-accent)' : 'rgba(255,255,255,0.06)',
            color: '#fff', border: 'none', fontSize: 12,
            cursor: selectedDocIds.length > 0 ? 'pointer' : 'default',
            opacity: selectedDocIds.length > 0 ? 1 : 0.5, fontFamily: 'var(--s-font-ui)',
          }}
        >
          {auditing ? '⏳ Auditing…' : `🔎 Run Audit (${selectedDocIds.length})`}
        </button>
      </div>

      {auditResult && (
        <div style={{ padding: '8px 40px' }}>
          <AuditorResultBubble
            risk_flags={auditResult.risk_flags as any}
            anomalies={auditResult.anomalies as any}
            compliance_gaps={auditResult.compliance_gaps as any}
            summary={auditResult.summary}
          />
        </div>
      )}

      <div className={`legal-studio__chat ${sourcePanelOpen ? 'legal-studio__chat--peeked' : ''}`}
           style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative' }}>
        <ChatMessages
          messages={messages}
          loading={loading}
          webSearching={webSearching}
          onSourceClick={handleSourceClick}
          activeSourceId={activeSource?.source}
        />
        {(researching || researchReport) && (
          <div style={{ padding: '8px 40px' }}>
            <ResearchBubble phases={researchPhases} report={researchReport} />
          </div>
        )}
        <SourcePeeker
          key={`source-peeker-${messages.length}`}
          sources={activeSources}
          isOpen={sourcePanelOpen}
          highlightedSource={activeSource?.source}
          onClose={() => { setSourcePanelOpen(false); setActiveSource(null); }}
        />
      </div>

      <ChatInput
        onSend={sendMessage}
        disabled={loading}
        initialValue={initialValue}
        mode={mode}
        onModeChange={setMode}
      />
    </>
  );

  return (
    <ThreePaneLayout
      left={
        <SourcesSidebar
          docs={docs}
          selectedIds={selectedDocIds}
          onSelect={handleDocSelect}
          onDelete={handleDocDelete}
          onUpload={handleDocUpload}
          onPreview={handleDocPreview}
        />
      }
      center={centerContent}
      right={<StudioPanel sourceIds={selectedDocIds} />}
    />
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc -b --noEmit`

Expected: No errors. The old `ModeDropdown` and `PreviewPane` imports are removed.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/studios/LegalStudio/LegalStudio.tsx
git commit -m "feat: rewrite LegalStudio with ThreePaneLayout, StudioPanel, ModePills

Replaces old flex-based multi-pane layout with CSS Grid 3-pane.
Removes ModeDropdown and PreviewPane imports.
Integrates StudioPanel (right) and redesigned ChatInput."
```

---

## Task 17: Create NotebookCard Component

**Files:**
- Create: `frontend/src/components/common/NotebookCard.tsx`

- [ ] **Step 1: Create the common directory and NotebookCard.tsx**

First create directory:

```bash
mkdir -p frontend/src/components/common
```

Then create `frontend/src/components/common/NotebookCard.tsx`:

```tsx
interface Notebook {
  id: string;
  title: string;
  updated_at: string;
  source_count?: number;
  thumbnail_icon?: string;
}

interface Props {
  notebook: Notebook;
  onClick: (id: string) => void;
}

export function NotebookCard({ notebook, onClick }: Props) {
  const dateStr = new Date(notebook.updated_at).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  });

  return (
    <div
      className="notebook-card"
      onClick={() => onClick(notebook.id)}
      role="button"
      tabIndex={0}
      onKeyDown={e => { if (e.key === 'Enter') onClick(notebook.id); }}
    >
      <div className="notebook-card__thumb">
        {notebook.thumbnail_icon ?? '📄'}
      </div>
      <div className="notebook-card__info">
        <div className="notebook-card__title">{notebook.title}</div>
        <div className="notebook-card__meta">
          {dateStr}{notebook.source_count != null ? ` · ${notebook.source_count} sources` : ''}
        </div>
      </div>
    </div>
  );
}

interface CreateCardProps {
  onClick: () => void;
}

export function CreateNotebookCard({ onClick }: CreateCardProps) {
  return (
    <div
      className="notebook-card notebook-card--create"
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={e => { if (e.key === 'Enter') onClick(); }}
    >
      <div className="notebook-card__thumb" style={{ color: 'var(--s-accent)' }}>+</div>
      <div className="notebook-card__info">
        <div className="notebook-card__title" style={{ color: 'var(--s-accent)' }}>
          Create New Notebook
        </div>
        <div className="notebook-card__meta">Start from scratch</div>
      </div>
    </div>
  );
}

export type { Notebook };
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc -b --noEmit`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/common/NotebookCard.tsx
git commit -m "feat: add NotebookCard and CreateNotebookCard components for home page"
```

---

## Task 18: Create HomePage Component

**Files:**
- Create: `frontend/src/pages/HomePage.tsx`

- [ ] **Step 1: Create HomePage.tsx**

```tsx
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../lib/api';
import { NotebookCard, CreateNotebookCard, type Notebook } from '../components/common/NotebookCard';

export default function HomePage() {
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    API.get('/api/chat/conversations')
      .then(r => {
        const convos = r.data ?? [];
        setNotebooks(convos.map((c: any) => ({
          id: c.id,
          title: c.title || 'Untitled Notebook',
          updated_at: c.updated_at || new Date().toISOString(),
          source_count: c.source_count,
        })));
      })
      .catch(() => {});
  }, []);

  const handleOpen = (id: string) => {
    navigate(`/notebook/${id}`);
  };

  const handleCreate = () => {
    navigate('/notebook/new');
  };

  return (
    <div className="home-page">
      <div className="home-page__header">
        <h1 className="home-page__title">📚 Legal Studio</h1>
        <button
          type="button"
          className="home-page__new-btn"
          onClick={handleCreate}
        >
          + New Notebook
        </button>
      </div>

      <div className="home-page__section-label">Recent Notebooks</div>

      <div className="notebook-grid">
        {notebooks.map(nb => (
          <NotebookCard key={nb.id} notebook={nb} onClick={handleOpen} />
        ))}
        <CreateNotebookCard onClick={handleCreate} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc -b --noEmit`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/HomePage.tsx
git commit -m "feat: add HomePage with notebook card grid like NotebookLM"
```

---

## Task 19: Update App.tsx Routing

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Update App.tsx**

Replace the full contents of `App.tsx`:

```tsx
import React, { Suspense, useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useParams, useNavigate, useLocation } from 'react-router-dom';
import { API, type Alert } from './lib/api';
import { StudioProvider } from './context/StudioProvider';
import { ThemeProvider } from './context/ThemeContext';
import { StudioSwitcher } from './components/StudioSwitcher';
import { ContextualSidebar } from './components/ContextualSidebar';

const LegalStudio = React.lazy(() =>
  import('./components/studios/LegalStudio/LegalStudio').then(m => ({ default: m.LegalStudio }))
);
const FinanceStudio = React.lazy(() =>
  import('./components/studios/FinanceStudio/FinanceStudio').then(m => ({ default: m.FinanceStudio }))
);
const RegulatoryStudio = React.lazy(() =>
  import('./components/studios/RegulatoryStudio/RegulatoryStudio').then(m => ({ default: m.RegulatoryStudio }))
);
const SettingsPage = React.lazy(() => import('./pages/SettingsPage'));
const TemplateStudio = React.lazy(() =>
  import('./components/studios/TemplateStudio/TemplateStudio').then(m => ({ default: m.TemplateStudio }))
);
const HomePage = React.lazy(() => import('./pages/HomePage'));

interface Conversation {
  id: string;
  title: string;
  updated_at: string;
}

function PageLoader() {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flex: 1,
      background: 'var(--s-bg)',
    }}>
      <div className="loading-spinner" />
    </div>
  );
}

function NotebookPage({ conversations, onConversationsChange }: {
  conversations: Conversation[];
  onConversationsChange: (c: Conversation[]) => void;
}) {
  const { id } = useParams<{ id: string }>();
  const convId = id === 'new' ? undefined : id;

  return (
    <LegalStudio
      key={convId ?? `new-${Date.now()}`}
      onConversationsChange={onConversationsChange}
      initialConversationId={convId}
    />
  );
}

function AppInner() {
  const [alertCount, setAlertCount] = useState(0);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const navigate = useNavigate();
  const location = useLocation();

  // Determine if current route is a legal route (home or notebook)
  const isLegalRoute = location.pathname === '/' || location.pathname.startsWith('/notebook');

  const handleLoadConversation = (id: string) => {
    navigate(`/notebook/${id}`);
  };

  const handleNewChat = () => {
    navigate('/notebook/new');
  };

  useEffect(() => {
    API.get('/api/monitoring/alerts')
      .then(r => {
        const data: Alert[] = Array.isArray(r.data) ? r.data : [];
        setAlertCount(Array.isArray(data) ? data.filter(a => a.severity === 'critical').length : 0);
      })
      .catch(() => {});
  }, []);

  return (
    <div className={`app-shell ${isLegalRoute ? 'app-shell--legal' : ''}`}>
      <StudioSwitcher alertCount={alertCount} />
      <ContextualSidebar conversations={conversations} onLoadConversation={handleLoadConversation} onNewChat={handleNewChat} />
      <main className="studio-main">
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route
              path="/notebook/new"
              element={
                <LegalStudio
                  key={`new-${Date.now()}`}
                  onConversationsChange={setConversations}
                />
              }
            />
            <Route
              path="/notebook/:id"
              element={
                <NotebookPage
                  conversations={conversations}
                  onConversationsChange={setConversations}
                />
              }
            />
            <Route path="/finance" element={<FinanceStudio />} />
            <Route path="/monitoring" element={<RegulatoryStudio />} />
            <Route path="/templates" element={<TemplateStudio />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </Suspense>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
    <Router>
      <StudioProvider>
        <AppInner />
      </StudioProvider>
    </Router>
    </ThemeProvider>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc -b --noEmit`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: add HomePage route and notebook/:id routing

/ now shows the NotebookLM-style home page with card grid.
/notebook/:id loads the 3-pane Legal Studio.
/notebook/new creates a fresh notebook."
```

- [ ] **Step 5: Update StudioSwitcher to recognize /notebook/* as legal route**

In `frontend/src/components/StudioSwitcher.tsx`, update the `isActive` function to recognize notebook routes as legal:

Replace:
```tsx
  const isActive = (path: string) =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);
```
With:
```tsx
  const isActive = (path: string) =>
    path === '/'
      ? location.pathname === '/' || location.pathname.startsWith('/notebook')
      : location.pathname.startsWith(path);
```

- [ ] **Step 6: Commit StudioSwitcher change**

```bash
git add frontend/src/components/StudioSwitcher.tsx
git commit -m "fix: StudioSwitcher recognizes /notebook/* as legal route"
```

---

## Task 20: Full Build Verification and Fix Any Issues

**Files:**
- Potentially any file from Tasks 1-19

- [ ] **Step 1: Run full TypeScript check**

Run: `cd frontend && npx tsc -b --noEmit 2>&1`

Fix any type errors found.

- [ ] **Step 2: Run full Vite build**

Run: `cd frontend && npx vite build 2>&1`

Expected: Build completes successfully with no errors.

- [ ] **Step 3: Fix any errors found in Steps 1-2**

If errors are found, fix them in the relevant files.

- [ ] **Step 4: Commit fixes**

```bash
git add -A
git commit -m "fix: resolve build errors from UI redesign"
```

---

## Task 21: Cleanup Deprecated Files

**Files:**
- Modify: `frontend/src/components/studios/LegalStudio/ModeDropdown.tsx` (add deprecation notice)
- Modify: `frontend/src/components/studios/LegalStudio/PreviewPane.tsx` (add deprecation notice)

- [ ] **Step 1: Add deprecation comments**

In `ModeDropdown.tsx`, prepend:

```tsx
/**
 * @deprecated Replaced by ModePills component.
 * Kept for backward compatibility with other studios.
 * New code should import from './ModePills' instead.
 */
```

In `PreviewPane.tsx`, prepend:

```tsx
/**
 * @deprecated Replaced by StudioPanel > ReportPreview.
 * Kept for backward compatibility.
 */
```

- [ ] **Step 2: Re-export ChatMode from ModePills for backward compat**

Verify that `ChatInput.tsx` now exports `ChatMode` type (it does in the rewrite). Any other file that imports `ChatMode` from `ModeDropdown` should still work because `ModeDropdown.tsx` still exports it.

- [ ] **Step 3: Final build check**

Run: `cd frontend && npx vite build 2>&1`

Expected: Build succeeds.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: add deprecation notices to ModeDropdown and PreviewPane

Both replaced by new components but kept for backward compat."
```

---

## Summary

| Task | Component | Action |
|---|---|---|
| 1 | CSS | Add all new CSS classes to index.css |
| 2 | SourceTypeIcon | Create colored file type badges |
| 3 | ModePills | Create Gemini-style pill mode selector |
| 4 | AttachButton | Create `+` attach with file picker |
| 5 | AttachedFileChips | Create removable file chip display |
| 6 | ChatInput | Redesign with new sub-components |
| 7 | SourceSearch | Create search input for sources |
| 8 | EmptySourcesState | Create empty state CTA |
| 9 | AddSourcesOverlay | Create drag-drop upload overlay |
| 10 | SourcesSidebar | Redesign with type icons, search, overlay |
| 11 | AuditorFormatGrid | Create 2×2 format selector |
| 12 | StudioCards | Create report action cards |
| 13 | ReportPreview | Create report preview with markdown |
| 14 | StudioPanel | Create right panel (cards + format + preview) |
| 15 | ThreePaneLayout | Create CSS Grid 3-column wrapper |
| 16 | LegalStudio | Rewrite to use 3-pane layout |
| 17 | NotebookCard | Create notebook cards for home page |
| 18 | HomePage | Create NotebookLM-style landing page |
| 19 | App.tsx | Update routing for home + notebook pages |
| 20 | Build Verification | Full build check and fix |
| 21 | Cleanup | Deprecate old components |
