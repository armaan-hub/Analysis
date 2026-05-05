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
sleep 8

BACKEND_OK=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8002/health 2>/dev/null)
FRONTEND_OK=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5173 2>/dev/null)

echo ""
echo "=== Status ==="
[ "$BACKEND_OK" = "200" ] && echo "✅ Backend:  http://localhost:8002" || echo "❌ Backend:  not responding (check ~/backend_server.log)"
[ "$FRONTEND_OK" = "200" ] && echo "✅ Frontend: http://localhost:5173" || echo "❌ Frontend: not responding (check ~/frontend_server.log)"
echo "📖 API Docs: http://localhost:8002/docs"
