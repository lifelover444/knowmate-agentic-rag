@echo off
setlocal
cd /d "%~dp0"

echo Starting knowmate development stack...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-dev.ps1"

echo.
echo Window will stay open so you can read the startup result.
pause
