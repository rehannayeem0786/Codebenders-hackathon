# SchemeSetu - one-command start (Windows PowerShell)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[setup] created .env from .env.example" -ForegroundColor Yellow
}

Write-Host "[setup] installing dependencies (fastapi, uvicorn, dotenv, networkx, httpx)" -ForegroundColor Cyan
python -m pip install -q -r requirements.txt

Write-Host "[run] starting SchemeSetu on http://127.0.0.1:8000" -ForegroundColor Green
python run.py
