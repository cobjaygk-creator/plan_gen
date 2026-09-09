#!/usr/bin/env bash
# OCI 인스턴스에서 실행되는 배포 스크립트 — GitHub Actions(deploy-oci.yml)가
# 코드를 rsync로 이미 올려놓은 뒤 SSH로 이 스크립트만 원격 실행한다.
# 프런트엔드는 CI에서 이미 빌드해서 dist/까지 rsync로 들어와 있으므로,
# 여기서는 서버 쪽(가벼운 파이썬 설치 + 서비스 재시작)만 처리한다 — 1GB
# RAM 인스턴스에서 npm run build를 굳이 돌리지 않기 위함.
set -euo pipefail

REPO_DIR="/opt/uxui/plan_gen"
cd "$REPO_DIR"

echo "==> curl 설치 확인"
# 테일즈위버 이벤트 수집이 urllib을 막는 사이트라 curl 서브프로세스로
# 우회하는데(nexon_sample.py의 _fetch_talesweaver_html), 최초 서버
# 세팅(setup_server.sh)에서 curl 없이 만들어진 기존 인스턴스도 있어서
# 배포 때마다 여기서도 확인해둔다(이미 있으면 즉시 끝나 비용 없음).
command -v curl >/dev/null || (sudo apt-get update -y && sudo apt-get install -y curl)

echo "==> 수동 접속용 SSH 공개키 등록 확인"
# GitHub Actions 배포 전용 키(OCI_SSH_KEY)만 살아있고, 사람이 직접 SSH할
# 때 쓰던 개인키(uxui_deploy)가 Cloud Shell 스토리지에서 사라져 접속 불가
# 상태가 됐던 적이 있다 — 이 배포 키로는 여전히 접속되니, 그 통로로 사람용
# 보조 키를 authorized_keys에 등록해둔다(이미 있으면 건너뜀).
MANUAL_ACCESS_KEY="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQClPcZUmKgYjnjNnB/OiRlAh9MtPOzitxfZjm+c5YTCerLDFuifRtaPPEoZhMaSRKTawkIDnU098RBq8zXiqJdXkkZyLaMaQvr5WhNL5WinSgEwNDnVxN3KARY7UVtIQPIUJBNdce7I2hHasJUkqPBCJfXOU168E82JTZ/NVp2sBnHfUl7pjYyYLDEiV+QxWx4rsXoH7KB8mMY3f1+t61G2UHW8rKRw2CLlqdbMn3l/ciurni7Bxp0NNH60hvydKu0eY8majv3mp3Ppx3E3G7nKp11CB/xgBMvUy+Tlz5PdR4EqVKS9vw7MHnRBBqCGfOszxsJjwpgbfv7cfY0OuWddfwilXoKP48xeRzEg8FK6Ye8onOcOc0chYEa9CVg/qvq6Z54iK68+Q1Eyu0eBTwAzavnF1iP6pqrLCz0iDglBQdKw6ErWnlhn13aIVQPJoXwtHLcImdYpcp/Nl1Os9md9j12x+DT7jnCEwErPAAu2o+/6NZSiWheioYEFIs9pE5YbxsPuhS2p5+mBmBSuNC8c54c9ElQLKkV5CkBth19wJkw2aVitxen/dcJDHuJ0ebcLEaxg3Z/Ax12YGIg5uPYcdzK1UeY9Y7u0DOUCwhfkc3uenFtlub3Sj2eKfYZbCpzuItYjHDaTFE17e0coYPcDAsyJ0fQkvuZXZQqEhfjrGw== manual-access-20260909"
mkdir -p ~/.ssh
chmod 700 ~/.ssh
touch ~/.ssh/authorized_keys
grep -qF "$MANUAL_ACCESS_KEY" ~/.ssh/authorized_keys || echo "$MANUAL_ACCESS_KEY" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

echo "==> venv 준비"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

echo "==> backend deps"
# app/main.py -> routers/generations.py -> pipeline_runner.py -> tools/* 가
# 저장소 루트 requirements.txt(openpyxl 등 PPT 파이프라인 의존성)를 필요로
# 한다 — web/backend/requirements.txt만 설치하면 임포트 단계에서 죽는다.
.venv/bin/pip install -q -r requirements.txt -r web/backend/requirements.txt

echo "==> restart service"
sudo systemctl restart uxui-backend

echo "==> done: $(date -Iseconds)"
