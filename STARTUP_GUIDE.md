# Startup Guide — Accounting & Legal AI Chatbot

## Quick Start (Windows)

### Option 1: GUI Launcher (Recommended)
**Double-click:** `run_project.bat`

This starts the app with visible console output. You'll see both backend and frontend logs in real-time.

**Ports:**
- Backend: `http://localhost:8001` (API, docs at `/docs`)
- Frontend: `http://localhost:5173` (Web UI)
- Auto-restarts on crash

---

### Option 2: Hidden Background Mode
**Double-click:** `run_hidden.bat`

Launches the app with **no visible window**. All output is logged to files:
- `backend_server.log` — Backend activity
- `frontend_server.log` — Frontend activity
- `run_project.log` — Launcher status

To stop: Open Task Manager, kill PowerShell processes, or check `run_project.log` for the PID.

---

### Option 3: Manual PowerShell
```powershell
powershell -ExecutionPolicy Bypass -File ".\run_project.ps1"
```

---

## First-Time Setup

If you see "Python venv not found" error:
```powershell
.\install_all_dependencies.ps1
```

This installs:
- Python virtual environment (`backend/venv`)
- Backend dependencies (FastAPI, SQLite, etc.)
- Frontend dependencies (Node.js packages)

---

## Configuration

### Backend Port
Edit `.env`:
```
PORT=8001
```

### Frontend Dev Server Port
Frontend auto-selects port if 5173 is occupied. Check console output for the actual port.

### LLM Models
In `.env`:
```
NVIDIA_MODEL=deepseek-ai/deepseek-v3.2  # Deep research / Analyst / Council
NVIDIA_FAST_MODEL=deepseek-ai/deepseek-v3.1-terminus  # Fast mode

# OR use working fallbacks when DeepSeek is cold:
# NVIDIA_MODEL=nvidia/llama-3.3-nemotron-super-49b-v1
# NVIDIA_FAST_MODEL=meta/llama-3.3-70b-instruct
```

---

## Accessing the App

Once running:

1. **Web UI:** Open `http://localhost:5173` in your browser
2. **API Docs:** `http://localhost:8001/docs` (interactive API explorer)
3. **Health Check:** `http://localhost:8001/health`

---

## Logs

- **Backend:** Saved to `backend_server.log` (grows indefinitely; rotate as needed)
- **Frontend:** Saved to `frontend_server.log`
- **Launcher:** Saved to `run_project.log`

Clear logs:
```powershell
Clear-Content backend_server.log
Clear-Content frontend_server.log
Clear-Content run_project.log
```

---

## Troubleshooting

### "Port 8001 already in use"
Another app is using port 8001. Check:
```powershell
netstat -ano | findstr :8001
```

Then either:
- Kill the process
- Change `.env PORT=8002` and update frontend `.env VITE_API_BASE_URL=http://localhost:8002`

### "Python venv not found"
Run: `.\install_all_dependencies.ps1`

### Frontend stuck on "Connecting to backend"
- Check `http://localhost:8001/health` in browser
- Check `backend_server.log` for errors
- Verify `.env PORT` matches frontend `VITE_API_BASE_URL`

### Backend crashes immediately
Check `backend_server.log` for database/API key errors

---

## Architecture

```
Project Root
├── backend/                     # FastAPI app
│   ├── main.py                 # Entry point
│   ├── core/                   # Business logic (LLM, RAG, Council)
│   ├── api/                    # REST endpoints
│   ├── tests/                  # Unit tests
│   └── venv/                   # Python virtual environment
│
├── frontend/                    # React + Vite
│   ├── src/
│   │   ├── pages/              # UI pages (Chat, Settings, etc.)
│   │   └── components/         # Reusable React components
│   └── package.json            # Node.js dependencies
│
├── .env                        # Configuration (API keys, models, ports)
├── run_project.ps1            # Main launcher script
├── run_project.bat            # Batch wrapper
└── run_hidden.bat             # Hidden mode launcher
```

---

## Default Credentials

**No authentication required.** App uses local SQLite, all data is in `data/chatbot.db`.

---

## Performance

- **Fast Mode:** 11-31s (meta/llama-3.3-70b-instruct)
- **Deep Research:** 61s (nvidia/llama-3.3-nemotron-super-49b-v1)
- **Analyst Mode:** 27s (same model)
- **Council Mode:** 160s (4 experts + synthesis)

*Times depend on NVIDIA NIM availability and network latency.*

---

## Support

Check logs first. If stuck:
1. Look at `backend_server.log` for API/database errors
2. Check `frontend_server.log` for UI errors
3. Verify `.env` configuration
4. Run `.\install_all_dependencies.ps1` again if dependencies are corrupted
