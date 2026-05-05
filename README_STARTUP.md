# Quick Start Guide — Accounting & Legal Chatbot

Get the backend and frontend running with a single command.

## Prerequisites

- Python 3.11+ with venv at `~/chatbot_venv`
- Node.js 18+
- `.env` file in `Project_AccountingLegalChatbot/backend/` (copy from `.env.example` and add NVIDIA API keys)

## Start Everything Together

```bash
./start-dev.sh
```

This starts:
- **Backend** on http://localhost:8002 (API + Swagger UI)
- **Frontend** on http://localhost:5173

Press **Ctrl+C** to stop all services.

## Individual Service Startup

Start only backend:
```bash
./start-dev.sh --backend-only
```

Start only frontend:
```bash
./start-dev.sh --frontend-only
```

Or from service directories:
```bash
cd Main Branch/Project_AccountingLegalChatbot/backend && npm run start
cd Main Branch/Project_AccountingLegalChatbot/frontend && npm run start
```

## Troubleshooting

### Error: "Port 8002 is already in use"
Find and kill the process using port 8002, then retry.

### Error: "Python venv not found at ~/chatbot_venv"
```bash
python3.11 -m venv ~/chatbot_venv
source ~/chatbot_venv/bin/activate
cd Main Branch/Project_AccountingLegalChatbot/backend
pip install -r requirements.txt
```

### Error: ".env file not found"
```bash
cd Main Branch/Project_AccountingLegalChatbot/backend
cp .env.example .env
# Edit .env with your NVIDIA API keys
nano .env
```

### Error: "node_modules not found" (frontend)
```bash
cd Main Branch/Project_AccountingLegalChatbot/frontend
npm install
```

## Verify Services

Once running, test the services:
```bash
# Backend health
curl http://localhost:8002/api/health

# Backend Swagger UI
open http://localhost:8002/docs

# Frontend
open http://localhost:5173
```

All should return 200 OK.

## Service URLs

- **Backend API**: http://localhost:8002
- **Backend Swagger**: http://localhost:8002/docs  
- **Frontend**: http://localhost:5173

## Next Steps

- See `Main Branch/Project_AccountingLegalChatbot/README.md` for architecture overview
- See `Main Branch/Project_AccountingLegalChatbot/DEVELOPER_GUIDE.md` for development
- See `docs/superpowers/specs/2026-05-05-startup-scripts-design.md` for design details
