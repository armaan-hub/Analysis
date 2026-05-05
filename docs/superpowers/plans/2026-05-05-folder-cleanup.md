# Folder Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Archive ~5.4GB of unnecessary/redundant files from the Agentic AI OneDrive folder into a single ZIP backup, then delete the originals, leaving only essential files.

**Architecture:** Use macOS `zip` with `-r` flag to bundle all archive targets into one ZIP in the root of the Agentic AI folder. Verify integrity with `unzip -t`. Delete originals only after verification passes. Use `tar.gz` is NOT preferred here — zip is simpler and universally readable on Windows/Mac. Node_modules directories are excluded from inside the ZIP where they appear in non-essential standalone folders (they are regeneratable via `npm install`).

**Tech Stack:** macOS `zip`, `unzip`, `rm -rf`, `du`, `git`

---

## Items to Archive (Total: ~5.4GB uncompressed)

| Path | Size | Reason |
|------|------|--------|
| `Project_AccountingLegalChatbot/` | 3.1GB | Canonical copy is in git at `~/chatbot_local` |
| `25. 21-Mar-2026/` | 1.4GB | Old March 2026 session, superseded |
| `desktop/` | 576MB | Only contains `node_modules`, no source code |
| `frontend/` | 269MB | Stale standalone frontend + orphaned `node_modules` |
| `backend/` | 3.7MB | Stale root-level backend (real one is in `Main Branch/`) |
| `vector_store/` | 648KB | Stale root-level ChromaDB |
| `vector_store_v2/` | 648KB | Stale root-level ChromaDB v2 |
| `src/` | 4KB | Orphaned hooks folder at root |
| `frontend_server.log` | 32KB | Runtime log |
| `backend_server.log` | 28KB | Runtime log |
| `run_project.log` | 8KB | Runtime log |
| `.pytest_cache/` | 20KB | Regeneratable pytest cache |
| `.vs/` | 1MB | Visual Studio IDE cache |
| `.claude/` | 4KB | AI session state cache |
| `.code-review-graph/` | 4.7MB | Code review tool cache |

## Items to Keep

| Path | Reason |
|------|---------|
| `Main Branch/` | Working project snapshot with all source |
| `data_source_finance/` | RAG finance PDFs — irreplaceable |
| `data_source_law/` | RAG law PDFs — irreplaceable |
| `PROJECT_JOURNAL.md` | Living journal |
| `.env` | API keys (gitignored) |
| `skills/` | Custom Copilot skills |
| `Gemini_Sessions/` | Session logs |
| `brain/` | Project planning files |
| `Testing data/` | Test data |
| `Project_SuperpowersIntegration/` | Active small project |
| `docs/` | Specs and plans |
| `auto-commit.ps1`, `setup-auto-push.ps1`, `setup_python_env.*` | Setup scripts |
| `.git/`, `.gitignore`, `.github/`, `.code-review-graphignore` | Git infrastructure |
| `archive_backup_2026-05-05.zip` | The backup we create |

---

## Variables (used throughout)

```bash
BASE="/Users/armaan/Library/CloudStorage/OneDrive-TheEraCorporations/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI"
ZIP="$BASE/archive_backup_2026-05-05.zip"
```

---

## Task 1: Create the ZIP archive

**⚠️ Warning:** This will take 10–30 minutes depending on disk speed. The `node_modules` folders contain many small files. Do NOT stop mid-way.

**Files:**
- Create: `$BASE/archive_backup_2026-05-05.zip`

- [ ] **Step 1: Verify archive targets exist before starting**

```bash
BASE="/Users/armaan/Library/CloudStorage/OneDrive-TheEraCorporations/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI"
ls -d \
  "$BASE/Project_AccountingLegalChatbot" \
  "$BASE/25. 21-Mar-2026" \
  "$BASE/desktop" \
  "$BASE/frontend" \
  2>/dev/null | wc -l
```

Expected output: `4` (all 4 large directories exist)

- [ ] **Step 2: Create the ZIP (run in background — it will take time)**

```bash
BASE="/Users/armaan/Library/CloudStorage/OneDrive-TheEraCorporations/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI"
ZIP="$BASE/archive_backup_2026-05-05.zip"

cd "$BASE" && zip -r "$ZIP" \
  "Project_AccountingLegalChatbot" \
  "25. 21-Mar-2026" \
  "desktop" \
  "frontend" \
  "backend" \
  "vector_store" \
  "vector_store_v2" \
  "src" \
  "frontend_server.log" \
  "backend_server.log" \
  "run_project.log" \
  "conv_id.txt" \
  ".pytest_cache" \
  ".vs" \
  ".claude" \
  ".code-review-graph" \
  2>&1 | tail -5
```

Expected: many lines of `adding: ...`, ending with exit code 0. No errors.

- [ ] **Step 3: Confirm ZIP was created**

```bash
BASE="/Users/armaan/Library/CloudStorage/OneDrive-TheEraCorporations/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI"
ls -lh "$BASE/archive_backup_2026-05-05.zip"
```

Expected: file exists, size >= 500MB (node_modules compress poorly, so actual size will be large)

---

## Task 2: Verify ZIP integrity

- [ ] **Step 1: Test ZIP integrity**

```bash
BASE="/Users/armaan/Library/CloudStorage/OneDrive-TheEraCorporations/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI"
unzip -t "$BASE/archive_backup_2026-05-05.zip" 2>&1 | tail -5
```

Expected: last line reads `No errors detected in compressed data in archive_backup_2026-05-05.zip.`

- [ ] **Step 2: Spot-check — verify a key file is inside the ZIP**

```bash
BASE="/Users/armaan/Library/CloudStorage/OneDrive-TheEraCorporations/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI"
unzip -l "$BASE/archive_backup_2026-05-05.zip" | grep "Project_AccountingLegalChatbot/backend/main.py" | head -3
```

Expected: one line showing the file path and size (confirms the project code is in the ZIP)

- [ ] **Step 3: Spot-check — verify old session is inside the ZIP**

```bash
BASE="/Users/armaan/Library/CloudStorage/OneDrive-TheEraCorporations/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI"
unzip -l "$BASE/archive_backup_2026-05-05.zip" | grep "25. 21-Mar-2026" | head -3
```

Expected: one or more lines showing files from the March session

**⛔ DO NOT proceed to Task 3 unless both spot-checks return results. If ZIP is empty or corrupted, re-run Task 1.**

---

## Task 3: Delete the archived originals

- [ ] **Step 1: Delete the large code/session directories**

```bash
BASE="/Users/armaan/Library/CloudStorage/OneDrive-TheEraCorporations/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI"
rm -rf \
  "$BASE/Project_AccountingLegalChatbot" \
  "$BASE/25. 21-Mar-2026" \
  "$BASE/desktop" \
  "$BASE/frontend"
echo "Done"
```

Expected: `Done` with no errors

- [ ] **Step 2: Delete remaining stale folders and files**

```bash
BASE="/Users/armaan/Library/CloudStorage/OneDrive-TheEraCorporations/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI"
rm -rf \
  "$BASE/backend" \
  "$BASE/vector_store" \
  "$BASE/vector_store_v2" \
  "$BASE/src" \
  "$BASE/.pytest_cache" \
  "$BASE/.vs" \
  "$BASE/.claude" \
  "$BASE/.code-review-graph"
rm -f \
  "$BASE/frontend_server.log" \
  "$BASE/backend_server.log" \
  "$BASE/run_project.log" \
  "$BASE/conv_id.txt"
echo "Done"
```

Expected: `Done` with no errors

- [ ] **Step 3: Verify the cleanup — check folder size is now small**

```bash
BASE="/Users/armaan/Library/CloudStorage/OneDrive-TheEraCorporations/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI"
du -sh "$BASE"/* 2>/dev/null | sort -hr | head -15
```

Expected: largest items should be the ZIP file, `data_source_finance/`, `data_source_law/`, `Main Branch/`. No `Project_AccountingLegalChatbot`, `25. 21-Mar-2026`, or `desktop` should appear.

- [ ] **Step 4: Verify essential items are still present**

```bash
BASE="/Users/armaan/Library/CloudStorage/OneDrive-TheEraCorporations/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI"
for item in "Main Branch" "data_source_finance" "data_source_law" "PROJECT_JOURNAL.md" ".env" "skills"; do
  [ -e "$BASE/$item" ] && echo "✅ $item" || echo "❌ MISSING: $item"
done
```

Expected: all 6 lines show ✅

---

## Task 4: Update PROJECT_JOURNAL.md and push

- [ ] **Step 1: Append cleanup entry to PROJECT_JOURNAL.md**

Open `~/chatbot_local/PROJECT_JOURNAL.md` and append the following entry to the **Chronological Session Log** section:

```markdown
### Session: 2026-05-05 — Folder Cleanup & Archive

**Goal:** Reduce OneDrive Agentic AI folder from ~6GB to ~850MB by archiving redundant files.

**What was archived (into `archive_backup_2026-05-05.zip`):**
- `Project_AccountingLegalChatbot/` (3.1GB) — canonical copy is in git at `~/chatbot_local`
- `25. 21-Mar-2026/` (1.4GB) — superseded March session
- `desktop/` (576MB) — orphaned node_modules, no source
- `frontend/` (269MB) — stale standalone frontend
- `backend/`, `vector_store/`, `vector_store_v2/`, `src/` — stale root-level duplicates
- Log files, IDE caches, temp files

**What was kept:**
- `Main Branch/`, `data_source_finance/`, `data_source_law/`
- `PROJECT_JOURNAL.md`, `.env`, `skills/`, `brain/`, `Gemini_Sessions/`
- Setup scripts, git infrastructure

**Result:** Folder reduced to ~850MB. ZIP backup at `archive_backup_2026-05-05.zip`.
```

- [ ] **Step 2: Commit and push from `~/chatbot_local`**

```bash
cd ~/chatbot_local
git add PROJECT_JOURNAL.md
git commit -m "docs(journal): 2026-05-05 folder cleanup — archived 5GB+ to ZIP backup

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push origin main
```

Expected: `main -> main` push confirmation

---

## Self-Review Checklist (completed inline)

1. **Spec coverage:** ✅ All 5 spec requirements covered: ZIP creation, verification, deletion, journal update, push
2. **Placeholder scan:** ✅ No TBDs, all commands are exact with expected outputs
3. **Type consistency:** N/A (file operations, no code types)
4. **Safety gate:** ✅ Task 3 explicitly blocked until Task 2 spot-checks pass
5. **Essential files:** ✅ Task 3 Step 4 verifies all 6 essential items survive cleanup
