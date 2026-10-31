$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pidPath = Join-Path $projectRoot '.local\dev-supervisor.pid'
if (-not (Test-Path -LiteralPath $pidPath)) {
    Write-Output 'Tidak ada PID supervisor SUBAKO yang dicatat.'
    exit 0
}
$supervisorId = [int](Get-Content -LiteralPath $pidPath -Raw).Trim()
$processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $supervisorId"
if (-not $processInfo) {
    Write-Output 'Supervisor SUBAKO sudah berhenti.'
    exit 0
}
$expectedPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if ($processInfo.ExecutablePath -ne $expectedPython -or $processInfo.CommandLine -notmatch 'tools[/\\]dev\.py') {
    throw 'PID tidak cocok dengan supervisor SUBAKO dari workspace ini; penghentian ditolak.'
}
& taskkill.exe /PID $supervisorId /T /F
if ($LASTEXITCODE -ne 0) { throw 'Supervisor gagal dihentikan.' }
Remove-Item -LiteralPath $pidPath
Write-Output 'Supervisor SUBAKO dan proses anaknya sudah dihentikan.'
