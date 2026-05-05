# Unified Backend/Frontend Startup System Design

Date: 2026-05-05
Status: Design Approved

## Overview

Three-layer startup system:
- Service Layer: Individual start scripts with validation
- npm Scripts: Cross-platform npm commands
- Orchestration: Unified startup script

## Components

### 1. Backend Startup (backend/scripts/start.sh)
- Check port 8002 availability
- Verify Python venv at ~/chatbot_venv
- Verify .env with NVIDIA keys
- Start FastAPI with uvicorn

### 2. Frontend Startup (frontend/scripts/start.sh)
- Check port 5173 availability
- Verify node_modules installed
- Start Vite dev server

### 3. Unified Script (start-dev.sh)
- Parse args: --backend-only, --frontend-only
- Start both in parallel
- Run health checks
- Handle Ctrl+C shutdown

### 4. Health Check (health-check.sh)
- Probe backend health endpoint
- Probe frontend availability
- 30-second timeout

## npm Scripts

Backend: npm run start = bash scripts/start.sh
Frontend: npm run start = bash scripts/start.sh

## Error Handling

1. Port in use: Show process info and how to resolve
2. venv missing: Show setup instructions
3. env missing: Show copy-from-example steps

## Usage

./start-dev.sh          (start both)
./start-dev.sh --backend-only
./start-dev.sh --frontend-only

## Success Criteria

✓ Reliable two-service startup
✓ Clear error messages
✓ Health verification
✓ Individual control
✓ Graceful shutdown
✓ Project-directory agnostic

## Out of Scope

- Auto-restart
- Boot auto-start
- Docker
- Env switching
- File logging
