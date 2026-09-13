"""SQLAlchemy models — users (self-managed accounts, admin-created via
create_user.py, no public signup) and generations (one row per
request.xlsx -> .pptx run, mirrors the "생성 이력" screen)."""
import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GenerationStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    NEEDS_REVIEW = "needs_review"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    generations: Mapped[list["Generation"]] = relationship(back_populates="user")


class AccessLog(Base):
    """One row per successful login — 관리자 전용 접속 통계 화면이 보여줄
    전부다(접속 시간·IP). 로그인 시점에만 기록하므로 세션이 살아있는 동안의
    개별 페이지 이동까지는 잡지 않는다 — "접속 통계"로 요청받은 범위가
    딱 그 정도였고, 매 요청마다 기록하면 트래픽 대비 테이블만 불필요하게
    커진다."""
    __tablename__ = "access_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    email: Mapped[str] = mapped_column(String(255))  # 탈퇴 계정이어도 기록은 그대로 읽히도록 비정규화
    ip_address: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Generation(Base):
    __tablename__ = "generations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    month: Mapped[str] = mapped_column(String(6))  # e.g. "202606"
    source_filename: Mapped[str] = mapped_column(String(255))
    output_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=GenerationStatus.PENDING.value)
    current_step: Mapped[int] = mapped_column(Integer, default=0)  # 0-4, matches run.py's [n/4] steps
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="generations")
