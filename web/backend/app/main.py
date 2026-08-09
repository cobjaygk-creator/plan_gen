from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from .config import SESSION_COOKIE_NAME, SESSION_MAX_AGE_SECONDS, SESSION_SECRET_KEY
from .database import Base, engine
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


@app.get("/health")
def health():
    return {"ok": True}
