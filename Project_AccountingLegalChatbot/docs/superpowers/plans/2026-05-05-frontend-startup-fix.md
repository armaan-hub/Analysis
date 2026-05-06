# Frontend Startup Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Get the frontend running reliably at http://localhost:5173, fully connected to the backend at http://localhost:8002 with correct Python venv.

**Architecture:** Four independent issues to fix in order: (1) restart backend with venv Python, (2) install frontend npm deps, (3) fix API URL env config, (4) start frontend and verify E2E. Each task is independently testable. Final E2E test sends a real chat message.

**Tech Stack:** FastAPI/uvicorn (Python 3.11 venv), React 18/Vite 5, Node.js 25, npm 11, ChromaDB 0.5.15 (venv only)

---

## File Map

| File | Action | Reason |
|------|--------|--------|
| `frontend/.env` | **Create** | Sets `VITE_API_BASE_URL=http://localhost:8002` |
| `frontend/src/api-config.ts` | **Read-only** | Verify it reads from `VITE_API_BASE_URL` (no change needed) |
| Backend process | **Restart** | Kill system-Python uvicorn, start with `~/chatbot_venv/bin/python3` |

---

## Task 1: Restart Backend with Correct Python (venv)

**Problem:** Backend PID 86096 runs under `/Library/Frameworks/Python.framework/Versions/3.14/...` which has ChromaDB **1.5.8** (incompatible). Must use `~/chatbot_venv` which has ChromaDB 0.5.15.

**Files:** No code changes — process management only.

- [ ] **Step 1: Kill the current backend process**

```bash
kill 86096
sleep 2
ps aux | grep uvicorn | grep -v grep
```
Expected: no uvicorn processes listed.

- [ ] **Step 2: Verify venv Python has correct ChromaDB**

```bash
~/chatbot_venv/bin/python3 -c "import chromadb; print(chromadb.__version__)"
```
Expected output: `0.5.15`

- [ ] **Step 3: Start backend with venv Python**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/backend
source ~/chatbot_venv/bin/activate
nohup ~/chatbot_venv/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8002 --reload > ~/backend_server.log 2>&1 &
echo "Backend PID: $!"
```

- [ ] **Step 4: Wait for backend to be healthy**

```bash
sleep 5
curl -s http://localhost:8002/health
```
Expected: `{"status":"ok"}`

If not ok after 5s, wait 10 more seconds and retry. If still not ok, check `~/backend_server.log` for errors.

- [ ] **Step 5: Verify ChromaDB loaded correctly (no import errors in log)**

```bash
grep -i "chromadb\|import error\|modulenotfound" ~/backend_server.log | head -10
```
Expected: no `ModuleNotFoundError` for chromadb.

---

## Task 2: Install Frontend Dependencies

**Problem:** `~/chatbot_local/Project_AccountingLegalChatbot/frontend/node_modules` is empty — `npm install` was never run in the fresh clone.

**Files:** `frontend/node_modules/` (populated by npm), `frontend/package-lock.json` (unchanged).

- [ ] **Step 1: Navigate to frontend and run npm install**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/frontend
npm install
```
Expected: packages installed, no `ERR!` lines. This may take 1-2 minutes.

- [ ] **Step 2: Verify node_modules populated**

```bash
ls ~/chatbot_local/Project_AccountingLegalChatbot/frontend/node_modules | wc -l
```
Expected: 300+ entries.

- [ ] **Step 3: Verify vite is available**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/frontend
npx vite --version
```
Expected: `vite/X.X.X ...` (any version without error)

---

## Task 3: Fix API URL Configuration

**Problem:** `api-config.ts` defaults to `localhost:8001`. `.env.example` says `localhost:8000`. Backend is at `localhost:8002`. No `.env` file exists.

**Files:**
- Create: `frontend/.env`
- Read: `frontend/src/api-config.ts` (verify — no change needed)

- [ ] **Step 1: Verify api-config.ts reads from env var**

```bash
cat ~/chatbot_local/Project_AccountingLegalChatbot/frontend/src/api-config.ts
```
Expected to see: `import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'`
This confirms the `.env` file will override the default — no code change needed.

- [ ] **Step 2: Create frontend/.env with correct backend URL**

```bash
cat > ~/chatbot_local/Project_AccountingLegalChatbot/frontend/.env << 'EOF'
VITE_API_BASE_URL=http://localhost:8002
EOF
```

- [ ] **Step 3: Verify the file was created correctly**

```bash
cat ~/chatbot_local/Project_AccountingLegalChatbot/frontend/.env
```
Expected:
```
VITE_API_BASE_URL=http://localhost:8002
```

- [ ] **Step 4: Verify .env is git-ignored (must NOT be committed)**

```bash
cat ~/chatbot_local/Project_AccountingLegalChatbot/frontend/.gitignore 2>/dev/null | grep ".env" || cat ~/chatbot_local/.gitignore 2>/dev/null | grep ".env"
```
Expected: `.env` appears in gitignore. If NOT found, add it:
```bash
echo ".env" >> ~/chatbot_local/Project_AccountingLegalChatbot/frontend/.gitignore
```

---

## Task 4: Start Frontend and Verify It Loads

**Problem:** Frontend dev server was not started. `vite.config.ts` has `strictPort: true` so it will fail (not silently bump) if port 5173 is in use.

**Files:** No code changes — process management only.

- [ ] **Step 1: Check port 5173 is free**

```bash
lsof -i :5173 | grep LISTEN
```
Expected: no output. If a process is listed, kill it with `kill <PID>`.

- [ ] **Step 2: Start frontend dev server as background process**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot/frontend
nohup npm run dev > ~/frontend_server.log 2>&1 &
echo "Frontend PID: $!"
```

- [ ] **Step 3: Wait and verify it started**

```bash
sleep 8
curl -s -o /dev/null -w "%{http_code}" http://localhost:5173
```
Expected: `200`

If not 200, check logs:
```bash
tail -20 ~/frontend_server.log
```
Common failure: port in use (kill the conflicting process), or npm install failed (re-run Task 2).

- [ ] **Step 4: Verify the app HTML is served**

```bash
curl -s http://localhost:5173 | grep -i "<title>"
```
Expected: `<title>` tag present (any content).

---

## Task 5: E2E Verification — Chat with E-Invoicing Query

**Problem:** Even with frontend running, we need to verify the full stack: frontend → backend → RAG → LLM → response.

**Test query:** `"Explain me E-Invoicing and provide company services provider link"`

**Files:** No changes — verification only.

- [ ] **Step 1: Verify backend health**

```bash
curl -s http://localhost:8002/health
```
Expected: `{"status":"ok"}`

- [ ] **Step 2: Send E-Invoicing chat query directly to backend API**

```bash
curl -s -X POST http://localhost:8002/api/chat/send \
  -H "Content-Type: application/json" \
  -d '{"message": "Explain me E-Invoicing and provide company services provider link", "mode": "fast"}' \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
resp = data.get('response', data.get('content', str(data)))
print('=== RESPONSE (first 500 chars) ===')
print(resp[:500])
sources = data.get('sources', [])
print(f'=== SOURCES ({len(sources)} total) ===')
for s in sources[:5]:
    print(f'  - {s.get(\"source\", s.get(\"title\", \"?\"))}: score={s.get(\"score\",\"?\"):.3f}')
"
```
Expected: Response mentions e-invoicing/Peppol/FTA, 5+ sources, scores > 0.3.

- [ ] **Step 3: Test streaming response (SSE)**

```bash
curl -s -N -X POST http://localhost:8002/api/chat/send \
  -H "Content-Type: application/json" \
  -d '{"message": "What is UAE VAT rate?", "mode": "fast", "stream": true}' \
  --max-time 30 | head -20
```
Expected: SSE `data: ` lines streaming in.

- [ ] **Step 4: Verify frontend connects to backend (no CORS errors)**

```bash
curl -s -X OPTIONS http://localhost:8002/api/chat/send \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: POST" \
  -v 2>&1 | grep -i "access-control"
```
Expected: `Access-Control-Allow-Origin: *` or `Access-Control-Allow-Origin: http://localhost:5173`

- [ ] **Step 5: Record final status and commit .env.example update**

```bash
# Update .env.example to document the correct port
sed -i '' 's|VITE_API_BASE_URL=http://localhost:8000|VITE_API_BASE_URL=http://localhost:8002|' \
  ~/chatbot_local/Project_AccountingLegalChatbot/frontend/.env.example

cat ~/chatbot_local/Project_AccountingLegalChatbot/frontend/.env.example | grep VITE_API
```
Expected: `VITE_API_BASE_URL=http://localhost:8002`

- [ ] **Step 6: Commit the .env.example fix**

```bash
cd ~/chatbot_local
git add Project_AccountingLegalChatbot/frontend/.env.example
git commit -m "fix(frontend): correct VITE_API_BASE_URL default port to 8002

.env.example was documenting localhost:8000, api-config.ts defaulted
to localhost:8001, but backend runs on 8002. Align .env.example.
.env itself is gitignored and must be created locally.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push origin main
```

---

## Task 6: Make Startup Reliable (macOS Launch Script)

**Problem:** Frontend keeps stopping because there's no persistent startup mechanism on macOS. The Windows `run_project.ps1` doesn't work on macOS.

**Files:**
- Create: `~/chatbot_local/Project_AccountingLegalChatbot/run_project.sh`

- [ ] **Step 1: Create macOS startup script**

```bash
cat > ~/chatbot_local/Project_AccountingLegalChatbot/run_project.sh << 'SCRIPT'
#!/bin/bash
# macOS dev launcher — starts backend (port 8002) + frontend (port 5173)
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON=~/chatbot_venv/bin/python3

echo "=== Accounting & Legal AI Chatbot ==="
echo "Project: $PROJECT_DIR"
echo ""

# Kill any existing processes on our ports
lsof -ti :8002 | xargs kill -9 2>/dev/null && echo "Killed existing backend on 8002" || true
lsof -ti :5173 | xargs kill -9 2>/dev/null && echo "Killed existing frontend on 5173" || true
sleep 1

# Start backend
echo "Starting backend (port 8002)..."
cd "$PROJECT_DIR/backend"
nohup $VENV_PYTHON -m uvicorn main:app --host 0.0.0.0 --port 8002 --reload \
  > ~/backend_server.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Start frontend
echo "Starting frontend (port 5173)..."
cd "$PROJECT_DIR/frontend"
nohup npm run dev > ~/frontend_server.log 2>&1 &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

# Wait for services to be ready
echo ""
echo "Waiting for services..."
sleep 6

BACKEND_OK=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8002/health 2>/dev/null)
FRONTEND_OK=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5173 2>/dev/null)

echo ""
echo "=== Status ==="
[ "$BACKEND_OK" = "200" ] && echo "✅ Backend:  http://localhost:8002" || echo "❌ Backend:  not responding (check ~/backend_server.log)"
[ "$FRONTEND_OK" = "200" ] && echo "✅ Frontend: http://localhost:5173" || echo "❌ Frontend: not responding (check ~/frontend_server.log)"
echo "📖 API Docs: http://localhost:8002/docs"
SCRIPT
chmod +x ~/chatbot_local/Project_AccountingLegalChatbot/run_project.sh
echo "Created run_project.sh"
```

- [ ] **Step 2: Test the script**

```bash
~/chatbot_local/Project_AccountingLegalChatbot/run_project.sh
```
Expected output ends with both ✅ lines.

- [ ] **Step 3: Commit the startup script**

```bash
cd ~/chatbot_local
git add Project_AccountingLegalChatbot/run_project.sh
git commit -m "feat(scripts): add macOS run_project.sh launcher

Starts backend (venv Python, port 8002) + frontend (port 5173).
Kills any stale processes on those ports before starting.
Prints status check after 6s startup delay.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push origin main
```

---

## Self-Review Checklist

| Requirement | Task | Status |
|-------------|------|--------|
| Backend uses venv Python (ChromaDB 0.5.15) | Task 1 | ✅ covered |
| node_modules installed | Task 2 | ✅ covered |
| API URL points to port 8002 | Task 3 | ✅ covered |
| Frontend starts at 5173 | Task 4 | ✅ covered |
| E-Invoicing query tested | Task 5, Step 2 | ✅ covered |
| Streaming tested | Task 5, Step 3 | ✅ covered |
| CORS verified | Task 5, Step 4 | ✅ covered |
| .env.example corrected and pushed | Task 5, Step 5-6 | ✅ covered |
| macOS startup script | Task 6 | ✅ covered |
| No placeholder steps | — | ✅ verified |
