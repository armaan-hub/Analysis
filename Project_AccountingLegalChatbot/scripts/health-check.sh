#!/bin/bash

BACKEND_URL="http://localhost:8002"
FRONTEND_URL="http://localhost:5173"
TIMEOUT=30
INTERVAL=1

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo "Checking service health..."
echo ""

BACKEND_OK=0
FRONTEND_OK=0
ELAPSED=0

while [ $ELAPSED -lt $TIMEOUT ]; do
    # Check backend health
    if [ $BACKEND_OK -eq 0 ]; then
        if curl -sf "$BACKEND_URL/api/health" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Backend${NC} responding at $BACKEND_URL"
            BACKEND_OK=1
        fi
    fi

    # Check frontend
    if [ $FRONTEND_OK -eq 0 ]; then
        if curl -sf "$FRONTEND_URL" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Frontend${NC} responding at $FRONTEND_URL"
            FRONTEND_OK=1
        fi
    fi

    # Both are healthy
    if [ $BACKEND_OK -eq 1 ] && [ $FRONTEND_OK -eq 1 ]; then
        echo ""
        echo -e "${GREEN}✓ All services healthy!${NC}"
        exit 0
    fi

    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done

# Timeout reached
echo ""
if [ $BACKEND_OK -eq 0 ]; then
    echo -e "${RED}✗ Backend${NC} not responding after ${TIMEOUT}s"
fi
if [ $FRONTEND_OK -eq 0 ]; then
    echo -e "${RED}✗ Frontend${NC} not responding after ${TIMEOUT}s"
fi
exit 1
