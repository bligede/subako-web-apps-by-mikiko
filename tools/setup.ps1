$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Python venv gagal dibuat.' }
    }
    & '.\.venv\Scripts\python.exe' -m pip install -r apps/api/requirements.lock
    if ($LASTEXITCODE -ne 0) { throw 'Instalasi backend gagal.' }
    npm --prefix apps/web ci
    if ($LASTEXITCODE -ne 0) { throw 'Instalasi frontend gagal.' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Build frontend gagal.' }
    Write-Output 'Setup selesai. Jalankan: .\.venv\Scripts\python.exe tools/dev.py --built'
} finally {
    Pop-Location
}
