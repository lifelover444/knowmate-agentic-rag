@echo off
setlocal
cd /d "%~dp0"

echo Stopping knowmate development processes...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-dev.ps1"

echo.
pause
