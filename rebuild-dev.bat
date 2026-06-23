@echo off
setlocal
cd /d "%~dp0"

echo Rebuilding and starting knowmate development stack...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-dev.ps1" -Rebuild

echo.
echo Window will stay open so you can read the startup result.
pause
