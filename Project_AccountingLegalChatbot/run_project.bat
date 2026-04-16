@echo off
REM run_project.bat — Double-click launcher for the full app.
REM Starts backend + frontend via PowerShell script.

echo Starting Accounting ^& Legal Chatbot...
powershell -ExecutionPolicy Bypass -File "%~dp0run_project.ps1"
pause
