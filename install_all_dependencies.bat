@echo off
set SCRIPT_DIR=%~dp0
powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%install_all_dependencies.ps1"
if %ERRORLEVEL% NEQ 0 (
  echo Dependency installation failed.
  exit /b %ERRORLEVEL%
)
echo Dependency installation completed.
