# UXTLER GitHub Pages 배포

이 배포는 로그인·PPT 생성 기능을 제외하고 업계동향, 이벤트 모음, 사이트 모음만
정적 화면으로 공개한다. 기존 로컬 FastAPI 서비스와 사용자 DB는 변경하지 않는다.

## 최초 설정

1. GitHub 저장소의 **Settings → Pages → Source**에서 `GitHub Actions`를 선택한다.
2. **Settings → Secrets and variables → Actions**에서 `OPENAI_API_KEY`를 등록한다.
   분류·종합을 Anthropic으로 사용할 경우 `ANTHROPIC_API_KEY`도 등록한다.
3. **Actions → UXTLER static benchmark → Run workflow**를 실행한다.

키가 없으면 기존에 저장된 정적 JSON만 빌드하며, 키를 저장한 뒤 다시 실행하면 수집과
분석을 수행한다. 예약 실행은 6시간 간격(UTC 기준 약간 지연될 수 있음)이다.

## 데이터 안전

자동 수집 상태는 `static_state.db`라는 별도 SQLite 파일에 저장한다. 기존 `plan_gen.db`,
사용자 계정, 생성 이력은 정적 배포에 포함하지 않는다. 페이지는 공개 URL이므로 링크를
아는 사람은 누구나 볼 수 있다.

## 로컬 정적 빌드

```powershell
.venv\Scripts\python.exe web/backend/static_export.py
cd web/frontend
$env:VITE_STATIC_SITE="true"
$env:VITE_BASE_PATH="/plan_gen/"
npm run build
```
