#!/usr/bin/env bash
# 최초 1회, OCI 인스턴스에 SSH로 접속해서 직접 실행하는 서버 세팅 스크립트
# (Ubuntu 24.04, VM.Standard.E2.1.Micro — x86, RAM 1GB 기준).
#
# RAM이 1GB뿐이라 프런트엔드 빌드(npm run build)는 이 서버에서 하지 않는다
# — GitHub Actions가 빌드까지 마친 뒤 결과물을 rsync로 통째로 올린다.
# 그래서 이 서버엔 git도 Node.js도 필요 없고, 파이썬만 있으면 된다.
#
# 사용법:
#   scp -i <private-key> deploy/setup_server.sh ubuntu@<PUBLIC_IP>:~/
#   ssh -i <private-key> ubuntu@<PUBLIC_IP> 'bash ~/setup_server.sh'
set -euo pipefail

REPO_DIR="/opt/uxui/plan_gen"

echo "==> apt 업데이트 및 기본 패키지 (git/Node 없이 파이썬 + rsync만)"
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip rsync

echo "==> 배포 대상 디렉터리 준비 (실제 코드는 GitHub Actions가 rsync로 채운다)"
sudo mkdir -p "$REPO_DIR"
sudo chown -R "$USER":"$USER" /opt/uxui

echo "==> systemd 서비스 등록 (코드가 아직 없어도 등록만 해둔다 — 첫 배포
    전까지는 실행 파일이 없어 시작에 실패하는 게 정상)"
sudo mkdir -p /etc/systemd/system
cat <<'EOF' | sudo tee /etc/systemd/system/uxui-backend.service > /dev/null
[Unit]
Description=UX Insight (plan_gen) FastAPI backend
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/uxui/plan_gen/web/backend
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/uxui/plan_gen/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=3
User=ubuntu

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable uxui-backend

echo "==> 완료. 다음 순서로 진행:"
echo "    1) GitHub Actions에서 이 저장소를 처음 배포(master에 push, 또는"
echo "       workflow_dispatch 수동 실행)해서 $REPO_DIR 에 코드를 채운다."
echo "    2) 그 다음 이 서버에 SSH로 들어가 .env를 직접 채운다:"
echo "       nano $REPO_DIR/.env  (ANTHROPIC_API_KEY / OPENAI_API_KEY / SESSION_SECRET_KEY)"
echo "    3) sudo systemctl restart uxui-backend && sudo systemctl status uxui-backend"
