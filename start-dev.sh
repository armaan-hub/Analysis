#!/bin/bash

# Unified start script for backend and frontend
# Usage: ./start-dev.sh [--backend-only|--frontend-only] [--no-health-check]

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/Project_AccountingLegalChatbot/backend"
FRONTEND_DIR="$PROJECT_ROOT/Project_AccountingLegalChatbot/frontend"
HEALTH_CHECK_SCRIPT="$PROJECT_ROOT/Project_AccountingLegalChatbot/scripts/health-check.sh"

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

# Start backend if requested
if [ $START_BACKEND -eq 1 ]; then
    echo -e "${BLUE}Starting backend...${NC}"
    cd "$BACKEND_DIR"
    npm run start &
    BACKEND_PID=$!
    echo "Backend PID: $BACKEND_PID"
fi

# Start frontend if requested
if [ $START_FRONTEND -eq 1 ]; then
    echo -e "${BLUE}Starting frontend...${NC}"
    cd "$FRONTEND_DIR"
    npm run start &
    FRONTEND_PID=$!
    echo "Frontend PID: $FRONTEND_PID"
fi

echo ""

# Wait briefly for services to start
sleep 2

# Run health checks if requested and both services were started
if [ $RUN_HEALTH_CHECK -eq 1 ] && [ $START_BACKEND -eq 1 ] && [ $START_FRONTEND -eq 1 ]; then
    echo -e "${BLUE}Running health checks...${NC}"
    if [ -f "$HEALTH_CHECK_SCRIPT" ]; then
        bash "$HEALTH_CHECK_SCRIPT" || true
    fi
    echo ""
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
