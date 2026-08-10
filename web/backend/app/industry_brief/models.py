"""Article storage (design doc section 28's `articles` table). Deliberately
its own module, not added to app/models.py, so User/Generation stay
untouched by anything Industry Brief does — per the "기존 기능과 강하게
결합하지 않는다" principle."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Article(Base):
    __tablename__ = "industry_brief_articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(100))
    source_type: Mapped[str] = mapped_column(String(20))  # "media" | "official"
    category: Mapped[str] = mapped_column(String(10))  # "GAME" | "AI"
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(1000), unique=True, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Phase 3 (Article Intelligence) — null until classify_pending() processes
    # this row; a null classified_at is exactly the "still pending" queue.
    is_relevant: Mapped[bool | None] = mapped_column(nullable=True)
    importance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON-encoded list[str]
    entities: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON-encoded list[str]
    classified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Issue(Base):
    """design doc section 28's `issues` table. why_it_matters is Phase 6
    (AI synthesis) and stays null until then — Phase 4 only clusters."""
    __tablename__ = "industry_brief_issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(10))  # "GAME" | "AI"
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_it_matters: Mapped[str | None] = mapped_column(Text, nullable=True)
    importance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)  # STRONG | MODERATE | WEAK
    lifecycle: Mapped[str] = mapped_column(String(20), default="EMERGING")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class IssueArticle(Base):
    __tablename__ = "industry_brief_issue_articles"

    issue_id: Mapped[int] = mapped_column(ForeignKey("industry_brief_issues.id"), primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("industry_brief_articles.id"), primary_key=True)


class DailyBrief(Base):
    """design doc section 28's `daily_briefs` table. changes/watchList/
    signals/new_today are JSON columns per the spec — computed at
    generation time, not their own normalized entities (see trends.py's
    docstring for why)."""
    __tablename__ = "industry_brief_daily_briefs"

    id: Mapped[int] = mapped_column(primary_key=True)
    brief_date: Mapped[str] = mapped_column(String(10))  # "YYYY-MM-DD"
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    article_count: Mapped[int] = mapped_column(default=0)
    issue_count: Mapped[int] = mapped_column(default=0)

    game_headline: Mapped[str] = mapped_column(Text)
    game_briefing: Mapped[str] = mapped_column(Text)  # JSON-encoded list[str] paragraphs
    game_changes: Mapped[str] = mapped_column(Text)  # JSON
    game_watchlist: Mapped[str] = mapped_column(Text)  # JSON

    ai_headline: Mapped[str] = mapped_column(Text)
    ai_briefing: Mapped[str] = mapped_column(Text)
    ai_changes: Mapped[str] = mapped_column(Text)
    ai_watchlist: Mapped[str] = mapped_column(Text)

    game_ai_analysis: Mapped[str] = mapped_column(Text)  # JSON-encoded list[str] paragraphs

    signals: Mapped[str] = mapped_column(Text)  # JSON
    new_today: Mapped[str] = mapped_column(Text)  # JSON

    status: Mapped[str] = mapped_column(String(20), default="ok")  # "ok" | "stale" (see synthesis.py)
