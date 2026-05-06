# Git Hooks & Workflow Verification — Google Drive Migration

**Date:** 2026-05-06  
**Trigger:** Repository folder moved from OneDrive to Google Drive  
**Goal:** Verify all git hooks, auto-push rules, and startup scripts work correctly in the new location.

---

## Problem

The project folder moved from:
```
~/Library/CloudStorage/OneDrive-TheEraCorporations/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI/
```
to:
```
~/Library/CloudStorage/GoogleDrive-armaanmishra86@gmail.com/My Drive/Study/Armaan/AI Class/Data Science Class/35. 11-Apr-2026 Agentic AI/
```

Git hooks and scripts that hardcode the old path will break silently.

---

## Components to Verify

### 1. Git Hooks
- **pre-commit** (`.git/hooks/pre-commit`): Detects major changes (backend, frontend, deps, config). Uses only relative git commands — should be path-independent.
- **post-commit** (`.git/hooks/post-commit`): Auto-pushes on "major" keyword commits. Uses `git push origin "$BRANCH"` — path-independent.

### 2. Git Aliases (`auto-commit.ps1`)
- Aliases `major`/`minor` call `powershell -NoProfile -Command ".\\auto-commit.ps1 @args"`.
- **Risk:** `powershell` command is Windows-only. On macOS it must be `pwsh`. Needs verification.

### 3. Startup Scripts (`start-dev.sh`, `start-app.sh`)
- Previously patched to use `~/chatbot_local/Project_AccountingLegalChatbot/`. Should be path-independent. Needs confirmation.

### 4. Hardcoded OneDrive Paths
- Any scripts, configs, or docs referencing `OneDrive-TheEraCorporations` will point to wrong/missing locations.

### 5. Stored Workflow Rules
- Memory Rule 3 contains the old OneDrive path for the Main Branch folder. Must be updated.

---

## Implementation Plan

**Phase 1 — Audit:** `grep -r "OneDrive" .` across all scripts, hooks, and configs.  
**Phase 2 — Fix:** Replace OneDrive refs with Google Drive path or relative paths.  
**Phase 3 — Live Test:** Commit a test file with a "fix:" prefix, confirm hook output.  
**Phase 4 — Script Check:** Confirm `start-dev.sh` uses `~/chatbot_local/` (not hardcoded).  
**Phase 5 — Memory Update:** Update Rule 3 to reference the new Google Drive path.

---

## Success Criteria
- No OneDrive path references remain in any script or config
- `pre-commit` hook prints "Running pre-commit checks..." on commit
- `post-commit` hook auto-pushes successfully on a "fix:" commit  
- `start-dev.sh` resolves paths correctly
- Stored Rule 3 reflects the Google Drive path
