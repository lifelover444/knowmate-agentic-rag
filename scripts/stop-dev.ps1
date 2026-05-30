$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$LogDir = Join-Path $RepoRoot ".runtime-logs"

if (-not (Test-Path $LogDir)) {
    Write-Host "No .runtime-logs directory found. Nothing to stop."
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
}

function Stop-ProjectProcessPattern {
    param([string]$Pattern)
    Get-CimInstance Win32_Process |
        Where-Object {
            $_.CommandLine -and
            $_.CommandLine -match [regex]::Escape($RepoRoot) -and
            $_.CommandLine -match $Pattern
        } |
        ForEach-Object {
            Write-Host "Stopping project process. PID=$($_.ProcessId)"
            & taskkill.exe /PID $_.ProcessId /T /F 2>$null | Out-Null
        }
}

function Stop-PortListener {
    param([int]$Port)
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object {
            Write-Host "Stopping listener on port $Port. PID=$($_.OwningProcess)"
            & taskkill.exe /PID $_.OwningProcess /T /F 2>$null | Out-Null
        }
}

Get-ChildItem -Path $LogDir -Filter "*.pid" | ForEach-Object {
    $Name = $_.BaseName
    $PidText = (Get-Content $_.FullName -Raw).Trim()
    if (-not $PidText) {
        Remove-Item -LiteralPath $_.FullName -Force
        return
    }

    $Process = Get-Process -Id ([int]$PidText) -ErrorAction SilentlyContinue
    if ($Process) {
        Write-Host "Stopping $Name. PID=$PidText"
        & taskkill.exe /PID $Process.Id /T /F 2>$null | Out-Null
    }
    Remove-Item -LiteralPath $_.FullName -Force
}

Stop-ProjectProcessPattern -Pattern "uvicorn|app\.main:app"
Stop-ProjectProcessPattern -Pattern "celery|celery_app"
Stop-ProjectProcessPattern -Pattern "vite|npm.*--prefix.*frontend"
Stop-PortListener -Port 8000
5173..5199 | ForEach-Object { Stop-PortListener -Port $_ }

Write-Host "Stopped local processes recorded by start-dev.ps1."
Write-Host "Docker services were not stopped."
Write-Host "To stop Docker services: docker compose stop postgres redis qdrant"
