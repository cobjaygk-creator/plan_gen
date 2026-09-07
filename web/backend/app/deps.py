from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .database import get_db
from .models import User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "로그인이 필요합니다.")
    user = db.get(User, user_id)
    if user is None:
        request.session.clear()  # stale session pointing at a deleted account
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "로그인이 필요합니다.")
    return user


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> User | None:
    """업계동향/타사 이벤트/타사 사이트처럼 로그인 없이도 열람 가능한
    엔드포인트용 — 세션이 없거나 만료됐어도 401을 던지지 않고 None을
    돌려준다. 화면 쪽 접근 제어(어떤 메뉴를 보여줄지)는 프런트가 하고,
    여기서는 "로그인 자체를 요구하지 않는다"만 보장한다."""
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    user = db.get(User, user_id)
    if user is None:
        request.session.clear()
    return user
