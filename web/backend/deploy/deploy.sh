#!/usr/bin/env bash
# OCI 인스턴스에서 실행되는 배포 스크립트 — GitHub Actions(deploy-oci.yml)가
# 코드를 rsync로 이미 올려놓은 뒤 SSH로 이 스크립트만 원격 실행한다.
# 프런트엔드는 CI에서 이미 빌드해서 dist/까지 rsync로 들어와 있으므로,
# 여기서는 서버 쪽(가벼운 파이썬 설치 + 서비스 재시작)만 처리한다 — 1GB
# RAM 인스턴스에서 npm run build를 굳이 돌리지 않기 위함.
set -euo pipefail

REPO_DIR="/opt/uxui/plan_gen"
cd "$REPO_DIR"

echo "==> venv 준비"
if [ ! -d .venv ]; then
  python3.12 -m venv .venv
fi

echo "==> backend deps"
.venv/bin/pip install -q -r web/backend/requirements.txt

echo "==> restart service"
sudo systemctl restart uxui-backend

echo "==> done: $(date -Iseconds)"
