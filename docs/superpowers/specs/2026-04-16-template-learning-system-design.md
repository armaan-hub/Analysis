# Template Learning System — Design Spec

**Date:** 2026-04-16  
**Objective:** Make PDF format setup scalable — first-time takes hours (auto-extract + manual verification), future runs take seconds (config-based rendering).

---

## 1. Problem Statement

**Current state:** Each new user format requires 1-2 weeks of manual Python fine-tuning in `format_applier.py`. With N users and M different formats, this is O(N×M) effort — completely unscalable.

**Goal:** Reduce first-time setup from 1-2 weeks to 1-2 hours (automated extraction + brief manual verification), and future runs to <5 seconds (config lookup + render).

**Key constraint:** Generated PDF must match reference format precisely (columns, fonts, spacing, notes placement) for auditor acceptance. Silent failures are unacceptable.

---

## 2. Architecture

```
FIRST TIME (hours, runs in background):

  User uploads reference PDF
       ↓
  template_analyzer.py
  ├─ Extracts: page size, margins, fonts, tables, spacing
  ├─ Calculates: confidence scores per element
  └─ Produces: template_config.json + confidence report
       ↓
  template_verifier.py
  ├─ Renders sample PDF using extracted config
  ├─ Compares: page count, dimensions, text positions vs reference
  ├─ Produces: verification report (pass/fail/needs review)
  └─ If confidence low: mark "needs review" + show editor UI
       ↓
  Manual review (user can skip if verification passes)
  └─ User edits columns, fonts, positions in template_editor UI
       ↓
  template_store.py
  └─ Saves template_config.json to DB + stores verification results
       ↓
  User notified: "Template ready. Future reports: seconds."


FUTURE RUNS (seconds):

  User uploads new financial data + selects saved template
       ↓
  template_store.py
  └─ Loads template_config.json from DB
       ↓
  template_applier.py
  ├─ Applies config (page size, margins, fonts, table layout)
  ├─ Injects financial data
  └─ Renders PDF
       ↓
  Output: PDF matching reference format ✓


TEMPLATE SCOPE:
  ├─ Private templates  → per user, stored in DB
  └─ Global library     → shared across all users (optional publish)
```

---

## 3. Components

| Component | Type | Purpose |
|---|---|---|
| `backend/core/template_analyzer.py` | Python service | Reads reference PDF → extracts formatting rules with confidence scores |
| `backend/core/template_verifier.py` | Python service | Renders test PDF using config → compares to reference → pass/fail/needs-review |
| `backend/core/template_applier.py` | Python service | Refactored `format_applier.py` — reads config instead of hardcoded defaults |
| `backend/core/template_store.py` | Python service | Save/load templates from DB (by user + name) |
| `backend/api/templates.py` | FastAPI routes | `/upload-reference`, `/learn`, `/verify`, `/status`, `/list`, `/apply`, `/edit` |
| `frontend/TemplateManager/` | React UI | Upload reference PDF, review extraction results, manual editor, pick saved templates |
| `skills/learn-audit-format/SKILL.md` | Superpowers skill | CLI: `copilot learn-audit-format <pdf-path> --save <name>` for admins |

---

## 4. Data Model

### Database Schema
```sql
CREATE TABLE templates (
    id          TEXT PRIMARY KEY,       -- uuid
    user_id     TEXT,                   -- NULL = global/shared
    name        TEXT,                   -- "Castle Plaza Format", "IFRS Standard"
    config_json TEXT,                   -- template config (see below)
    embedding   BLOB,                   -- vector for variation matching
    status      TEXT,                   -- 'draft' | 'verified' | 'needs_review' | 'ready'
    verification_report TEXT,           -- JSON with pass/fail details
    page_count  INTEGER,                -- reference page count
    source_pdf  BLOB,                   -- original PDF filename
    created_at  DATETIME,
    updated_at  DATETIME,
    is_global   BOOLEAN DEFAULT 0,      -- published to shared library?
    confidence_score REAL               -- 0.0 - 1.0
);
```

### Template Config Structure
```json
{
  "page": {
    "width": 612,
    "height": 792,
    "unit": "points"
  },
  "margins": {
    "top": 72,
    "bottom": 72,
    "left": 72,
    "right": 72
  },
  "fonts": {
    "heading": { "family": "Helvetica-Bold", "size": 12 },
    "body": { "family": "Helvetica", "size": 9 },
    "footer": { "family": "Helvetica", "size": 8 }
  },
  "substitutions": {
    "ABCDEE+Helvetica": "Helvetica"
  },
  "tables": [
    {
      "name": "sofp_table",
      "page_type": "financial",
      "layout": "flow",
      "columns": [
        { "name": "label", "width": 240 },
        { "name": "year1", "width": 90 },
        { "name": "year2", "width": 90 }
      ],
      "confidence": 0.92
    }
  ],
  "sections": [
    { "name": "cover", "page": 1 },
    { "name": "sofp", "page": 2, "layout": "flow" },
    { "name": "sopl", "page": 3, "layout": "flow" },
    { "name": "notes", "pages": [4, 5, 6], "layout": "flow", "overflow": "continue_next_page" }
  ],
  "extraction_metadata": {
    "analyzer_version": "1.0",
    "extracted_at": "2026-04-16T20:00:00Z",
    "confidence_per_element": {
      "page_size": 0.99,
      "margins": 0.85,
      "fonts": 0.78,
      "tables": 0.92
    }
  }
}
```

---

## 5. Workflows

### Workflow A: Learn New Format (First Time)

```
1. User/Admin: Upload reference PDF via UI or CLI
2. Backend: Start background job
   - Call template_analyzer.extract() → raw extracted config + confidence scores
   - Call template_verifier.verify() → test render + comparison
   - If confidence >= 0.85: mark "verified"
   - If 0.70 <= confidence < 0.85: mark "needs_review", show editor
   - If confidence < 0.70: mark "draft", user must edit before approval
3. Frontend: Poll /api/templates/status/{job_id}
   - Show progress bar until job completes
   - If verified: "Ready to use!"
   - If needs_review: "Review extracted data" + manual editor UI
4. (If needed) User edits config in UI:
   - Adjust columns, fonts, positions
   - Click "Preview" → re-verify
   - If passes: save
5. Template stored in DB, marked "ready"
```

### Workflow B: Apply Saved Template (Future Runs)

```
1. User: Upload new financial data (trial balance)
2. User: Select saved template
3. Backend: Call template_applier.render()
   - Load template_config from DB
   - Inject financial data
   - Render PDF using ReportLab + config
   - Output: perfect format match ✓
4. Return PDF to user (< 5 seconds)
```

### Workflow C: Publish to Global Library

```
1. User has verified template
2. User clicks "Publish to Library" (optional)
3. Template copied to DB with user_id = NULL
4. Other users see it in template picker: "IFRS Standard (shared)"
5. They can apply it with one click
```

---

## 6. Error Handling & Safety

**If extraction confidence is low:**
- Mark template "needs_review"
- Show visual editor with extracted values highlighted
- Require explicit user approval before marking "ready"
- Log why confidence was low (missing fonts, unclear tables, etc.)

**If verification fails (test render doesn't match reference):**
- Show side-by-side diff of rendered vs reference
- List specific mismatches (page count, text position errors, etc.)
- Suggest which config elements to adjust
- Mark as "needs_review" until user fixes

**If user has no verified template:**
- Fall back to default system template (basic IFRS format)
- Warn: "Using default format; output may not match your preferences"

**For financial data gaps (e.g., missing 2024 prior-year data):**
- This is a data problem, not a template problem
- Handled by `audit_profile_builder.py` calling `prior_year_extractor.py`
- Template system does not fix data gaps

---

## 7. Success Criteria

✓ **First-time setup:** Extract + verification completes in < 1 hour (background, non-blocking)  
✓ **Future renders:** < 5 seconds per PDF (config lookup + ReportLab render)  
✓ **Format accuracy:** Generated PDF matches reference page dimensions, fonts, column widths, spacing  
✓ **Verification:** Automated comparison catches mismatches before user sees them  
✓ **Scalability:** 100 users with 5 common formats = 5 learned templates, used 100 times in seconds  
✓ **Safety:** No silent failures; low-confidence templates marked for review  

---

## 8. Out of Scope

- **LLM-based auto-correction:** Explicitly not doing this (too slow, too unpredictable)
- **Arbitrary PDF format support:** Only financial audit PDFs (IFRS-like structure assumed)
- **Real-time collaboration on template editing:** Single-user edit, no live sync
- **Template versioning/rollback:** V1 does not support multiple versions per template (can add later)
- **Automatic format detection:** User explicitly picks which template to use (no guessing)

---

## 9. Dependencies

**Existing:**
- FastAPI backend
- React frontend
- ReportLab for PDF generation
- PyMuPDF (fitz) for PDF reading
- SQLite DB

**New packages needed:**
- `pdf2image` — convert PDF pages to images for visual comparison
- `pillow` — image diff for verification
- `difflib` — text diff for verification

**Internal:**
- `prior_year_extractor.py` — must be wired into audit_profile_builder (separate fix, orthogonal to this)

---

## 10. Timeline Estimate

- **Design & validation:** Completed ✓
- **Implementation:** 5-7 days (template_analyzer, verifier, applier, UI, API routes)
- **Testing & refinement:** 2-3 days
- **Total before first successful template:** 1-2 weeks
- **Per new template after that:** 1-2 hours (extraction + verification) + manual review if needed

---

## 11. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| PDF table detection fails silently | High | Verification step catches this; mark as needs_review |
| Font extraction doesn't translate to ReportLab | High | Font substitution map + visual diff in verification |
| Content-dependent layout breaks (e.g., longer notes) | High | Store dynamic flow rules, not absolute positions |
| Global library has duplicates | Medium | Fingerprint-based dedup before merge |
| User gets impatient during 1-hour first-time analysis | Low | Show progress, allow background processing |

---

## 12. Next Steps

1. **Write implementation plan** (invoke writing-plans skill)
2. **Implement components in order:**
   - `template_analyzer.py` (PDF extraction)
   - `template_verifier.py` (verification + visual diff)
   - `template_applier.py` (refactored rendering)
   - `template_store.py` (DB operations)
   - FastAPI routes + frontend UI
   - Superpowers SKILL.md
3. **Test with real Castle Plaza format** — learn from reference PDF, verify, apply to new data
4. **Iterate based on real-world feedback**

