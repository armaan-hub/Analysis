# Folder Cleanup Design
**Date:** 2026-05-05  
**Topic:** Archive unnecessary files from `35. 11-Apr-2026 Agentic AI` OneDrive folder  
**Status:** Approved

---

## Problem

The `35. 11-Apr-2026 Agentic AI` folder has grown to ~6GB containing many redundant or stale items:
- A 3.1GB duplicate of the project code (canonical source is `~/chatbot_local` in git)
- 1.4GB of old March 2026 session files
- 576MB of orphaned `node_modules` in `desktop/` (no source code)
- 269MB stale standalone `frontend/` with `node_modules`
- Stale `backend/`, `vector_store*/`, `src/` at root (duplicates of what's in `Main Branch/`)
- Runtime log files, temp files, IDE/tool caches

## Approach

**Single ZIP backup → delete originals**

Create `archive_backup_2026-05-05.zip` in the same folder containing all unnecessary items, verify integrity, then delete the originals.

## Archive List (goes into ZIP)

| Item | Size | Reason |
|------|------|---------|
| `Project_AccountingLegalChatbot/` | 3.1GB | Duplicate — canonical code is in git at `~/chatbot_local` |
| `25. 21-Mar-2026/` | 1.4GB | Old March 2026 session, superseded |
| `desktop/` | 576MB | Only contains `node_modules`, no source code |
| `frontend/` | 269MB | Stale standalone frontend + orphaned `node_modules` |
| `backend/` | 3.7MB | Stale root-level backend (real one is in `Main Branch/`) |
| `vector_store/` | 648KB | Stale root-level vector store |
| `vector_store_v2/` | 648KB | Stale root-level vector store v2 |
| `src/` | ~4KB | Root-level hooks folder, orphaned |
| `frontend_server.log` | 32KB | Runtime log |
| `backend_server.log` | 28KB | Runtime log |
| `run_project.log` | 8KB | Runtime log |
| `conv_id.txt` | 4KB | Temp file |
| `.pytest_cache/` | — | Regeneratable pytest cache |
| `.vs/` | — | Visual Studio IDE cache |
| `.claude/` | — | AI session state cache |
| `.code-review-graph/` | — | Code review tool cache |

## Keep List

| Item | Reason |
|------|---------|
| `Main Branch/` | Working project snapshot with all source code |
| `data_source_finance/` | RAG finance PDF documents — irreplaceable training data |
| `data_source_law/` | RAG law PDF documents — irreplaceable training data |
| `PROJECT_JOURNAL.md` | Living journal (Rule 1 + 2 apply) |
| `.env` | API keys — sensitive, gitignored |
| `skills/` | Custom Copilot skills |
| `Gemini_Sessions/` | AI session logs — reference value |
| `brain/` | Project planning files |
| `Testing data/` | Test data |
| `Project_SuperpowersIntegration/` | Active small project |
| `docs/` | This spec and future specs |
| `auto-commit.ps1`, `setup-auto-push.ps1`, `setup_python_env.*` | Setup scripts |
| `.git/`, `.gitignore`, `.github/`, `.code-review-graphignore` | Git infrastructure |
| `archive_backup_2026-05-05.zip` | The backup we create |

## Implementation Steps

1. Create the ZIP file: `zip -r archive_backup_2026-05-05.zip <all archive items>`
2. Verify ZIP integrity: `unzip -t archive_backup_2026-05-05.zip`
3. Delete the archived originals
4. Update `PROJECT_JOURNAL.md` with cleanup entry
5. Commit and push to git (Rule 2)

## Expected Outcome

- Folder reduced from ~6GB to ~750MB–850MB
- Single `archive_backup_2026-05-05.zip` file (~2–3GB compressed) as safety net
- Only essential, active files remain at root level
- Changes committed and pushed to `armaan-hub/Analysis`

## Risks

- ZIP creation on OneDrive may be slow (large files) — use native `zip` command
- `.env` contains sensitive API keys — must stay excluded from git (already gitignored)
- `data_source_*` folders are NOT backed up in git — they are irreplaceable, do NOT archive them
