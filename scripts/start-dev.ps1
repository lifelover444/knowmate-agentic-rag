param(
    [switch]$SkipDocker,
    [switch]$SkipFrontend,
    [switch]$SkipWorker,
    [switch]$NoHiddenWindows
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$LogDir = Join-Path $RepoRoot ".runtime-logs"
$WindowStyle = if ($NoHiddenWindows) { "Normal" } else { "Hidden" }

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
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

function Stop-RecordedProcess {
    param([string]$Name)
    $PidFile = Join-Path $LogDir "$Name.pid"
    if (-not (Test-Path $PidFile)) {
        return
    }
    $PidText = (Get-Content $PidFile -Raw).Trim()
    if ($PidText) {
        $Existing = Get-Process -Id ([int]$PidText) -ErrorAction SilentlyContinue
        if ($Existing) {
            & taskkill.exe /PID $Existing.Id /T /F 2>$null | Out-Null
        }
    }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
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
            & taskkill.exe /PID $_.ProcessId /T /F 2>$null | Out-Null
        }
}

function Stop-PortListener {
    param([int]$Port)
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object {
            & taskkill.exe /PID $_.OwningProcess /T /F 2>$null | Out-Null
        }
}

function Start-DevProcess {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$ArgumentList
    )

    Stop-RecordedProcess -Name $Name
    $Stdout = Join-Path $LogDir "$Name.out.log"
    $Stderr = Join-Path $LogDir "$Name.err.log"
    $Process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $RepoRoot `
        -RedirectStandardOutput $Stdout `
        -RedirectStandardError $Stderr `
        -WindowStyle $WindowStyle `
        -PassThru

    Set-Content -Path (Join-Path $LogDir "$Name.pid") -Value $Process.Id -Encoding ascii
    Write-Host "Started $Name. PID=$($Process.Id). Logs: $Stdout / $Stderr"
}

Set-Location $RepoRoot
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Stop-PortListener -Port 8000
5173..5199 | ForEach-Object { Stop-PortListener -Port $_ }
Stop-ProjectProcessPattern -Pattern "uvicorn|app\.main:app"
Stop-ProjectProcessPattern -Pattern "celery|celery_app"
Stop-ProjectProcessPattern -Pattern "vite|npm.*--prefix.*frontend"

Test-RequiredCommand "python"
Test-RequiredCommand "alembic"
Test-RequiredCommand "npm.cmd"

if (-not $SkipDocker) {
    Test-RequiredCommand "docker"
    Write-Step "Starting PostgreSQL / Redis / Qdrant"
    # Equivalent command: docker compose up -d postgres redis qdrant
    Invoke-CheckedNative -FilePath "docker" -ArgumentList @("compose", "up", "-d", "postgres", "redis", "qdrant")
}

Write-Step "Running database migrations"
# Equivalent command: alembic upgrade head
Invoke-CheckedNative -FilePath "alembic" -ArgumentList @("upgrade", "head")

Write-Step "Starting FastAPI"
# Equivalent command: uvicorn app.main:app --reload
Start-DevProcess `
    -Name "api" `
    -FilePath "python" `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--reload")

if (-not $SkipWorker) {
    Write-Step "Starting Celery Worker"
    # Equivalent command: celery -A app.workers.celery_app:celery_app worker --loglevel=info --pool=solo
    Start-DevProcess `
        -Name "worker" `
        -FilePath "celery" `
        -ArgumentList @("-A", "app.workers.celery_app:celery_app", "worker", "--loglevel=info", "--pool=solo")
}

if (-not $SkipFrontend) {
    Write-Step "Starting Vue frontend"
    # Equivalent command: npm --prefix frontend run dev
    Start-DevProcess `
        -Name "frontend" `
        -FilePath "npm.cmd" `
        -ArgumentList @("--prefix", "frontend", "run", "dev")
}

Write-Host ""
Write-Host "knowmate development stack started." -ForegroundColor Green
Write-Host "  API:      http://127.0.0.1:8000"
Write-Host "  Docs:     http://127.0.0.1:8000/docs"
Write-Host "  Frontend: check .runtime-logs/frontend.out.log for the Vite URL, usually http://127.0.0.1:5173"
Write-Host ""
Write-Host "Stop: double-click stop-dev.bat or run scripts/stop-dev.ps1"
