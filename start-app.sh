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
kill_port()    { lsof -ti tcp:"$1" 2>/dev/null | xargs kill -9 2>/dev/null; true; }

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
  CF_BACKEND_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG_DIR/cf-backend.log" 2>/dev/null | head -1)
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
  CF_FRONTEND_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG_DIR/cf-frontend.log" 2>/dev/null | head -1)
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
  kill $BACKEND_PID $FRONTEND_PID $CF_BACKEND_PID $CF_FRONTEND_PID 2>/dev/null || true
  kill_port 8002; kill_port 5173
  pkill -f "cloudflared tunnel" 2>/dev/null || true
  echo "  ✓ Stopped."
}
trap cleanup INT TERM

# Keep script alive
wait
