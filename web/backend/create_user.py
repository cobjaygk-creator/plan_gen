"""Admin-only account creation. There is no public signup endpoint (see the
login screen's "관리자에게 초대를 요청하세요" copy) — an admin runs this
script directly on the server instead.

Usage:
    .venv\\Scripts\\python.exe web/backend/create_user.py <email> <password> <name>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import Base, SessionLocal, engine
from app.models import User
from app.security import hash_password


def create_user(email: str, password: str, name: str) -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email).first():
            print(f"이미 존재하는 계정입니다: {email}")
            sys.exit(1)
        user = User(email=email, password_hash=hash_password(password), name=name)
        db.add(user)
        db.commit()
        print(f"계정 생성 완료: {email} ({name})")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("사용법: create_user.py <email> <password> <name>")
        sys.exit(1)
    create_user(sys.argv[1], sys.argv[2], sys.argv[3])
