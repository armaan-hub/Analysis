# Backend/Frontend Startup System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide reliable, repeatable startup for both backend and frontend services with error handling and health verification.

**Architecture:** Three-layer system with individual service startup scripts (validation + launch), npm scripts for cross-platform compatibility, and a unified orchestrator that starts both services in parallel, runs health checks, and handles graceful shutdown.

**Tech Stack:** Bash shell scripts, npm, uvicorn (backend), vite (frontend), curl (health checks), lsof (port checking)

---

## File Structure

### Scripts to Create
- `backend/scripts/start.sh` — Backend startup with port/venv/env validation
- `frontend/scripts/start.sh` — Frontend startup with port/node_modules validation
- `scripts/health-check.sh` — Health endpoint verification utility
- `start-dev.sh` — Root-level unified orchestrator

### Files to Modify
- `backend/package.json` — Add "start" npm script
- `frontend/package.json` — Add "start" npm script

### Documentation to Create
- `README_STARTUP.md` — Usage guide and troubleshooting

---

## Task 1: Create Backend Startup Script

**Files:**
- Create: `backend/scripts/start.sh`

- [ ] **Step 1:** `mkdir -p backend/scripts`

- [ ] **Step 2:** Create backend/scripts/start.sh with complete implementation

- [ ] **Step 3:** `chmod +x backend/scripts/start.sh`

- [ ] **Step 4:** Test: `bash backend/scripts/start.sh` (expect venv error)

- [ ] **Step 5:** Commit

---

## Task 2: Create Frontend Startup Script

**Files:**
- Create: `frontend/scripts/start.sh`

- [ ] **Step 1:** `mkdir -p frontend/scripts`

- [ ] **Step 2:** Create frontend/scripts/start.sh with complete implementation

- [ ] **Step 3:** `chmod +x frontend/scripts/start.sh`

- [ ] **Step 4:** Test: `bash frontend/scripts/start.sh` (expect node_modules error)

- [ ] **Step 5:** Commit

---

## Task 3: Create Health Check Script

**Files:**
- Create: `scripts/health-check.sh`

- [ ] **Step 1:** `mkdir -p scripts`

- [ ] **Step 2:** Create scripts/health-check.sh

- [ ] **Step 3:** `chmod +x scripts/health-check.sh`

- [ ] **Step 4:** Verify: `ls -la scripts/health-check.sh`

- [ ] **Step 5:** Commit

---

## Task 4: Create Unified Start Script

**Files:**
- Create: `start-dev.sh`

- [ ] **Step 1:** Create start-dev.sh with orchestration logic

- [ ] **Step 2:** `chmod +x start-dev.sh`

- [ ] **Step 3:** Verify: `ls -la start-dev.sh`

- [ ] **Step 4:** Test: Can execute without errors

- [ ] **Step 5:** Commit

---

## Task 5: Update Backend package.json

**Files:**
- Modify: `backend/package.json`

- [ ] **Step 1:** Add `"start": "bash scripts/start.sh",` to scripts section

- [ ] **Step 2:** Validate JSON: `node -e "require('./package.json'); console.log('OK')"`

- [ ] **Step 3:** Verify change: `grep '"start":' backend/package.json`

- [ ] **Step 4:** Commit

---

## Task 6: Update Frontend package.json

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1:** Add `"start": "bash scripts/start.sh",` to scripts section

- [ ] **Step 2:** Validate JSON: `node -e "require('./package.json'); console.log('OK')"`

- [ ] **Step 3:** Verify change: `grep '"start":' frontend/package.json`

- [ ] **Step 4:** Commit

---

## Task 7: Create Startup Documentation

**Files:**
- Create: `README_STARTUP.md`

- [ ] **Step 1:** Create comprehensive startup guide with all troubleshooting

- [ ] **Step 2:** Verify file: `ls -la README_STARTUP.md && head -20 README_STARTUP.md`

- [ ] **Step 3:** Commit

---

## Task 8: Final Verification and Push

**Files:**
- All scripts and docs

- [ ] **Step 1:** Verify all scripts: `ls -la backend/scripts/start.sh frontend/scripts/start.sh scripts/health-check.sh start-dev.sh`

- [ ] **Step 2:** Check all are executable

- [ ] **Step 3:** View git log: `git log --oneline -10`

- [ ] **Step 4:** Push: `git push origin main`

---

## Complete Task Descriptions

See implementation steps in the main session execution.

