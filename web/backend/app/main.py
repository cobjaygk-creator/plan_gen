from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import SESSION_COOKIE_NAME, SESSION_MAX_AGE_SECONDS, SESSION_SECRET_KEY
from .database import Base, engine
from .industry_brief.routes import router as industry_brief_router
from .routers import auth, generations

Base.metadata.create_all(bind=engine)

app = FastAPI(title="plan_gen API")

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


@app.get("/health")
def health():
    return {"ok": True}


# Single-process local use: once `npm run build` has produced
# web/frontend/dist, serve it from this same FastAPI process instead of
# needing a separate Vite dev server running alongside it. Registered
# after the API routers above, so /auth/*, /generations/*, /health still
# take priority — Starlette matches routes in registration order.
_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="frontend-assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = _FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")
