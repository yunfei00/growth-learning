[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing .venv. Create it with: python -m venv .venv"
}

Push-Location (Join-Path $projectRoot "backend")
try {
    & $python -m ruff check .
    if ($LASTEXITCODE -ne 0) { throw "Backend lint failed." }
    & $python -m ruff format --check .
    if ($LASTEXITCODE -ne 0) { throw "Backend format check failed." }
    & $python -m pytest
    if ($LASTEXITCODE -ne 0) { throw "Backend tests failed." }
}
finally {
    Pop-Location
}

Push-Location (Join-Path $projectRoot "frontend")
try {
    & pnpm test
    if ($LASTEXITCODE -ne 0) { throw "Frontend tests failed." }
    & pnpm lint
    if ($LASTEXITCODE -ne 0) { throw "Frontend lint failed." }
    & pnpm typecheck
    if ($LASTEXITCODE -ne 0) { throw "Frontend typecheck failed." }
    & pnpm build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
}
finally {
    Pop-Location
}
