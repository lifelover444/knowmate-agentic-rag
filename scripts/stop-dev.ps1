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

function Stop-KnowmatePythonProcessPattern {
    param([string]$Pattern)
    Get-CimInstance Win32_Process |
        Where-Object {
            $_.CommandLine -and
            $_.CommandLine -match $Pattern
        } |
        ForEach-Object {
            Write-Host "Stopping Knowmate local Python process. PID=$($_.ProcessId)"
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
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

function Test-RequiredCommand {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing command: $Name. Install it or add it to PATH."
    }
}

function Invoke-CheckedNative {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList
    )
    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE`: $FilePath $($ArgumentList -join ' ')"
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
Stop-KnowmatePythonProcessPattern -Pattern "uvicorn.*app\.main:app|app\.main:app.*uvicorn"
Stop-KnowmatePythonProcessPattern -Pattern "app\.workers\.celery_app:celery_app|celery_app"
Stop-ProjectProcessPattern -Pattern "vite|npm.*--prefix.*frontend"
5173..5199 | ForEach-Object { Stop-PortListener -Port $_ }

Test-RequiredCommand "docker"
Write-Host "Stopping Docker Compose backend stack."
# Equivalent command: docker compose stop api worker postgres redis qdrant
Invoke-CheckedNative -FilePath "docker" -ArgumentList @("compose", "stop", "api", "worker", "postgres", "redis", "qdrant")

Write-Host "Stopped local processes recorded by start-dev.ps1."
Write-Host "Stopped Docker Compose backend services."
