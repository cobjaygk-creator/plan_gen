# OCI 배포 — 최초 설정 가이드

목표: `master`에 push하면 GitHub Actions가 프런트엔드를 빌드하고, OCI
인스턴스에 코드+빌드 결과물을 올린 뒤 서비스를 재시작한다. 도쿄 리전의
Ampere A1(ARM, 무료)이 재고 부족으로 계속 생성 실패해서, **x86 Always
Free 셰이프(VM.Standard.E2.1.Micro, RAM 1GB)** 로 전환했다 — RAM이 작아
프런트엔드 빌드는 서버가 아니라 GitHub Actions에서 하고, 빌드 결과물만
rsync로 올린다.

아래 단계 중 OCI 콘솔·GitHub 시크릿 등록은 브라우저 로그인이 필요해 이
세션이 직접 할 수 없으므로, 사용자가 직접 진행해야 한다. 그 외(서버
프로비저닝 스크립트, systemd, GitHub Actions 워크플로)는 이미 준비돼
있다.

## 0. 이미 준비된 것

- SSH 키페어 생성 완료 (이 컴퓨터의 `~/.ssh/oci_uxui/uxui_deploy`,
  `uxui_deploy.pub`) — 아래 공개키를 인스턴스 생성 시 그대로 붙여넣으면 된다.
- `web/backend/deploy/setup_server.sh` — 서버 최초 세팅(파이썬만 설치,
  systemd 등록 — git/Node는 필요 없음)
- `web/backend/deploy/deploy.sh` — rsync로 코드가 올라온 뒤 서버에서
  실행되는 마무리 스크립트(venv/의존성 갱신 + 서비스 재시작)
- `.github/workflows/deploy-oci.yml` — push 시 프런트엔드 빌드 →
  rsync 업로드 → deploy.sh 원격 실행까지 전부 자동화

## 1. OCI 콘솔에서 인스턴스 생성 (사용자가 직접)

Compute → Instances → **Create instance**

- **이름**: `uxui-backend`
- **Image and shape**: Ubuntu 24.04 (x86_64), Shape를 **VM.Standard.E2.1.Micro**
  로 변경(Always Free 자격 표시 확인). Ampere A1이 재고 부족으로 계속
  실패했기 때문에 이 셰이프로 진행한다.
- **Networking**: 기존 VCN **uxui-vcn** 선택, 서브넷 **uxui-public-subnet**,
  "퍼블릭 IPv4 주소" = 예(자동 할당).
- **Add SSH keys**: "Paste public keys"를 선택하고 아래 공개키를 그대로
  붙여넣기:

  ```
  ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIG2qEVjd1VR7oqGaUDJwPBd8HSNkxZXXbG1wrDt3DRns uxui-deploy
  ```

- **Create** 클릭 후 몇 분 기다렸다가, 인스턴스 상세 페이지에서
  **퍼블릭 IP 주소**를 확인한다.

## 2. 보안 목록(Security List)에 인바운드 규칙 추가 (사용자가 직접)

Networking → Virtual Cloud Networks → **uxui-vcn** → 서브넷
(uxui-public-subnet) → Security Lists → 기본 보안 목록 →
Add Ingress Rules:

- Source CIDR: `0.0.0.0/0`
- IP Protocol: TCP
- Destination Port Range: `8000` (앱이 이 포트로 뜬다)

(SSH용 22번 포트는 OCI가 VCN 생성 마법사에서 기본으로 열어두는 경우가
많다 — 안 열려 있으면 같은 방식으로 22번도 추가한다.)

## 3. 서버 최초 세팅 (터미널에서 — 나에게 IP만 알려주면 내가 대신 SSH로
   실행해줄 수도 있다)

```bash
scp -i ~/.ssh/oci_uxui/uxui_deploy web/backend/deploy/setup_server.sh ubuntu@<PUBLIC_IP>:~/
ssh -i ~/.ssh/oci_uxui/uxui_deploy ubuntu@<PUBLIC_IP> 'bash ~/setup_server.sh'
```

이 단계는 파이썬 설치 + 디렉터리 준비 + systemd 등록만 한다. 실제
코드는 아직 없다 — GitHub Actions가 처음 배포할 때 rsync로 채운다.

## 4. GitHub 저장소 시크릿 등록 (사용자가 직접)

GitHub 저장소 → Settings → Secrets and variables → Actions →
**New repository secret** 3개:

| 이름 | 값 |
|---|---|
| `OCI_HOST` | 인스턴스 퍼블릭 IP |
| `OCI_USER` | `ubuntu` |
| `OCI_SSH_KEY` | `~/.ssh/oci_uxui/uxui_deploy` 파일의 **개인키 전체 내용** (`cat` 결과 그대로) |

## 5. 첫 배포 실행

시크릿까지 등록됐으면, `master`에 아무 커밋이나 push하거나 GitHub
Actions 탭에서 **deploy-oci** 워크플로를 "Run workflow"로 수동 실행한다.
성공하면 서버의 `/opt/uxui/plan_gen`에 코드+빌드 결과물이 올라온다.

## 6. .env 채우기 (사용자가 직접 — API 키는 내가 대신 입력하지 않는다)

```bash
ssh -i ~/.ssh/oci_uxui/uxui_deploy ubuntu@<PUBLIC_IP>
cp /opt/uxui/plan_gen/.env.example /opt/uxui/plan_gen/.env
nano /opt/uxui/plan_gen/.env   # ANTHROPIC_API_KEY / OPENAI_API_KEY / SESSION_SECRET_KEY 채우기
sudo systemctl restart uxui-backend
sudo systemctl status uxui-backend
curl localhost:8000/health
```

브라우저에서 `http://<PUBLIC_IP>:8000` 접속해 뜨는지 확인. 이후로는
`master`에 push할 때마다 자동으로 재배포된다(.env는 rsync에서 제외돼
있어 서버에 그대로 남는다).
