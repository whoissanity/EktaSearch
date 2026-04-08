param(
  [int]$Port = 8000,
  [switch]$NoReload
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".\venv\Scripts\python.exe")) {
  Write-Host "[backend] creating virtualenv..."
  python -m venv venv
}

Write-Host "[backend] installing/updating dependencies..."
.\venv\Scripts\python -m pip install -r .\requirements.txt | Out-Host

$reloadArg = if ($NoReload) { "" } else { "--reload" }
Write-Host "[backend] starting api on http://127.0.0.1:$Port"
Write-Host "[backend] startup scrape logs will appear as [startup-scrape] ..."

if ([string]::IsNullOrWhiteSpace($reloadArg)) {
  .\venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port $Port
} else {
  .\venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port $Port
}
