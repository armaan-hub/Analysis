# Startup Script & UX Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a single `start-app.sh` that boots backend + frontend + Cloudflare tunnels, auto-patches `frontend/.env`, and adds "Select All" + hint text to the conversation list UI.

**Architecture:** Shell script handles process orchestration and URL extraction; React component gets a "Select All" button and instructional hint text inside the existing selection-mode toolbar.

**Tech Stack:** Bash, cloudflared (CLI), Vite (React), uvicorn (FastAPI), SQLite

---

## Task 1: Create `~/chatbot_local/start-app.sh`

**Files:**
- Create: `~/chatbot_local/start-app.sh`

- [ ] **Step 1: Create the script**

```bash
#!/usr/bin/env bash
set -e

BACKEND_DIR="$HOME/chatbot_local/Project_AccountingLegalChatbot/backend"
FRONTEND_DIR="$HOME/chatbot_local/Project_AccountingLegalChatbot/frontend"
VENV="$HOME/chatbot_venv/bin/activate"
ENV_FILE="$FRONTEND_DIR/.env"
LOG_DIR="$HOME/chatbot_local/logs"

mkdir -p "$LOG_DIR"

# ── Helpers ──────────────────────────────────────────────────────────────────
port_running() { lsof -ti tcp:"$1" &>/dev/null; }
kill_port()    { lsof -ti tcp:"$1" | xargs kill -9 2>/dev/null; true; }

echo "╔══════════════════════════════════════════════════╗"
echo "║  Accounting & Legal AI Chatbot — Full Startup    ║"
echo "╚══════════════════════════════════════════════════╝"

# ── 1. Kill stale processes ───────────────────────────────────────────────────
echo ""
echo "▶ Stopping any stale processes on :8002 and :5173…"
kill_port 8002
kill_port 5173
pkill -f "cloudflared tunnel" 2>/dev/null || true
sleep 1

# ── 2. Backend ────────────────────────────────────────────────────────────────
echo ""
echo "▶ Starting backend on :8002…"
source "$VENV"
cd "$BACKEND_DIR"
uvicorn main:app --host localhost --port 8002 \
  > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"

# Wait until backend health check passes
for i in $(seq 1 30); do
  if curl -sf http://localhost:8002/health &>/dev/null; then
    echo "  ✓ Backend healthy"
    break
  fi
  sleep 1
  if [ $i -eq 30 ]; then echo "  ✗ Backend failed to start. Check $LOG_DIR/backend.log"; exit 1; fi
done

# ── 3. Cloudflare tunnel for backend ─────────────────────────────────────────
echo ""
echo "▶ Starting Cloudflare tunnel for backend…"
cloudflared tunnel --url http://localhost:8002 \
  > "$LOG_DIR/cf-backend.log" 2>&1 &
CF_BACKEND_PID=$!

# Extract backend tunnel URL
CF_BACKEND_URL=""
for i in $(seq 1 30); do
  CF_BACKEND_URL=$(grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG_DIR/cf-backend.log" 2>/dev/null | head -1)
  [ -n "$CF_BACKEND_URL" ] && break
  sleep 1
done

if [ -z "$CF_BACKEND_URL" ]; then
  echo "  ✗ Could not detect backend Cloudflare URL. Check $LOG_DIR/cf-backend.log"
  exit 1
fi
echo "  ✓ Backend tunnel: $CF_BACKEND_URL"

# ── 4. Patch frontend/.env with new backend URL ───────────────────────────────
echo ""
echo "▶ Updating frontend/.env → VITE_API_BASE_URL=$CF_BACKEND_URL"
if grep -q '^VITE_API_BASE_URL=' "$ENV_FILE"; then
  sed -i.bak "s|^VITE_API_BASE_URL=.*|VITE_API_BASE_URL=$CF_BACKEND_URL|" "$ENV_FILE"
else
  echo "VITE_API_BASE_URL=$CF_BACKEND_URL" >> "$ENV_FILE"
fi
echo "  ✓ .env updated"

# ── 5. Frontend ───────────────────────────────────────────────────────────────
echo ""
echo "▶ Starting frontend on :5173…"
cd "$FRONTEND_DIR"
npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID"

# Wait until Vite is ready
for i in $(seq 1 30); do
  if curl -sf http://localhost:5173 &>/dev/null; then
    echo "  ✓ Frontend ready"
    break
  fi
  sleep 1
  if [ $i -eq 30 ]; then echo "  ✗ Frontend failed to start. Check $LOG_DIR/frontend.log"; exit 1; fi
done

# ── 6. Cloudflare tunnel for frontend ────────────────────────────────────────
echo ""
echo "▶ Starting Cloudflare tunnel for frontend…"
cloudflared tunnel --url http://localhost:5173 \
  > "$LOG_DIR/cf-frontend.log" 2>&1 &
CF_FRONTEND_PID=$!

CF_FRONTEND_URL=""
for i in $(seq 1 30); do
  CF_FRONTEND_URL=$(grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG_DIR/cf-frontend.log" 2>/dev/null | head -1)
  [ -n "$CF_FRONTEND_URL" ] && break
  sleep 1
done

if [ -z "$CF_FRONTEND_URL" ]; then
  echo "  ✗ Could not detect frontend Cloudflare URL. Check $LOG_DIR/cf-frontend.log"
  exit 1
fi
echo "  ✓ Frontend tunnel: $CF_FRONTEND_URL"

# ── 7. Summary ────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  ✅  All services started successfully           ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  LOCAL"
echo "    Backend  : http://localhost:8002"
echo "    Frontend : http://localhost:5173"
echo ""
echo "  INTERNET (share these links)"
echo "    Backend  : $CF_BACKEND_URL"
echo "    Frontend : $CF_FRONTEND_URL"
echo ""
echo "  PIDs: backend=$BACKEND_PID  frontend=$FRONTEND_PID"
echo "        cf-backend=$CF_BACKEND_PID  cf-frontend=$CF_FRONTEND_PID"
echo ""
echo "  Press Ctrl+C to stop all services"
echo ""

# ── 8. Trap Ctrl+C to clean up all child processes ───────────────────────────
cleanup() {
  echo ""
  echo "▶ Shutting down all services…"
  kill $BACKEND_PID $FRONTEND_PID $CF_BACKEND_PID $CF_FRONTEND_PID 2>/dev/null
  kill_port 8002; kill_port 5173
  pkill -f "cloudflared tunnel" 2>/dev/null || true
  echo "  ✓ Stopped."
}
trap cleanup INT TERM

# Keep script alive
wait
```

- [ ] **Step 2: Make executable and test**

```bash
chmod +x ~/chatbot_local/start-app.sh
~/chatbot_local/start-app.sh
```

Expected: All four URLs printed; no errors.

- [ ] **Step 3: Commit**

```bash
cd ~/chatbot_local
git add start-app.sh
git commit -m "feat: add start-app.sh — one command starts backend + frontend + Cloudflare tunnels

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: UX — Select All button + hint text in HomePage

**Files:**
- Modify: `~/chatbot_local/Project_AccountingLegalChatbot/frontend/src/pages/HomePage.tsx`

- [ ] **Step 1: Add "Select All" handler (after line ~95 `exitSelectionMode`)**

```typescript
const handleSelectAll = () => {
  setSelectedIds(new Set(filtered.map(nb => nb.id)));
};
```

- [ ] **Step 2: Add hint text and "Select All" button to selection toolbar**

In the toolbar section, after the `Select` / `Cancel` button and before `{selectionMode && selectedIds.size > 0 && ...}`, add:

```tsx
{/* Selection mode hint */}
{selectionMode && (
  <span style={{ fontSize: '12px', color: 'var(--s-text-2)', marginLeft: '4px' }}>
    {selectedIds.size === 0
      ? 'Tap notebooks to select them'
      : `${selectedIds.size} selected`}
  </span>
)}

{/* Select All button */}
{selectionMode && (
  <button
    type="button"
    style={toolbarBtnStyle}
    onClick={handleSelectAll}
  >
    Select All
  </button>
)}
```

- [ ] **Step 3: Verify UI in browser**

Open http://localhost:5173 → click "Select" → confirm:
- Hint text says "Tap notebooks to select them"
- "Select All" button is visible
- Clicking "Select All" selects every notebook
- Counter updates as you click individual cards
- "Delete (N)" button appears and modal works

- [ ] **Step 4: Commit**

```bash
cd ~/chatbot_local/Project_AccountingLegalChatbot
git add frontend/src/pages/HomePage.tsx
git commit -m "feat: add Select All button and hint text to conversation list

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: Sync to Main Branch and push to GitHub

**Files:**
- Modify: `~/Library/CloudStorage/.../Main Branch/Project_AccountingLegalChatbot/frontend/src/pages/HomePage.tsx`

- [ ] **Step 1: Sync start-app.sh to OneDrive root**

```bash
cp ~/chatbot_local/start-app.sh \
   ~/Library/CloudStorage/OneDrive-TheEraCorporations/Study/Armaan/AI\ Class/Data\ Science\ Class/35.\ 11-Apr-2026\ Agentic\ AI/start-app.sh
```

- [ ] **Step 2: Sync HomePage.tsx**

```bash
cp ~/chatbot_local/Project_AccountingLegalChatbot/frontend/src/pages/HomePage.tsx \
   ~/Library/CloudStorage/OneDrive-TheEraCorporations/Study/Armaan/AI\ Class/Data\ Science\ Class/35.\ 11-Apr-2026\ Agentic\ AI/Main\ Branch/Project_AccountingLegalChatbot/frontend/src/pages/HomePage.tsx
```

- [ ] **Step 3: Push to GitHub**

```bash
cd ~/Library/CloudStorage/OneDrive-TheEraCorporations/Study/Armaan/AI\ Class/Data\ Science\ Class/35.\ 11-Apr-2026\ Agentic\ AI/Main\ Branch
git add Project_AccountingLegalChatbot/frontend/src/pages/HomePage.tsx
git add ../start-app.sh 2>/dev/null || true
git commit -m "feat: startup script + select-all UX improvements

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push origin main
```

- [ ] **Step 4: Update PROJECT_JOURNAL.md**

Append entry to the Chronological Session Log:

```markdown
### Session — 2026-05-06

**Goal:** Startup script + UX cleanup

**What was done:**
- Created `start-app.sh` — one command starts backend (uvicorn), frontend (Vite), and two Cloudflare tunnels; auto-patches `frontend/.env` with new backend URL; prints all 4 URLs on success; Ctrl+C cleanly stops everything
- Deleted 281 test conversations (t, t2, t3, t4) directly from SQLite
- Added "Select All" button and "Tap notebooks to select" hint text to HomePage
- Cloudflare quick tunnels confirmed working (free, no account needed, runs on macOS/Linux/Windows)
```
