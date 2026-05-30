$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$LogDir = Join-Path $RepoRoot ".runtime-logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Stop-Frontend {
    $PidFile = Join-Path $LogDir "frontend.pid"
    if (-not (Test-Path $PidFile)) {
        return
    }
    $PidText = (Get-Content $PidFile -Raw).Trim()
    if ($PidText) {
        $Process = Get-Process -Id ([int]$PidText) -ErrorAction SilentlyContinue
        if ($Process) {
            Write-Host "Stopping frontend. PID=$PidText"
            & taskkill.exe /PID $Process.Id /T /F 2>$null | Out-Null
        }
    }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
}

function Stop-OldFrontendProcesses {
    Get-CimInstance Win32_Process |
        Where-Object {
            $_.CommandLine -and
            $_.CommandLine -match [regex]::Escape($RepoRoot) -and
            $_.CommandLine -match "vite|npm.*--prefix.*frontend"
        } |
        ForEach-Object {
            Write-Host "Stopping old frontend process. PID=$($_.ProcessId)"
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

if (-not (Get-Command "npm.cmd" -ErrorAction SilentlyContinue)) {
    throw "Missing command: npm.cmd. Install Node.js or add npm to PATH."
}

Set-Location $RepoRoot
Stop-Frontend
Stop-OldFrontendProcesses
5173..5199 | ForEach-Object { Stop-PortListener -Port $_ }

$Stdout = Join-Path $LogDir "frontend.out.log"
$Stderr = Join-Path $LogDir "frontend.err.log"
$Process = Start-Process `
    -FilePath "npm.cmd" `
    -ArgumentList @("--prefix", "frontend", "run", "dev") `
    -WorkingDirectory $RepoRoot `
    -RedirectStandardOutput $Stdout `
    -RedirectStandardError $Stderr `
    -WindowStyle Hidden `
    -PassThru

Set-Content -Path (Join-Path $LogDir "frontend.pid") -Value $Process.Id -Encoding ascii
Start-Sleep -Seconds 3

Write-Host "Frontend restarted. PID=$($Process.Id)"
Write-Host "Logs: $Stdout / $Stderr"
Write-Host "Vite URL:"
Get-Content $Stdout -ErrorAction SilentlyContinue | Select-String -Pattern "Local:" | Select-Object -Last 1
