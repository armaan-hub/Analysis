# run_project.ps1
# Starts backend (uvicorn) + frontend (vite dev) with auto-restart on crash.
# Press Ctrl+C to stop both cleanly.

$ErrorActionPreference = "Continue"

$ROOT          = Split-Path -Parent $MyInvocation.MyCommand.Path
$BACKEND       = Join-Path $ROOT "backend"
$FRONTEND      = Join-Path $ROOT "frontend"
$PYTHON        = Join-Path $BACKEND "venv\Scripts\python.exe"   # use directly — avoids Activate.ps1 issues in jobs
$BACKEND_LOG   = Join-Path $ROOT "backend_server.log"
$FRONTEND_LOG  = Join-Path $ROOT "frontend_server.log"
$LAUNCHER_LOG  = Join-Path $ROOT "run_project.log"

function Write-Log {
    param([string]$Message, [string]$Color = "White")
    Write-Host $Message -ForegroundColor $Color
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LAUNCHER_LOG -Value "[$ts] $Message" -Encoding UTF8 -ErrorAction SilentlyContinue
}

Write-Log ""
Write-Log "============================================" Cyan
Write-Log "  Accounting & Legal Chatbot - Launcher" Cyan
Write-Log "============================================" Cyan
Write-Log ""

# ── Verify paths ─────────────────────────────────────────────────────────────
if (-not (Test-Path $PYTHON)) {
    Write-Log "[ERROR] Python venv not found at: $PYTHON" Red
    Write-Log "        Run install_all_dependencies.ps1 first." Yellow
    exit 1
}
if (-not (Test-Path (Join-Path $FRONTEND "package.json"))) {
    Write-Log "[ERROR] Frontend package.json not found at: $FRONTEND" Red
    exit 1
}

Write-Log "  Backend  : http://localhost:8001" White
Write-Log "  Frontend : http://localhost:5173" White
Write-Log "  API Docs : http://localhost:8001/docs" White
Write-Log "  Logs     : backend_server.log | frontend_server.log" White
Write-Log "  Press Ctrl+C to stop both services." Yellow
Write-Log ""

# ── Port cleanup helper ───────────────────────────────────────────────────────
function Stop-ViteProcesses {
    # Kill any process holding Vite's port range (5173-5179) so the next start
    # always gets 5173. Stop-Job kills the PS job wrapper but leaves node.exe alive.
    $killed = 0
    5173..5179 | ForEach-Object {
        $port = $_
        netstat -ano | Select-String ":${port}\s" | ForEach-Object {
            $parts = ($_ -split '\s+') | Where-Object { $_ -ne '' }
            $pid_ = $parts[-1]
            if ($pid_ -match '^\d+$') {
                Stop-Process -Id ([int]$pid_) -Force -ErrorAction SilentlyContinue
                Write-Log "  [CLEANUP] Killed process $pid_ on port $port" DarkGray
                $killed++
            }
        }
    }
    if ($killed -gt 0) { Start-Sleep -Seconds 1 }   # give Windows time to release ports
}

# ── Job factory functions ─────────────────────────────────────────────────────
function New-BackendJob {
    param($backendPath, $pythonExe)
    return Start-Job -ScriptBlock {
        param($bp, $py)
        Set-Location $bp
        $env:PYTHONUTF8 = "1"   # prevents UnicodeEncodeError on Windows cp1252 terminals
        # Restrict the file watcher to the application source only.
        # --reload-dir "." limits watching to the backend directory.
        # --reload-exclude "venv" prevents venv .py files (synced by OneDrive)
        # from triggering spurious reloads; likewise for data/db/cache dirs.
        & $py -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload `
            --reload-dir "." `
            --reload-exclude "venv" `
            --reload-exclude "data" `
            --reload-exclude "__pycache__" `
            --reload-exclude "vector_store_v2" `
            --reload-exclude "uploads" `
            2>&1
    } -ArgumentList $backendPath, $pythonExe
}

function New-FrontendJob {
    param($frontendPath)
    return Start-Job -ScriptBlock {
        param($fp)
        Set-Location $fp
        & npm run dev 2>&1
    } -ArgumentList $frontendPath
}

# ── Restart policy ────────────────────────────────────────────────────────────
$RESTART_DELAY    = 3    # seconds to wait before restarting
$MAX_CONSEC_FAILS = 5    # stop after this many back-to-back crashes
$STABLE_THRESHOLD = 30   # seconds of uptime that resets the crash counter

# ── Initial launch ────────────────────────────────────────────────────────────
Write-Log "[1/2] Starting backend ..."  Green
$backendJob    = New-BackendJob  $BACKEND $PYTHON
$backendFails  = 0
$backendStart  = Get-Date

# Wait for backend to be ready — stream output while polling so the user
# sees progress rather than a blank screen. Use a deadline instead of a
# counter so the timeout is correct regardless of sleep duration.
# Increased timeout to 120 seconds to accommodate slower systems or first-time initialization
$backendDeadline = (Get-Date).AddSeconds(120)
Write-Host "Waiting for backend to be ready..."
while ((Get-Date) -lt $backendDeadline) {
    # Forward any backend output accumulated since last poll
    $out = Receive-Job -Job $backendJob -ErrorAction SilentlyContinue
    if ($out) {
        $out | ForEach-Object {
            Write-Host "[backend]  $_" -ForegroundColor DarkCyan
            Add-Content -Path $BACKEND_LOG -Value $_ -Encoding UTF8 -ErrorAction SilentlyContinue
        }
    }

    if ($backendJob.State -in "Failed", "Stopped") {
        Write-Log "ERROR: Backend job failed to start. Check backend_server.log" Red
        break
    }
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8001/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-Log "Backend is ready!" Green
            break
        }
    } catch {
        # Not ready yet, continue waiting
    }
    Start-Sleep -Milliseconds 500
}
if ((Get-Date) -ge $backendDeadline) {
    Write-Log "Warning: Backend did not become ready within 120 seconds. Starting frontend anyway." Yellow
}

Write-Log "[2/2] Starting frontend ..." Green
# Kill any lingering Vite/node processes before starting
Stop-ViteProcesses

$frontendJob   = New-FrontendJob $FRONTEND
$frontendFails = 0
$frontendStart = Get-Date

Write-Log ""

# ── Main loop ─────────────────────────────────────────────────────────────────
try {
    while ($true) {

        # Forward backend output
        $out = Receive-Job -Job $backendJob -ErrorAction SilentlyContinue
        if ($out) {
            $out | ForEach-Object {
                Write-Host "[backend]  $_" -ForegroundColor DarkCyan
                Add-Content -Path $BACKEND_LOG -Value $_ -Encoding UTF8 -ErrorAction SilentlyContinue
            }
        }

        # Forward frontend output
        $out = Receive-Job -Job $frontendJob -ErrorAction SilentlyContinue
        if ($out) {
            $out | ForEach-Object {
                Write-Host "[frontend] $_" -ForegroundColor DarkGreen
                Add-Content -Path $FRONTEND_LOG -Value $_ -Encoding UTF8 -ErrorAction SilentlyContinue
            }
        }

        # ── Auto-restart backend if stopped ──────────────────────────────────
        if ($backendJob.State -in "Completed", "Failed", "Stopped") {
            $uptime = (Get-Date) - $backendStart
            if ($uptime.TotalSeconds -ge $STABLE_THRESHOLD) { $backendFails = 0 }  # was stable — reset counter
            $backendFails++
            if ($backendFails -gt $MAX_CONSEC_FAILS) {
                Write-Log "[ERROR] Backend crashed $MAX_CONSEC_FAILS times in a row. Fix the error above and re-run the script." Red
                break
            }
            $uptimeSec = [int]$uptime.TotalSeconds
            Write-Log "[RESTART $backendFails/$MAX_CONSEC_FAILS] Backend stopped (uptime: ${uptimeSec}s). Restarting in ${RESTART_DELAY}s..." Yellow
            Start-Sleep -Seconds $RESTART_DELAY
            Remove-Job -Job $backendJob -Force -ErrorAction SilentlyContinue
            $backendJob   = New-BackendJob $BACKEND $PYTHON
            $backendStart = Get-Date
            Write-Log "[OK] Backend restarted." Green
        }

        # ── Auto-restart frontend if stopped ─────────────────────────────────
        if ($frontendJob.State -in "Completed", "Failed", "Stopped") {
            $uptime = (Get-Date) - $frontendStart
            if ($uptime.TotalSeconds -ge $STABLE_THRESHOLD) { $frontendFails = 0 }
            $frontendFails++
            if ($frontendFails -gt $MAX_CONSEC_FAILS) {
                Write-Log "[ERROR] Frontend crashed $MAX_CONSEC_FAILS times in a row. Fix the error above and re-run the script." Red
                break
            }
            $uptimeSec = [int]$uptime.TotalSeconds
            Write-Log "[RESTART $frontendFails/$MAX_CONSEC_FAILS] Frontend stopped (uptime: ${uptimeSec}s). Restarting in ${RESTART_DELAY}s..." Yellow
            Start-Sleep -Seconds $RESTART_DELAY
            Remove-Job -Job $frontendJob -Force -ErrorAction SilentlyContinue
            Stop-ViteProcesses
            $frontendJob   = New-FrontendJob $FRONTEND
            $frontendStart = Get-Date
            Write-Log "[OK] Frontend restarted." Green
        }

        Start-Sleep -Milliseconds 200
    }
}
finally {
    # ── Clean shutdown on Ctrl+C ─────────────────────────────────────────────
    Write-Log ""
    Write-Log "Shutting down services..." Yellow
    if ($backendJob) {
        Stop-Job  -Job $backendJob  -ErrorAction SilentlyContinue
        Remove-Job -Job $backendJob -Force -ErrorAction SilentlyContinue
        Write-Log "  [OK] Backend stopped." DarkGray
    }
    if ($frontendJob) {
        Stop-Job  -Job $frontendJob  -ErrorAction SilentlyContinue
        Remove-Job -Job $frontendJob -Force -ErrorAction SilentlyContinue
        Write-Log "  [OK] Frontend job stopped." DarkGray
    }
    # Kill any node/vite process still holding the port (child of npm run dev
    # is not always cleaned up when the PS job wrapper is stopped)
    Stop-ViteProcesses
    Write-Log "Done." Green
}
