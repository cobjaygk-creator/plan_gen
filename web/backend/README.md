# plan_gen backend (FastAPI)

1단계: 인증만 구현된 상태입니다 (아키텍처 설계 문서의 다음 구현 순서 참고).

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

## 테스트
```
.venv\Scripts\python.exe -m pytest web/backend/tests/ -q
```

## 다음 단계
`tools/pipeline.py`에 진행상황 콜백 훅 추가 → `/generations` 업로드+SSE 진행상황 API.
