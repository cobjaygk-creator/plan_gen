# plan_gen backend (FastAPI)

인증 + 요청서 업로드/생성/진행상황/다운로드까지 구현되어 있고, 프론트엔드까지
포함해서 **팀 배포 없이 본인 PC에서만 쓰는 용도로 완성된 상태**입니다
(사내 서버 배포는 필요 시 나중에 별도로).

## 설치
```
.venv\Scripts\python.exe -m pip install -r web/backend/requirements.txt
```

## .env
루트 `.env`에 `SESSION_SECRET_KEY`가 이미 채워져 있습니다 (없다면
`python -c "import secrets; print(secrets.token_hex(32))"`로 생성해서 추가).

## 계정 생성 (자체 회원가입 없음 — 관리자가 직접 생성)
```
.venv\Scripts\python.exe web/backend/create_user.py <이메일> <비밀번호> <이름>
```

## 평소 실행 (권장) — 백엔드 하나로 화면+API 전부
```
powershell -ExecutionPolicy Bypass -File web/run_local.ps1
```
`http://localhost:8000`에서 로그인부터 다운로드까지 전부 됩니다. 이 스크립트가
프론트엔드를 빌드하고 `web/frontend/dist`를 FastAPI가 직접 서빙하도록
`app/main.py`에 구성돼 있어서, 프로세스 하나만 띄우면 됩니다.

## 개발 중 (프론트 코드를 수정할 때만)
HMR(자동 새로고침)이 필요하면 백엔드/프론트를 따로 띄우세요:
```
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --app-dir web/backend --port 8000
```
그리고 별도 터미널에서 `web/frontend/README.md`대로 `npm run dev` (5173 포트,
`/auth` `/generations` `/health`를 8000으로 프록시).

## 엔드포인트
- `POST /auth/login` — `{"email": ..., "password": ...}` → 세션 쿠키 발급
- `POST /auth/logout`
- `GET /auth/me` — 로그인 여부 확인 + 현재 사용자 정보
- `GET /health` — 헬스 체크 (인증 불필요)
- `POST /generations` — request.xlsx 업로드(`multipart/form-data`, 필드명 `file`) + 생성 시작,
  즉시 202 반환하고 파이프라인은 백그라운드에서 실행
- `GET /generations` — 내 생성 이력 목록 (최신순)
- `GET /generations/{id}` — 단건 조회
- `GET /generations/{id}/stream` — SSE로 진행상황 구독 (`step` 1~4, `status`가
  done/error/needs_review 중 하나가 되면 스트림 종료)
- `GET /generations/{id}/download` — 완료된 .pptx 다운로드 (완료 전엔 409)

모든 `/generations/*`는 로그인 필요, 본인 소유 레코드만 조회 가능(타인 것은 404).

## 테스트
```
.venv\Scripts\python.exe -m pytest web/backend/tests/ -q
```
`test_generations.py`는 `tools.pipeline.classify_month`를 모킹해서 실제 Anthropic API를
호출하지 않습니다 — 진짜 API 연동은 서버를 띄워서 직접 확인했습니다 (curl로 로그인 →
업로드 → SSE 스트림 → 다운로드까지 실제 202606 요청서로 검증, 결과물이 python-pptx로
정상적으로 열림).

## 확인한 것
`web/run_local.ps1`로 빌드 후 서버 하나만 띄워서, 브라우저로 `http://localhost:8000`
접속 → 로그인 → 생성 이력(실데이터) 확인, curl로 SPA 클라이언트 라우팅(`/generate`
같은 경로도 index.html로 정상 폴백)·API 경로 우선순위(`/auth/me`가 SPA 폴백에
안 먹힘)·정적 에셋 서빙까지 전부 실제로 검증.

## 다음 단계
지금은 필요 없지만, 나중에 팀 배포가 필요해지면 아키텍처 설계 문서의 6단계
(Nginx + systemd/Docker, 사내 서버 상시 배포)를 진행하면 됩니다.

## Industry Brief — RSS 수집 (Phase 2)
`app/industry_brief/`에 격리된 별도 기능. `User`/`Generation`과 같은 SQLite 파일을
쓰지만(같은 `Base`) 코드/모델은 완전히 분리돼 있습니다.

```
.venv\Scripts\python.exe web/backend/industry_brief_collect.py
```
`app/industry_brief/sources.py`에 등록된 소스(RSS 실존 확인된 것만) 각각에서 기사를
가져와 URL 기준 중복 제거 후 저장합니다. 아직 스케줄러 없음 — 수동 실행. AI 분류/중요도
평가는 Phase 3, 대시보드 연동(`GET /industry-brief/latest`)은 그 이후.

**실제로 돌려서 확인한 것**: 소스 7개 중 6개 정상 수집(1,320건), TechCrunch는 그쪽 서버
인증서 만료로 실패(코드 문제 아님, 다른 소스에 영향 없이 개별 에러로 격리됨 확인). 같은
스크립트를 두 번째 실행하니 신규 0건·전부 중복으로 잡혀서 URL 중복 제거가 실제로 동작하는
것도 확인. 참고로 OpenAI 피드는 최신 글만이 아니라 전체 아카이브(1,115건)를 반환해서,
Phase 3에서 브리핑 만들 때는 `published_at` 기준으로 최근 것만 걸러써야 합니다.

게임메카/디스이즈게임/Anthropic 등 스펙에 있던 다른 소스는 공식 RSS를 못 찾아서 아직
목록에 없습니다 (`sources.py` 주석 참고).
