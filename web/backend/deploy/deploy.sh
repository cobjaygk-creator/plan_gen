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
  python3 -m venv .venv
fi

echo "==> backend deps"
# app/main.py -> routers/generations.py -> pipeline_runner.py -> tools/* 가
# 저장소 루트 requirements.txt(openpyxl 등 PPT 파이프라인 의존성)를 필요로
# 한다 — web/backend/requirements.txt만 설치하면 임포트 단계에서 죽는다.
.venv/bin/pip install -q -r requirements.txt -r web/backend/requirements.txt

echo "==> 타사 사이트(game_sites) official_sites.json 갱신"
# game_sites/portal_collector.py의 OFFICIAL_PATH는 BENCHMARK_DATA_DIR로
# 옮길 수 없는 고정 경로(DATA_DIR/official_sites.json)라, CI가 커밋해둔
# 최신본을 매 배포마다 그 자리로 복사해준다 — .env의 BENCHMARK_DATA_DIR
# 설정만으로는 이 파일까지 못 옮긴다.
if [ -f web/backend/data/ci/game_sites/official_sites.json ]; then
  cp web/backend/data/ci/game_sites/official_sites.json web/backend/data/official_sites.json
fi

echo "==> restart service"
sudo systemctl restart uxui-backend

echo "==> done: $(date -Iseconds)"
