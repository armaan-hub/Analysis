#!/usr/bin/env bash
set -e

# ── Config ────────────────────────────────────────────────────────────────────
BACKEND_DIR="$HOME/chatbot_local/Project_AccountingLegalChatbot/backend"
FRONTEND_DIR="$HOME/chatbot_local/Project_AccountingLegalChatbot/frontend"
VENV="$HOME/chatbot_venv/bin/activate"
ENV_FILE="$FRONTEND_DIR/.env"
LOG_DIR="$HOME/chatbot_local/logs"
CF_RETRIES=3                       # attempts per tunnel before giving up
CF_WAIT_SECS=45                    # seconds to wait per attempt for URL
STARTUP_TIMEOUT=${STARTUP_TIMEOUT:-60}   # seconds to wait for service ready

mkdir -p "$LOG_DIR"

# ── Helpers ───────────────────────────────────────────────────────────────────
kill_port() {
  local pids
  pids=$(lsof -ti tcp:"$1" 2>/dev/null)
  # || true prevents set -e exit when port is already free (pids is empty)
  [ -n "$pids" ] && echo "$pids" | xargs kill -9 2>/dev/null || true
}

# ── Cleanup — registered FIRST so any exit (set -e, Ctrl+C, crash) cleans up ─
BACKEND_PID="" FRONTEND_PID="" CF_BACKEND_PID="" CF_FRONTEND_PID=""
cleanup() {
  echo ""
  echo "▶ Shutting down all services…"
  for pid in "$BACKEND_PID" "$FRONTEND_PID" "$CF_BACKEND_PID" "$CF_FRONTEND_PID"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
  kill_port 8002; kill_port 5173
  echo "  ✓ Stopped."
}
trap cleanup INT TERM EXIT   # EXIT covers set -e exits and crashes too

# ── CF tunnel helper: retries up to CF_RETRIES times, non-fatal on failure ────
# Sets CF_URL (tunnel URL or "") and CF_PID (cloudflared PID or "")
start_cf_tunnel() {
  local name="$1" local_url="$2" log_file="$3"
  local attempt url pid i

  for attempt in $(seq 1 "$CF_RETRIES"); do
    [ "$attempt" -gt 1 ] && echo "  ↻ Retry $attempt/$CF_RETRIES for $name tunnel…"
    > "$log_file"   # truncate log before each attempt

    cloudflared tunnel --url "$local_url" >> "$log_file" 2>&1 &
    pid=$!
    url=""

    for i in $(seq 1 "$CF_WAIT_SECS"); do
      url=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$log_file" 2>/dev/null | head -1)
      [ -n "$url" ] && break
      if ! kill -0 "$pid" 2>/dev/null; then
        echo "  ✗ cloudflared ($name) exited early. $(tail -1 "$log_file")"
        break
      fi
      sleep 1
    done

    if [ -n "$url" ]; then
      CF_URL="$url"; CF_PID="$pid"
      return 0
    fi

    kill "$pid" 2>/dev/null || true
    sleep 2
  done

  CF_URL=""; CF_PID=""
  echo "  ⚠ Could not get $name tunnel URL after $CF_RETRIES attempts."
  echo "    Check $log_file for details. Services still running locally."
  return 1
}

echo "╔══════════════════════════════════════════════════╗"
echo "║  Accounting & Legal AI Chatbot — Full Startup    ║"
echo "╚══════════════════════════════════════════════════╝"

# ── 1. Kill stale processes ───────────────────────────────────────────────────
echo ""
echo "▶ Stopping any stale processes on :8002 and :5173…"
kill_port 8002
kill_port 5173
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

for i in $(seq 1 "$STARTUP_TIMEOUT"); do
  if curl -sf http://localhost:8002/health &>/dev/null; then
    echo "  ✓ Backend healthy"; break
  fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "  ✗ Backend process died. Check $LOG_DIR/backend.log"; exit 1
  fi
  sleep 1
  if [ "$i" -eq "$STARTUP_TIMEOUT" ]; then
    echo "  ✗ Backend timed out after ${STARTUP_TIMEOUT}s. Check $LOG_DIR/backend.log"; exit 1
  fi
done

# ── 3. Cloudflare tunnel for backend ─────────────────────────────────────────
echo ""
echo "▶ Starting Cloudflare tunnel for backend…"
CF_URL=""; CF_PID=""
if start_cf_tunnel "backend" "http://localhost:8002" "$LOG_DIR/cf-backend.log"; then
  CF_BACKEND_URL="$CF_URL"; CF_BACKEND_PID="$CF_PID"
  echo "  ✓ Backend tunnel: $CF_BACKEND_URL"
else
  CF_BACKEND_URL="(unavailable)"; CF_BACKEND_PID=""
fi

# ── 4. Patch frontend/.env with new backend URL ───────────────────────────────
echo ""
if [ "$CF_BACKEND_URL" != "(unavailable)" ]; then
  echo "▶ Updating frontend/.env → VITE_API_BASE_URL=$CF_BACKEND_URL"
  if grep -q '^VITE_API_BASE_URL=' "$ENV_FILE"; then
    sed -i '' "s|^VITE_API_BASE_URL=.*|VITE_API_BASE_URL=$CF_BACKEND_URL|" "$ENV_FILE"
  else
    echo "VITE_API_BASE_URL=$CF_BACKEND_URL" >> "$ENV_FILE"
  fi
  echo "  ✓ .env updated"
else
  echo "▶ Skipping .env patch (backend tunnel unavailable — keeping existing VITE_API_BASE_URL)"
fi

# ── 5. Frontend ───────────────────────────────────────────────────────────────
echo ""
echo "▶ Starting frontend on :5173…"
cd "$FRONTEND_DIR"
npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID"

for i in $(seq 1 "$STARTUP_TIMEOUT"); do
  if curl -sf http://localhost:5173 &>/dev/null; then
    echo "  ✓ Frontend ready"; break
  fi
  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "  ✗ Frontend process died. Check $LOG_DIR/frontend.log"; exit 1
  fi
  sleep 1
  if [ "$i" -eq "$STARTUP_TIMEOUT" ]; then
    echo "  ✗ Frontend timed out after ${STARTUP_TIMEOUT}s. Check $LOG_DIR/frontend.log"; exit 1
  fi
done

# ── 6. Cloudflare tunnel for frontend ────────────────────────────────────────
echo ""
echo "▶ Starting Cloudflare tunnel for frontend…"
CF_URL=""; CF_PID=""
if start_cf_tunnel "frontend" "http://localhost:5173" "$LOG_DIR/cf-frontend.log"; then
  CF_FRONTEND_URL="$CF_URL"; CF_FRONTEND_PID="$CF_PID"
  echo "  ✓ Frontend tunnel: $CF_FRONTEND_URL"
else
  CF_FRONTEND_URL="(unavailable)"; CF_FRONTEND_PID=""
fi

# ── 7. Summary ────────────────────────────────────────────────────────────────
echo ""
if [ "$CF_BACKEND_URL" != "(unavailable)" ] && [ "$CF_FRONTEND_URL" != "(unavailable)" ]; then
  echo "╔══════════════════════════════════════════════════╗"
  echo "║  ✅  All services started successfully           ║"
  echo "╚══════════════════════════════════════════════════╝"
else
  echo "╔══════════════════════════════════════════════════╗"
  echo "║  ⚠   Services started (tunnels partially down)  ║"
  echo "╚══════════════════════════════════════════════════╝"
fi
echo ""
echo "  LOCAL (always works)"
echo "    Backend  : http://localhost:8002"
echo "    Frontend : http://localhost:5173"
echo ""
echo "  INTERNET (share these links)"
echo "    Backend  : $CF_BACKEND_URL"
echo "    Frontend : $CF_FRONTEND_URL"
echo ""
echo "  PIDs: backend=$BACKEND_PID  frontend=$FRONTEND_PID"
[ -n "$CF_BACKEND_PID" ]  && echo "        cf-backend=$CF_BACKEND_PID"
[ -n "$CF_FRONTEND_PID" ] && echo "        cf-frontend=$CF_FRONTEND_PID"
echo ""
echo "  Press Ctrl+C to stop all services"
echo ""

# Unset EXIT trap now — let services run until Ctrl+C (INT/TERM handles cleanup)
trap - EXIT
trap cleanup INT TERM

# Keep script alive; || true prevents set -e from firing if a child crashes
wait || true
