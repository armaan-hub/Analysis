#!/bin/bash
set -e

FRONTEND_PORT=5173
FRONTEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo "Starting frontend server..."

# Check if port is already in use
if lsof -Pi :$FRONTEND_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}✗ Port $FRONTEND_PORT is already in use${NC}"
    echo "Another process is listening on this port."
    echo ""
    echo "Options:"
    echo "  1. Kill the existing process:"
    echo "     PID=\$(lsof -ti:$FRONTEND_PORT)"
    echo "     kill -9 \$PID"
    echo ""
    echo "  2. Or use a different port:"
    echo "     PORT=5174 npm run start"
    exit 1
fi

# Check if node_modules exists
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo -e "${RED}✗ node_modules not found in $FRONTEND_DIR${NC}"
    echo "Install dependencies first:"
    echo "  cd $FRONTEND_DIR"
    echo "  npm install"
    exit 2
fi

cd "$FRONTEND_DIR"

echo -e "${GREEN}✓ Environment validated${NC}"
echo "Starting Vite dev server on http://localhost:$FRONTEND_PORT"
echo "Press Ctrl+C to stop"
echo ""

exec npm run dev
