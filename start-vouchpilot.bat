@echo off
rem VouchPilot double-click launcher: backend API + premium web UI (+ llama server if weights exist).
cd /d %~dp0
powershell -ExecutionPolicy Bypass -File start-vouchpilot.ps1
pause

