[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$backendDirectory = Join-Path $projectRoot "backend"
$frontendDirectory = Join-Path $projectRoot "frontend"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing .venv. Install the backend with: .\.venv\Scripts\python.exe -m pip install -e '.\backend[dev]'"
}

if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) {
    throw "pnpm is not available. Install the repository Node.js and pnpm versions first."
}

if (-not (Test-Path -LiteralPath (Join-Path $frontendDirectory "node_modules"))) {
    throw "Missing frontend dependencies. Run: Set-Location frontend; pnpm install --frozen-lockfile"
}

$backendLogDirectory = Join-Path ([System.IO.Path]::GetTempPath()) "growth-learning"
[System.IO.Directory]::CreateDirectory($backendLogDirectory) | Out-Null
$backendOut = Join-Path $backendLogDirectory "backend.out.log"
$backendError = Join-Path $backendLogDirectory "backend.err.log"

$backend = Start-Process -FilePath $python `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload") `
    -WorkingDirectory $backendDirectory `
    -RedirectStandardOutput $backendOut `
    -RedirectStandardError $backendError `
    -WindowStyle Hidden `
    -PassThru

Write-Host "Backend started at http://localhost:8000 (PID $($backend.Id))."
Write-Host "Backend logs: $backendLogDirectory"
Write-Host "Starting frontend at http://localhost:3000. Press Ctrl+C to stop."

function Stop-ProcessTree {
    param([Parameter(Mandatory = $true)][int]$ProcessId)

    Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcessId" -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-ProcessTree -ProcessId $_.ProcessId }
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

Push-Location $frontendDirectory
try {
    & pnpm dev
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
    Stop-ProcessTree -ProcessId $backend.Id
}
