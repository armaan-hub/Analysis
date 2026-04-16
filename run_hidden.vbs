' run_hidden.vbs
' Launches run_project.ps1 completely hidden (no visible window).
' Logs are written to: backend_server.log, frontend_server.log, run_project.log

Set fso   = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
psScript  = scriptDir & "\run_project.ps1"

' Window style 0 = hidden; False = don't wait for completion
shell.Run "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -NonInteractive -File """ & psScript & """", 0, False
