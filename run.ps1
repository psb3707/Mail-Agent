# mail-agent 로컬 실행 스크립트 (Windows, 지시-018)
# 사용법: .\run.ps1
# 동작: .venv 확인 → .env에서 PORT 로드(기본 8765) → uvicorn 실행
$ErrorActionPreference = "Stop"

if (!(Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[ERROR] .venv가 없습니다. 먼저 설치하세요:"
    Write-Host "  python -m venv .venv"
    Write-Host "  .venv\Scripts\pip install -e ."
    exit 1
}

$port = "8765"
if (Test-Path ".env") {
    $line = Get-Content ".env" | Where-Object { $_ -match "^PORT=" } | Select-Object -First 1
    if ($line) {
        $port = (($line -split "=", 2)[1]).Trim().Trim('"')
    }
}

Write-Host "[RUN] uvicorn app.main:app --port $port --reload (키 없으면 폴백 동작)"
& .venv\Scripts\python.exe -m uvicorn app.main:app --port $port --reload