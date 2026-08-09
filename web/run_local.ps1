# 내 PC에서만 쓰는 로컬 실행 스크립트. 프론트엔드를 프로덕션 빌드해서
# FastAPI 백엔드 프로세스 하나가 API + 화면을 전부 서빙하게 한다 —
# 평소 쓸 땐 npm run dev / uvicorn을 따로 띄울 필요 없이 이 스크립트 하나면 됨.
#
# 사용법: web/run_local.ps1 안에서 실행하거나, 루트에서:
#   powershell -ExecutionPolicy Bypass -File web/run_local.ps1
#
# 프론트엔드 코드를 수정 중이라 HMR(자동 새로고침)이 필요하면 대신
# web/backend/README.md, web/frontend/README.md의 "개발 중" 안내를 따라
# uvicorn --reload와 npm run dev를 각각 따로 띄우세요.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "[1/2] 프론트엔드 빌드 중..."
Push-Location "$root\frontend"
npm run build
Pop-Location

Write-Host "[2/2] 서버 시작 (http://localhost:8000)"
& "$root\..\.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir "$root\backend" --port 8000
