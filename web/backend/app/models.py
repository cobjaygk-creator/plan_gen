"""SQLAlchemy models — users (self-managed accounts, admin-created via
create_user.py, no public signup) and generations (one row per
request.xlsx -> .pptx run, mirrors the "생성 이력" screen)."""
import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """SQLite는 tzinfo를 저장하지 않아 UTC로 넣은 값이 naive로 돌아온다. 그러면 API가
    '+00:00' 없이 내려가 브라우저가 UTC 값을 현지 시각으로 읽어 한국에서 9시간 늦게 보인다."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


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
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_utcnow)

    generations: Mapped[list["Generation"]] = relationship(back_populates="user")


class AccessLog(Base):
    """One row per successful login. 실제로는 관리자 계정 하나만 로그인하는
    시스템(업계동향/타사 이벤트/타사 사이트는 로그인 없이 공개 이용) —
    일반 방문 통계는 SiteVisit이 담당하고, 이건 그 드문 관리자 로그인
    자체의 기록으로 남겨둔다."""
    __tablename__ = "access_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    email: Mapped[str] = mapped_column(String(255))  # 탈퇴 계정이어도 기록은 그대로 읽히도록 비정규화
    ip_address: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_utcnow)


class SiteVisit(Base):
    """One row per real page load of the public site (업계동향/타사 이벤트/
    타사 사이트 등 — 로그인 없이 이용되는 시스템이라 실제 방문 통계는
    로그인이 아니라 이걸로 잡는다). main.py의 SPA 캐치올 라우트가 index.html
    을 내려줄 때만(정적 파일 자체를 서빙하는 경우 제외) 기록한다 — 리액트
    라우터가 화면 안에서 처리하는 탭 전환은 서버 요청 자체가 없어 잡히지
    않고, 새 탭/새로고침/직접 URL 접근 같은 진짜 접속만 잡힌다."""
    __tablename__ = "site_visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ip_address: Mapped[str] = mapped_column(String(64))
    path: Mapped[str] = mapped_column(String(500))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_utcnow)


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
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    user: Mapped["User"] = relationship(back_populates="generations")


class WireframeGeneration(Base):
    __tablename__ = "wireframe_generations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    source_filename: Mapped[str] = mapped_column(String(255))
    page_id: Mapped[str] = mapped_column(String(120))
    page_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(nullable=True)
    output_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class WireframeEdit(Base):
    """퀵 프로토타입 결과에 대한 사용자 수정 목록(JSON). 원본 파일은 그대로 두고 수정만 따로 보관한다."""

    __tablename__ = "wireframe_edits"

    record_id: Mapped[int] = mapped_column(ForeignKey("wireframe_generations.id"), primary_key=True)
    patches: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_utcnow)
