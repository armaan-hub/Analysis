#!/bin/bash

# Unified start script for backend and frontend
# Usage: ./start-dev.sh [--backend-only|--frontend-only] [--no-health-check]
#
# Active code lives at ~/chatbot_local/ (local git clone separate from OneDrive)
# Backend:  http://localhost:8002
# Frontend: http://localhost:5173

CHATBOT_ROOT="$HOME/chatbot_local/Project_AccountingLegalChatbot"
BACKEND_DIR="$CHATBOT_ROOT/backend"
FRONTEND_DIR="$CHATBOT_ROOT/frontend"
VENV="$HOME/chatbot_venv"

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Parse arguments
START_BACKEND=1
START_FRONTEND=1
RUN_HEALTH_CHECK=1

for arg in "$@"; do
    case $arg in
        --backend-only)
            START_FRONTEND=0
            ;;
        --frontend-only)
            START_BACKEND=0
            ;;
        --no-health-check)
            RUN_HEALTH_CHECK=0
            ;;
    esac
done

# Trap Ctrl+C to clean up both processes
trap 'cleanup' SIGINT SIGTERM

cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down services...${NC}"
    
    if [ ! -z "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill -TERM "$BACKEND_PID" 2>/dev/null || true
        wait "$BACKEND_PID" 2>/dev/null || true
    fi
    
    if [ ! -z "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        kill -TERM "$FRONTEND_PID" 2>/dev/null || true
        wait "$FRONTEND_PID" 2>/dev/null || true
    fi
    
    echo -e "${YELLOW}✓ All services stopped${NC}"
    exit 0
}

echo -e "${BLUE}=== Accounting & Legal Chatbot Startup ===${NC}"
echo ""

# Validate directories exist
if [ $START_BACKEND -eq 1 ] && [ ! -d "$BACKEND_DIR" ]; then
    echo -e "\033[0;31m✗ Backend directory not found: $BACKEND_DIR\033[0m"
    echo "  Make sure ~/chatbot_local is checked out from git@github.com:armaan-hub/Analysis.git"
    exit 1
fi
if [ $START_FRONTEND -eq 1 ] && [ ! -d "$FRONTEND_DIR" ]; then
    echo -e "\033[0;31m✗ Frontend directory not found: $FRONTEND_DIR\033[0m"
    exit 1
fi
if [ $START_BACKEND -eq 1 ] && [ ! -d "$VENV" ]; then
    echo -e "\033[0;31m✗ Python venv not found: $VENV\033[0m"
    echo "  Run: python3 -m venv ~/chatbot_venv && ~/chatbot_venv/bin/pip install -r $BACKEND_DIR/requirements.txt"
    exit 1
fi

# Start backend if requested
if [ $START_BACKEND -eq 1 ]; then
    echo -e "${BLUE}Starting backend...${NC}"
    # Kill any existing process on port 8002
    lsof -ti :8002 | xargs -r kill -9 2>/dev/null || true
    cd "$BACKEND_DIR"
    source "$VENV/bin/activate"
    "$VENV/bin/uvicorn" main:app --host localhost --port 8002 --reload > /tmp/chatbot_backend.log 2>&1 &
    BACKEND_PID=$!
    echo "Backend PID: $BACKEND_PID (log: /tmp/chatbot_backend.log)"
fi

# Start frontend if requested
if [ $START_FRONTEND -eq 1 ]; then
    echo -e "${BLUE}Starting frontend...${NC}"
    # Kill any existing process on port 5173
    lsof -ti :5173 | xargs -r kill -9 2>/dev/null || true
    cd "$FRONTEND_DIR"
    npm run dev > /tmp/chatbot_frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo "Frontend PID: $FRONTEND_PID (log: /tmp/chatbot_frontend.log)"
fi

echo ""
echo -e "${BLUE}Waiting for services to start...${NC}"
sleep 4

# Health check
if [ $RUN_HEALTH_CHECK -eq 1 ] && [ $START_BACKEND -eq 1 ]; then
    BACKEND_OK=0
    for i in {1..10}; do
        if curl -sf http://localhost:8002/health > /dev/null 2>&1; then
            BACKEND_OK=1
            break
        fi
        sleep 1
    done
    if [ $BACKEND_OK -eq 0 ]; then
        echo -e "\033[0;31m✗ Backend health check failed — see /tmp/chatbot_backend.log\033[0m"
        tail -20 /tmp/chatbot_backend.log
    fi
fi

if [ $RUN_HEALTH_CHECK -eq 1 ] && [ $START_FRONTEND -eq 1 ]; then
    FRONTEND_OK=0
    for i in {1..10}; do
        if curl -sf http://localhost:5173 > /dev/null 2>&1; then
            FRONTEND_OK=1
            break
        fi
        sleep 1
    done
    if [ $FRONTEND_OK -eq 0 ]; then
        echo -e "\033[0;31m✗ Frontend health check failed — see /tmp/chatbot_frontend.log\033[0m"
        tail -10 /tmp/chatbot_frontend.log
    fi
fi

# Show status
if [ $START_BACKEND -eq 1 ]; then
    echo -e "${GREEN}✓ Backend:${NC}  http://localhost:8002"
    echo -e "  Swagger: http://localhost:8002/docs"
fi

if [ $START_FRONTEND -eq 1 ]; then
    echo -e "${GREEN}✓ Frontend:${NC} http://localhost:5173"
fi

echo ""
echo -e "${GREEN}Services ready!${NC}"
echo "Press Ctrl+C to stop all services."
echo ""

# Keep script running and forward signals
wait
