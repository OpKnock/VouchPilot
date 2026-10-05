@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-VouchPilot.ps1"
if errorlevel 1 (
  echo.
  echo VouchPilot installation failed. See the message above.
  pause
)
