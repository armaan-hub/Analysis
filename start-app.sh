#!/usr/bin/env bash
set -e

# ── Config ────────────────────────────────────────────────────────────────────
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/Project_AccountingLegalChatbot/backend"
FRONTEND_DIR="$PROJECT_ROOT/Project_AccountingLegalChatbot/frontend"
VENV="$HOME/chatbot_venv/bin/activate"
ENV_FILE="$FRONTEND_DIR/.env"
LOG_DIR="$PROJECT_ROOT/logs"
CF_RETRIES=5                       # attempts before giving up on tunnel
CF_WAIT_SECS=45                    # seconds to wait per attempt for URL
CF_RETRY_DELAY=8                   # seconds between retry attempts
STARTUP_TIMEOUT=${STARTUP_TIMEOUT:-60}

mkdir -p "$LOG_DIR"

# ── Helpers ───────────────────────────────────────────────────────────────────
kill_port() {
  local pids
  pids=$(lsof -ti tcp:"$1" 2>/dev/null) || true
  [ -n "$pids" ] && echo "$pids" | xargs kill -9 2>/dev/null || true
}

# ── Cleanup ───────────────────────────────────────────────────────────────────
BACKEND_PID="" FRONTEND_PID="" CF_BACKEND_PID=""
cleanup() {
  echo ""
  echo "▶ Shutting down all services…"
  for pid in "$BACKEND_PID" "$FRONTEND_PID" "$CF_BACKEND_PID"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
  kill_port 8002; kill_port 5173
  # Always restore .env to localhost so next browser open works without a tunnel
  local env_file="$FRONTEND_DIR/.env"
  if [ -f "$env_file" ]; then
    sed -i '' "s|^VITE_API_BASE_URL=.*|VITE_API_BASE_URL=http://localhost:8002|" "$env_file" 2>/dev/null || true
  fi
  echo "  ✓ Stopped."
}
trap cleanup INT TERM EXIT

# ── CF tunnel helper ──────────────────────────────────────────────────────────
start_cf_tunnel() {
  local name="$1" local_url="$2" log_file="$3"
  local attempt url pid i

  for attempt in $(seq 1 "$CF_RETRIES"); do
    [ "$attempt" -gt 1 ] && echo "  ↻ Retry $attempt/$CF_RETRIES for $name tunnel…"
    > "$log_file"

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
    sleep "$CF_RETRY_DELAY"
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

# ── 3. Cloudflare tunnel for backend (SINGLE tunnel — serves both API + UI) ──
echo ""
echo "▶ Starting Cloudflare tunnel…"
CF_URL=""; CF_PID=""
if start_cf_tunnel "backend" "http://localhost:8002" "$LOG_DIR/cf-backend.log"; then
  CF_BACKEND_URL="$CF_URL"; CF_BACKEND_PID="$CF_PID"
  echo "  ✓ Tunnel: $CF_BACKEND_URL"
else
  CF_BACKEND_URL="(unavailable)"; CF_BACKEND_PID=""
fi

# ── 4. Dev server always uses localhost — NEVER patch .env with tunnel URL ───
# The dev server is for local use; the tunnel URL is shown in the summary only.
# Ensure .env is set to localhost:8002 so the dev server always works locally.
echo ""
echo "▶ Ensuring frontend/.env → VITE_API_BASE_URL=http://localhost:8002 (local dev)"
if grep -q '^VITE_API_BASE_URL=' "$ENV_FILE" 2>/dev/null; then
  sed -i '' "s|^VITE_API_BASE_URL=.*|VITE_API_BASE_URL=http://localhost:8002|" "$ENV_FILE"
else
  echo "VITE_API_BASE_URL=http://localhost:8002" >> "$ENV_FILE"
fi
echo "  ✓ .env set to localhost:8002"

# ── 5. Build frontend with tunnel URL → served at /ui via backend tunnel ─────
echo ""
echo "▶ Building frontend for internet access (served at /ui via backend tunnel)…"
cd "$FRONTEND_DIR"
BUILD_ENV="VITE_API_BASE_URL=${CF_BACKEND_URL}"
if [ "$CF_BACKEND_URL" = "(unavailable)" ]; then
  BUILD_ENV="VITE_API_BASE_URL=http://localhost:8002"
fi
if env "$BUILD_ENV" npm run build > "$LOG_DIR/frontend-build.log" 2>&1; then
  echo "  ✓ Frontend built → ${CF_BACKEND_URL}/ui"
else
  echo "  ⚠ Frontend build failed — check $LOG_DIR/frontend-build.log"
  echo "    Internet access at /ui may show stale build."
fi

# ── 6. Start Vite dev server for local hot-reload ────────────────────────────
echo ""
echo "▶ Starting frontend dev server on :5173 (local hot-reload)…"
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

# ── 7. Summary ────────────────────────────────────────────────────────────────
echo ""
if [ "$CF_BACKEND_URL" != "(unavailable)" ]; then
  echo "╔══════════════════════════════════════════════════╗"
  echo "║  ✅  All services started successfully           ║"
  echo "╚══════════════════════════════════════════════════╝"
else
  echo "╔══════════════════════════════════════════════════╗"
  echo "║  ⚠   Services started (tunnel unavailable)      ║"
  echo "╚══════════════════════════════════════════════════╝"
fi
echo ""
echo "  LOCAL (always works)"
echo "    Backend  : http://localhost:8002"
echo "    Frontend : http://localhost:5173  (hot-reload)"
echo "    Frontend : http://localhost:8002/ui  (production build)"
echo ""
echo "  INTERNET (single tunnel, always reliable)"
echo "    Backend  : $CF_BACKEND_URL"
if [ "$CF_BACKEND_URL" != "(unavailable)" ]; then
  echo "    Frontend : ${CF_BACKEND_URL}/ui"
else
  echo "    Frontend : (unavailable — tunnel failed)"
fi
echo ""
echo "  PIDs: backend=$BACKEND_PID  frontend=$FRONTEND_PID"
[ -n "$CF_BACKEND_PID" ] && echo "        cf-backend=$CF_BACKEND_PID"
echo ""
echo "  Press Ctrl+C to stop all services"
echo ""

trap - EXIT
trap cleanup INT TERM

wait || true
