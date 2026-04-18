# NotebookLM-Style Finance Studio — Design Spec

**Date:** 2026-04-19
**Replaces:** `FinancialStudio` (entire wizard) + `AuditProfileStudio`
**Approach:** Modular frontend (Approach 2) + Backend-owned versioning (Approach 3)

---

## 1. Problem Statement

The existing Financial Studio is a linear 10-step wizard (upload → map → requirements → evidence → draft → analysis → format → export). The AuditProfileStudio is a separate 4-tab interface. Both are siloed, hard to navigate, and don't let the auditor stay in context while working.

**Goal:** Replace both with a single NotebookLM-style three-panel workspace where:
- Left panel = source documents + learned audit profile (always visible)
- Center = AI chat (left half) + live report preview (right half)
- Right panel = all output types + auditor format selector + version history
- AI guides the user through audit workflow steps with suggested actions
- Full version branching: "What if I remap Acct 4001?" — compare versions side-by-side

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  FinanceStudio.tsx  (orchestrator)                                              │
│  FinanceStudioContext  (shared state: profile, versions, chat, outputs)         │
├──────────────┬──────────────────────────────────────────┬───────────────────────┤
│  LEFT PANEL  │              CENTER                      │     RIGHT PANEL       │
│  ~280px      │             flex-1                       │      ~300px           │
│              │                                          │                       │
│ SourceDocs   │  AuditChat.tsx    │  ReportPreview.tsx   │  ExportsPanel.tsx     │
│ Sidebar.tsx  │  (left half)      │  (right half)        │                       │
│              │                   │                      │  • Format selector    │
│ - Upload     │  - Chat messages  │  - PDF-style live    │    (IFRS/GAAP/custom) │
│   dropzone   │  - Suggested      │    preview           │  • 7 output cards     │
│ - Doc cards  │    action btns    │  - Page-by-page      │  • Version history    │
│ - Learned    │  - Workflow step  │    scroll            │  • Branch + compare   │
│   profile    │    tracker        │                      │                       │
│   tree       │  - Freeform input │                      │                       │
│ - Version    │                   │                      │                       │
│   switcher   │                   │                      │                       │
└──────────────┴───────────────────┴──────────────────────┴───────────────────────┘
```

---

## 3. Frontend Component Structure

```
frontend/src/components/studios/FinanceStudio/
├── FinanceStudio.tsx                  ← Main orchestrator
├── FinanceStudio.css
├── FinanceStudioContext.tsx           ← Context + hooks
│
├── SourceDocsSidebar/
│   ├── SourceDocsSidebar.tsx         ← Left panel container
│   ├── DocumentCard.tsx              ← File row: name, type badge, confidence bar
│   ├── LearnedProfileTree.tsx        ← Collapsible sections tree
│   └── VersionSwitcher.tsx           ← Branch selector dropdown + version list
│
├── AuditChat/
│   ├── AuditChat.tsx                 ← Chat container (messages + input)
│   ├── ChatMessage.tsx               ← AI/user bubble + citation chips
│   ├── SuggestedActions.tsx          ← Quick-action buttons
│   └── WorkflowSteps.tsx             ← Step progress tracker (5 steps)
│
├── ReportPreview/
│   ├── ReportPreview.tsx             ← Right-center: live PDF preview
│   └── PreviewPage.tsx               ← Individual page renderer
│
└── ExportsPanel/
    ├── ExportsPanel.tsx              ← Right panel container
    ├── ExportCard.tsx                ← One card per output type
    ├── FormatPicker.tsx              ← Auditor format selector (prebuilt + custom)
    └── VersionCompare.tsx            ← Side-by-side diff view
```

**Deleted (replaced):**
- `frontend/src/components/studios/FinancialStudio/` — entire folder (15 files)
- `frontend/src/components/studios/AuditProfileStudio/AuditProfileStudio.tsx`

**Updated:**
- `frontend/src/context/StudioProvider.tsx` — remove `'financial'` and `'profiles'` studio types, add `'finance'`
- `frontend/src/components/StudioSwitcher.tsx` — replace two sidebar icons with one "Finance Studio" icon

---

## 4. State Management

`FinanceStudioContext` holds all shared state. Components consume via `useFinanceStudio()` hook.

```typescript
interface FinanceStudioState {
  // Profile
  activeProfile: AuditProfile | null;
  setActiveProfile: (p: AuditProfile) => void;

  // Versioning
  versions: ProfileVersion[];
  activeVersionId: string | null;
  switchVersion: (id: string) => void;
  branchVersion: (name: string) => Promise<void>;

  // Source docs
  sourceDocs: SourceDoc[];
  uploadDoc: (file: File, docType: string) => Promise<void>;
  deleteDoc: (id: string) => Promise<void>;

  // Chat
  chatHistory: ChatMessage[];
  sendMessage: (text: string) => Promise<void>;
  chatLoading: boolean;

  // Outputs
  outputs: GeneratedOutput[];        // one per output_type
  generateOutput: (type: OutputType) => Promise<void>;
  selectedTemplateId: string | null; // auditor format applied to all outputs
  setSelectedTemplate: (id: string) => void;

  // Workflow
  workflowStep: 1 | 2 | 3 | 4 | 5;
  setWorkflowStep: (s: number) => void;
}
```

**Workflow steps:**
1. Upload Source Documents
2. Build / Review Learned Profile
3. Validate with AI (chat)
4. Select Auditor Format
5. Generate Outputs

---

## 5. Backend API

### Reused (no changes needed)
```
GET  /api/templates/list                         ← Format picker dropdown
GET  /api/templates/prebuilt                     ← IFRS/GAAP/UAE/FRS102/ZATCA/GCC cards
POST /api/templates/prebuilt/{id}/apply          ← Apply prebuilt format
POST /api/templates/upload-reference             ← Learn format from PDF
POST /api/templates/learn/{job_id}               ← Start learning job
GET  /api/templates/status/{job_id}              ← Poll job status
POST /api/templates/{id}/feedback                ← Confidence feedback
GET  /api/audit-profiles                         ← Profile list (left sidebar header)
GET  /api/audit-profiles/{id}                    ← Profile detail
POST /api/audit-profiles                         ← Create new profile
DELETE /api/audit-profiles/{id}                  ← Delete profile
POST /api/audit-profiles/{id}/upload-source      ← Upload source doc
GET  /api/audit-profiles/{id}/source-documents   ← List source docs
POST /api/audit-profiles/{id}/build-profile      ← Run profile builder
```

### New endpoints (Approach 3 — backend owns versioning + chat + generation)

**File:** `backend/api/audit_studio.py`

```
# Versioning
POST /api/audit-profiles/{id}/branch
  body: { "branch_name": "remap-4001" }
  → Creates a copy of current profile version; returns new version_id

GET  /api/audit-profiles/{id}/versions
  → Returns list of all versions: [{ id, name, created_at, is_current }]

GET  /api/audit-profiles/{id}/versions/{v1_id}/compare/{v2_id}
  → Returns JSON diff of two versions (account_mappings, financial_data, etc.)

PATCH /api/audit-profiles/{id}/versions/{version_id}/activate
  → Sets a version as the active working version

# AI Chat
POST /api/audit-profiles/{id}/chat
  body: { "message": "Flag anomalies in revenue accounts" }
  → Streams AI response with citations from source docs

GET  /api/audit-profiles/{id}/chat/history
  → Returns full chat history for the active version

DELETE /api/audit-profiles/{id}/chat/history
  → Clear chat history

# Report Generation
POST /api/audit-profiles/{id}/generate/{output_type}
  # output_type: audit_report | profit_loss | balance_sheet | cash_flow |
  #              tax_schedule | management_report | custom
  body: { "template_id": "uuid", "options": {} }
  → Background job → returns job_id

GET  /api/audit-profiles/{id}/outputs
  → Lists all generated outputs with status + download URLs

GET  /api/audit-profiles/{id}/outputs/{output_id}/download
  → Download generated file
```

---

## 6. Data Models

### New DB Models (`backend/db/models.py` additions)

```python
class ProfileVersion(Base):
    __tablename__ = "profile_versions"
    id            = Column(Text, primary_key=True, default=lambda: str(uuid4()))
    profile_id    = Column(Text, ForeignKey("audit_profiles.id"), nullable=False)
    branch_name   = Column(Text, nullable=False)           # "main", "remap-4001"
    profile_json  = Column(Text, nullable=False)           # full profile snapshot
    is_current    = Column(Boolean, default=False)
    created_at    = Column(DateTime, default=datetime.utcnow)

class AuditChatMessage(Base):
    __tablename__ = "audit_chat_messages"
    id            = Column(Text, primary_key=True, default=lambda: str(uuid4()))
    profile_id    = Column(Text, ForeignKey("audit_profiles.id"), nullable=False)
    version_id    = Column(Text, ForeignKey("profile_versions.id"), nullable=True)
    role          = Column(Text, nullable=False)           # "user" | "assistant"
    content       = Column(Text, nullable=False)
    citations     = Column(Text, nullable=True)            # JSON: [{doc_id, page, excerpt}]
    created_at    = Column(DateTime, default=datetime.utcnow)

class GeneratedOutput(Base):
    __tablename__ = "generated_outputs"
    id            = Column(Text, primary_key=True, default=lambda: str(uuid4()))
    profile_id    = Column(Text, ForeignKey("audit_profiles.id"), nullable=False)
    version_id    = Column(Text, ForeignKey("profile_versions.id"), nullable=True)
    output_type   = Column(Text, nullable=False)           # audit_report | pl | etc.
    template_id   = Column(Text, ForeignKey("templates.id"), nullable=True)
    status        = Column(Text, default="pending")        # pending|processing|ready|failed
    output_path   = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
```

---

## 7. Auditor Format Integration

The template learning system integrates at two points:

**Point 1 — FormatPicker (right panel):**
- Loads `GET /api/templates/list` + `GET /api/templates/prebuilt`
- Shows prebuilt formats: IFRS Standard, GAAP Standard, UAE Corporate Tax, UK FRS 102, Saudi ZATCA, GCC Standard
- Shows learned custom formats per user (extracted from uploaded reference PDFs)
- Selected format applies to ALL 7 output types when generating

**Point 2 — "Learn From This Report" button (SourceDocsSidebar):**
- Any uploaded PDF marked as "Report Template" doc type can trigger format learning
- Button submits to `POST /api/templates/upload-reference` → starts background job
- On completion, new custom format appears in FormatPicker automatically

**Output types and their template mapping:**
| Output | Template sections used |
|--------|----------------------|
| Audit Report | All sections (cover, sofp, sopl, notes) |
| Profit & Loss | `sopl` section only |
| Balance Sheet | `sofp` section only |
| Cash Flow | `socf` section only |
| Tax Schedule | `tax` section (fallback: body font + table layout) |
| Management Report | `cover` + `notes` sections |
| Custom Export | User-defined section selection |

---

## 8. Workflow Steps (AuditChat WorkflowSteps.tsx)

```
Step 1: Upload Source Documents
  → Upload trial balance, prior audit, report template, chart of accounts
  → Status: "3/4 docs extracted"

Step 2: Build Learned Profile
  → Click "Build Profile" → backend merges all extractions
  → Status: "46 account mappings, 2 financial periods"

Step 3: Validate with AI
  → Suggested actions: "Flag Anomalies", "Audit Risk Summary",
    "Account Drill-Down", "Prior Year Comparison"
  → Freeform: "What's the revenue trend for the last 3 years?"
  → Status: "Validated — 2 risks flagged"

Step 4: Select Auditor Format
  → FormatPicker in right panel
  → Status: "IFRS Standard A4 selected"

Step 5: Generate Outputs
  → Each ExportCard has "Generate" button
  → Status per card: pending → processing → ready (download button appears)
```

---

## 9. Error Handling

| Scenario | Behavior |
|----------|----------|
| Doc extraction confidence < 0.7 | Yellow warning badge on DocumentCard, "Review" button |
| Chat API failure | Retry button on failed bubble, rest of chat unblocked |
| Generate job fails | ExportCard shows error reason + Re-try button |
| Version compare has no diff | "No differences found between these versions" message |
| Template confidence < 0.7 | FormatPicker shows warning, blocks generate until reviewed |
| No profile built yet | WorkflowSteps shows Step 2 as blocked, generates disabled |
| Upload of unsupported file type | Inline error under dropzone, supported types listed |

---

## 10. Testing

**Backend test files:**
- `backend/tests/test_audit_studio_versions.py` — branch, compare, activate
- `backend/tests/test_audit_studio_chat.py` — send message, history, clear
- `backend/tests/test_audit_studio_generate.py` — generate each output type, download

**Frontend component tests:**
- `SourceDocsSidebar.test.tsx` — upload, delete, tree expand/collapse
- `AuditChat.test.tsx` — message send, suggested action click, workflow step advance
- `ExportsPanel.test.tsx` — format selection, generate trigger, card status transitions

**Integration test:**
```
1. POST /audit-profiles (create)
2. POST /audit-profiles/{id}/upload-source (trial balance)
3. POST /audit-profiles/{id}/build-profile
4. POST /audit-profiles/{id}/chat ("Flag anomalies")
5. POST /api/templates/prebuilt/ifrs-standard-a4/apply
6. POST /audit-profiles/{id}/generate/audit_report
7. GET  /audit-profiles/{id}/outputs/{id}/download → 200 + valid PDF
```

---

## 11. Out of Scope

- Real-time multi-user collaboration on the same profile
- Automated anomaly detection without AI chat (all analysis is chat-driven)
- Mobile/tablet responsive layout (desktop-first)
- Exporting to Google Docs or SharePoint (download only)
- Automatic format detection without user selection

---

## 12. Success Criteria

- Upload 3 docs → Build Profile → Chat → Generate Audit Report in < 5 min end-to-end
- All 7 output types generate successfully with IFRS Standard format
- Version branching: create branch → change account mapping → compare → shows diff
- Zero "Network Error" banners (all API calls have proper error handling)
- Full test suite passes (existing 203 tests + new tests for audit studio)
