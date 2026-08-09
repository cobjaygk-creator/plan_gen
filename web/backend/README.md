# plan_gen backend (FastAPI)

2단계까지 구현된 상태입니다: 인증 + 요청서 업로드/생성/진행상황/다운로드
(아키텍처 설계 문서의 다음 구현 순서 참고).

## 설치
```
.venv\Scripts\python.exe -m pip install -r web/backend/requirements.txt
```

## .env
루트 `.env`에 다음을 추가하세요 (`.env.example` 참고):
```
SESSION_SECRET_KEY=<python -c "import secrets; print(secrets.token_hex(32))" 로 생성>
```
설정 안 하면 로컬 개발용 기본값으로 동작하지만, 실제 배포 전엔 반드시 설정해야 합니다.

## 계정 생성 (자체 회원가입 없음 — 관리자가 직접 생성)
```
.venv\Scripts\python.exe web/backend/create_user.py <이메일> <비밀번호> <이름>
```

## 서버 실행
```
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --app-dir web/backend --port 8000
```

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

## 다음 단계
React 프론트엔드 — 앞서 만든 와이어프레임을 실제 컴포넌트로 옮기고 이 API에 연결.
