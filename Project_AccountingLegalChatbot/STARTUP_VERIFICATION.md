# Startup Scripts Verification & Fixes Summary

## Files Checked & Updated

### ✅ `.env` (Project Root)
**Changes:**
- `PORT=8000` → `PORT=8001`

**Reason:** Backend was originally configured for port 8000, but a ghost socket persists on that port. Port 8001 is working and matches frontend config.

**Current Value:**
```
HOST=0.0.0.0
PORT=8001
```

---

### ✅ `run_project.ps1` (PowerShell Launcher)
**Changes:**
- Line 39: `http://localhost:8000` → `http://localhost:8001` (display message)
- Line 41: `http://localhost:8000/docs` → `http://localhost:8001/docs` (API docs link)
- Line 57: `--port 8000` → `--port 8001` (uvicorn backend port)
- Line 109: Health check URL `http://localhost:8000/health` → `http://localhost:8001/health`

**Current References:**
```powershell
# Line 39-41
Write-Log "  Backend  : http://localhost:8001" White
Write-Log "  Frontend : http://localhost:5173" White
Write-Log "  API Docs : http://localhost:8001/docs" White

# Line 57
& $py -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload `

# Line 109
$response = Invoke-WebRequest -Uri "http://localhost:8001/health" -UseBasicParsing -TimeoutSec 2
```

---

### ✅ `run_project.bat` (Batch Wrapper)
**Status:** No changes needed — correctly delegates to `run_project.ps1`

**Content:**
```batch
@echo off
REM run_project.bat — Double-click launcher for the full app.
REM Starts backend + frontend via PowerShell script.

echo Starting Accounting ^& Legal Chatbot...
powershell -ExecutionPolicy Bypass -File "%~dp0run_project.ps1"
pause
```

**Usage:** Double-click to start with visible console

---

### ✅ `run_hidden.bat` (Hidden Mode Launcher)
**Status:** No changes needed — correctly delegates to `run_hidden.vbs`

**Content:**
```batch
@echo off
REM run_hidden.bat — Double-click to start the app with NO visible window.
REM All output is logged to: backend_server.log, frontend_server.log, run_project.log

wscript "%~dp0run_hidden.vbs"
```

**Usage:** Double-click to start silently (all output goes to log files)

---

### ✅ `run_hidden.vbs` (VBScript Helper)
**Status:** No changes needed — correctly calls PowerShell with hidden window

**Content:**
```vbscript
' run_hidden.vbs
' Launches run_project.ps1 completely hidden (no visible window).
' Logs are written to: backend_server.log, frontend_server.log, run_project.log

Set fso   = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
psScript  = scriptDir & "\run_project.ps1"

' Window style 0 = hidden; False = don't wait for completion
shell.Run "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -NonInteractive -File """ & psScript & """", 0, False
```

---

### ✅ `frontend/.env` (React Frontend Config)
**Status:** Already correct — no changes needed

**Content:**
```
VITE_API_BASE_URL=http://localhost:8001
```

---

## URL Map (All Services)

| Service | URL | Purpose |
|---------|-----|---------|
| **Web UI** | http://localhost:5173 | Main application |
| **Backend API** | http://localhost:8001 | REST endpoints |
| **API Docs** | http://localhost:8001/docs | Swagger/OpenAPI explorer |
| **Health Check** | http://localhost:8001/health | Backend status |

---

## How to Use

### 1. GUI Mode (Visible Console)
```bash
Double-click: run_project.bat
```
- Shows real-time logs from backend and frontend
- Useful for debugging
- Press Ctrl+C to stop

### 2. Silent Mode (Hidden Window)
```bash
Double-click: run_hidden.bat
```
- No visible window
- All output → `backend_server.log`, `frontend_server.log`, `run_project.log`
- Use Task Manager or scripts to stop

### 3. Manual PowerShell
```powershell
.\run_project.ps1
```

---

## Auto-Restart Behavior

The launcher has built-in crash detection:

```
- Restart delay: 3 seconds
- Max consecutive failures: 5
- Stability threshold: 30 seconds (crash counter resets if uptime > 30s)
```

If either backend or frontend crashes 5 times in a row without staying up for 30s, the launcher exits and you see an error message.

---

## Log Files

| File | Content | Location |
|------|---------|----------|
| `backend_server.log` | Backend (FastAPI/uvicorn) output | Project root |
| `frontend_server.log` | Frontend (Vite) output | Project root |
| `run_project.log` | Launcher status/errors | Project root |

**Clear logs:**
```powershell
Clear-Content backend_server.log
Clear-Content frontend_server.log
Clear-Content run_project.log
```

---

## Troubleshooting

### Port 8001 Already in Use
```powershell
netstat -ano | findstr :8001
taskkill /PID <PID> /F
```

Then restart the launcher.

### Frontend Can't Connect to Backend
1. Check backend is running: `http://localhost:8001/health`
2. Verify `.env PORT=8001`
3. Verify `frontend/.env VITE_API_BASE_URL=http://localhost:8001`

### "Python venv not found"
```powershell
.\install_all_dependencies.ps1
```

---

## Summary of Corrections

| File | Issue | Fix | Status |
|------|-------|-----|--------|
| `.env` | PORT=8000 | PORT=8001 | ✅ Fixed |
| `run_project.ps1` | Hardcoded port 8000 | Changed to 8001 (4 places) | ✅ Fixed |
| `run_project.bat` | N/A | Already correct | ✅ OK |
| `run_hidden.bat` | N/A | Already correct | ✅ OK |
| `run_hidden.vbs` | N/A | Already correct | ✅ OK |
| `frontend/.env` | N/A | Already correct | ✅ OK |

All startup files now have **consistent port configuration** and correct links.

---

**New Documentation:**
- `STARTUP_GUIDE.md` — Complete user guide for launching and configuring the app
