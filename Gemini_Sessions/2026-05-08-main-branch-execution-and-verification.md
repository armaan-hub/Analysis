# Main Branch Execution and Verification Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Start the application from the Main Branch, verify all core components are functional, and confirm that all recent fixes (portable paths, database initialization) are active.

**Architecture:** Full-stack execution (FastAPI backend + React frontend) with verified SQLite database and hybrid RAG system.

**Tech Stack:** Python 3.11+, FastAPI, React, TypeScript, Vite, ChromaDB.

---

### Task 1: Environment Setup

**Files:**
- Modify: `Main Branch/Project_AccountingLegalChatbot/backend/.env` (from `.env.example`)

- [ ] **Step 1: Create .env file**
Run: `cp "Main Branch/Project_AccountingLegalChatbot/backend/.env.example" "Main Branch/Project_AccountingLegalChatbot/backend/.env"`

- [ ] **Step 2: Add API Keys**
Update `NVIDIA_API_KEY` and other necessary keys in the new `.env` file.

- [ ] **Step 3: Verify config loads correctly**
Run: `cd "Main Branch/Project_AccountingLegalChatbot/backend" && python3 -c "from config import settings; print('Config loaded successfully')"`
Expected: `Config loaded successfully`

---

### Task 2: Backend Initialization and Startup

**Files:**
- Verify: `Main Branch/Project_AccountingLegalChatbot/backend/data/chatbot.db` (will be created)

- [ ] **Step 1: Start Backend**
Run: `cd "Main Branch/Project_AccountingLegalChatbot/backend" && python3 main.py`
Expected: Server starts on http://localhost:8001. Database tables are automatically created.

- [ ] **Step 2: Verify health endpoint**
Run: `curl http://localhost:8001/health`
Expected: `{"status":"ok"}`

- [ ] **Step 3: Verify database tables**
Run: `python3 -c "import sqlite3; conn = sqlite3.connect('Main Branch/Project_AccountingLegalChatbot/backend/data/chatbot.db'); cursor = conn.cursor(); cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table'\"); print(len(cursor.fetchall()))"`
Expected: Result should be > 0 (22 tables expected).

---

### Task 3: Frontend Startup and Interaction

**Files:**
- Verify: `Main Branch/Project_AccountingLegalChatbot/frontend/`

- [ ] **Step 1: Install frontend dependencies**
Run: `cd "Main Branch/Project_AccountingLegalChatbot/frontend" && npm install`
Expected: Success.

- [ ] **Step 2: Start frontend dev server**
Run: `cd "Main Branch/Project_AccountingLegalChatbot/frontend" && npm run dev`
Expected: Server starts on http://localhost:5173.

- [ ] **Step 3: Verify UI access**
Open http://localhost:5173 in browser.
Expected: Chat interface loads.

---

### Task 4: Final Validation

- [ ] **Step 1: Run all tests in Main Branch**
Run: `cd "Main Branch/Project_AccountingLegalChatbot/backend" && python3 -m pytest tests/`
Expected: All tests pass (640+ passed).

- [ ] **Step 2: Verify Chat History Viewer**
Run: `cd "Main Branch/Project_AccountingLegalChatbot" && python3 chat_history_viewer.py --stats`
Expected: Displays database statistics.
