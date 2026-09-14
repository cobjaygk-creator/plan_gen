from sqlalchemy import select
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import AccessLog, SiteVisit, User
from ..schemas import AccessLogOut, LoginRequest, SiteVisitOut, UserOut
from ..security import verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

_ACCESS_LOG_LIMIT = 200


@router.post("/login", response_model=UserOut)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if user is None or not verify_password(body.password, user.password_hash):
        # same message for "no such account" and "wrong password" — don't
        # leak which one it was
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "이메일 또는 비밀번호가 올바르지 않습니다.")
    request.session["user_id"] = user.id
    db.add(AccessLog(
        user_id=user.id, email=user.email,
        ip_address=request.client.host if request.client else "unknown",
    ))
    db.commit()
    return user


@router.get("/access-logs", response_model=list[AccessLogOut])
def list_access_logs(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.scalars(
        select(AccessLog).order_by(AccessLog.occurred_at.desc()).limit(_ACCESS_LOG_LIMIT)
    ).all()


@router.get("/site-visits", response_model=list[SiteVisitOut])
def list_site_visits(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """로그인 없이 이용되는 시스템의 실제 접속 통계 — main.py의 SPA
    캐치올 라우트가 기록해둔 방문(IP·시간·경로)을 최신순으로 보여준다."""
    return db.scalars(
        select(SiteVisit).order_by(SiteVisit.occurred_at.desc()).limit(_ACCESS_LOG_LIMIT)
    ).all()


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
