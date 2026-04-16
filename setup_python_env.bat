@echo off
setlocal
set SCRIPT_DIR=%~dp0

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%setup_python_env.ps1" %*
if %ERRORLEVEL% NEQ 0 (
  echo Python environment setup failed.
  exit /b %ERRORLEVEL%
)

echo Python environment setup completed successfully.
endlocal
