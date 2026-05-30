@echo off
setlocal
cd /d "%~dp0"

echo Restarting knowmate frontend...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\restart-frontend.ps1"

echo.
pause
