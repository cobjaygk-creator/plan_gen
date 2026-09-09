from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import SESSION_COOKIE_NAME, SESSION_MAX_AGE_SECONDS, SESSION_SECRET_KEY
from .database import Base, engine
from .media_cache import THUMBNAIL_DIR
from .industry_brief.routes import router as industry_brief_router
from .industry_brief.scheduler import start_daily_refresh_scheduler
from .event_bench.routes import router as event_bench_router
from .preregistration.routes import router as preregistration_router
from .game_sites.routes import router as game_sites_router
from .sentiment_checker.routes import router as sentiment_checker_router
from .routers import auth, generations

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def _lifespan(_: FastAPI):
    # 업계동향: 매일 오전 7시(KST) 자동 갱신, 그 전까지는 이전 스냅샷 유지.
    start_daily_refresh_scheduler()
    yield


app = FastAPI(title="UX Insight API", lifespan=_lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    session_cookie=SESSION_COOKIE_NAME,
    max_age=SESSION_MAX_AGE_SECONDS,
    same_site="lax",
    https_only=False,  # flip to True once served behind HTTPS in production
)

app.include_router(auth.router)
app.include_router(generations.router)
app.include_router(industry_brief_router)
app.include_router(event_bench_router)
app.include_router(preregistration_router)
app.include_router(game_sites_router)
app.include_router(sentiment_checker_router)


@app.get("/health")
def health():
    return {"ok": True}


# Single-process local use: once `npm run build` has produced
# web/frontend/dist, serve it from this same FastAPI process instead of
# needing a separate Vite dev server running alongside it. Registered
# after the API routers above, so /auth/*, /generations/*, /health still
# take priority — Starlette matches routes in registration order.
# 캐시된 썸네일 전용 마운트 — web/frontend/dist(매 배포마다 CI에서 새로
# 빌드해 통째로 덮어씀)가 아니라 배포 rsync에서 제외되는 영속 디렉터리
# (web/backend/data/thumbnails/)에서 직접 서빙한다. 예전엔 dist 밑에
# 캐싱했었는데, 그러면 서버가 방금 캐싱한 썸네일이 다음 배포 때마다
# 사라지는 문제가 실제로 있었다(이터널 리턴/어둠의전설에서 확인).
THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/data/thumbnails", StaticFiles(directory=THUMBNAIL_DIR), name="thumbnails")

_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="frontend-assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = _FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")
