#!/bin/bash
set -e

BACKEND_PORT=8002
VENV_PATH=~/chatbot_venv
BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$BACKEND_DIR/.env"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo "Starting backend server..."

# Check if port is already in use
if lsof -Pi :$BACKEND_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}✗ Port $BACKEND_PORT is already in use${NC}"
    echo "Another process is listening on this port."
    echo ""
    echo "Options:"
    echo "  1. Kill the existing process:"
    echo "     PID=\$(lsof -ti:$BACKEND_PORT)"
    echo "     kill -9 \$PID"
    echo ""
    echo "  2. Or use a different port:"
    echo "     PORT=8003 npm run start"
    exit 1
fi

# Check if venv exists
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${RED}✗ Python venv not found at $VENV_PATH${NC}"
    echo "Run setup first:"
    echo "  python3.11 -m venv $VENV_PATH"
    echo "  source $VENV_PATH/bin/activate"
    echo "  pip install -r $BACKEND_DIR/requirements.txt"
    exit 2
fi

# Check if .env exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}✗ .env file not found in $BACKEND_DIR${NC}"
    echo "Create it from the example:"
    echo "  cp $BACKEND_DIR/.env.example $ENV_FILE"
    echo "  Edit $ENV_FILE with your NVIDIA API keys"
    exit 3
fi

# Source venv and start backend
source "$VENV_PATH/bin/activate"
cd "$BACKEND_DIR"

echo -e "${GREEN}✓ Environment validated${NC}"
echo "Starting FastAPI server on http://localhost:$BACKEND_PORT"
echo "Press Ctrl+C to stop"
echo ""

exec uvicorn main:app --reload --host localhost --port $BACKEND_PORT
