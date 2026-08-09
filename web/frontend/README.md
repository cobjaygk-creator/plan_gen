# plan_gen frontend (React + Vite + TypeScript)

앞서 만든 와이어프레임을 실제 컴포넌트로 옮긴 것입니다: 로그인, GNB/LNB 앱 셸,
빈 대시보드, 업로드+SSE 진행상황이 있는 기획서 생성 화면, 생성 이력 목록.

**평소 쓸 땐 이 프로젝트를 따로 실행할 필요 없습니다** — `web/run_local.ps1`이
빌드해서 FastAPI 하나로 서빙합니다 (`web/backend/README.md` 참고). 아래는 프론트
코드를 직접 수정하면서 HMR(자동 새로고침)이 필요할 때만 쓰는 개발용 실행 방법입니다.

## 설치 및 실행 (개발용, HMR)
```
cd web/frontend
npm install
npm run dev
```
`http://localhost:5173`에서 열립니다. `vite.config.ts`가 `/auth`, `/generations`,
`/health`를 백엔드(`http://localhost:8000`)로 프록시하므로, 브라우저 입장에서는
전부 같은 origin — CORS 설정이 필요 없고, 세션 쿠키도 그대로 동작합니다. 실제
배포에서도 Nginx가 정적 프론트엔드와 `/auth`·`/generations`를 같은 origin으로
묶을 예정이라 (아키텍처 설계 문서 참고) 동일한 전제가 유지됩니다.

먼저 `web/backend`를 8000 포트로 띄워야 합니다 (`web/backend/README.md` 참고).

## 구조
```
src/
  api/          fetch 래퍼(client.ts) + 타입(types.ts)
  auth/         AuthContext — /auth/me로 세션 확인, login/logout 상태 관리
  components/   AppShell(GNB+LNB), ProtectedRoute
  pages/        LoginPage, DashboardPage, GeneratePage, HistoryPage
```

## 검증한 것
- `npm run build` (tsc + vite build) 정상 통과
- 브라우저로 직접 로그인 → 대시보드 → 생성 이력(실제 백엔드 데이터 표시) 확인
- curl로 Vite 프록시(5173)를 통해 로그인 → 업로드 → **SSE 스트림**(여러 개의
  개별 이벤트로 도착, 버퍼링되지 않음) → 확인. 실제 202603 요청서로 테스트하다
  AI 신뢰도 부족으로 `needs_review` 상태가 되는 실제 케이스도 그대로 재현됨
  (파일 업로드는 이 브라우저 자동화 도구가 네이티브 파일 선택창을 열 수 없어
  UI에서 직접 시연은 못 했지만, 같은 엔드포인트를 curl로 실제 검증함)

## 다음 단계
지금 상태로 본인 PC에서 쓰기엔 완성입니다. 나중에 팀 배포가 필요해지면
Nginx + 프로세스 관리(systemd/Docker) 설정을 추가하면 됩니다.
