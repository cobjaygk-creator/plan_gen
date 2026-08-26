"""Article storage (design doc section 28's `articles` table). Deliberately
its own module, not added to app/models.py, so User/Generation stay
untouched by anything Industry Brief does — per the "기존 기능과 강하게
결합하지 않는다" principle."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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


class IssueFeedback(Base):
    """Team editorial feedback; isolated from plan-generation models."""
    __tablename__ = "industry_brief_issue_feedback"
    __table_args__ = (UniqueConstraint("issue_id", "user_id", "verdict", name="uq_industry_issue_feedback"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("industry_brief_issues.id"), index=True)
    user_id: Mapped[int] = mapped_column(Integer)
    verdict: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class EditorialRule(Base):
    """Human-approved plain-text rule proposed from repeated feedback."""
    __tablename__ = "industry_brief_editorial_rules"
    __table_args__ = (UniqueConstraint("pattern", "reason", name="uq_industry_editorial_rule"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pattern: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    created_by: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class EditorialRuleAudit(Base):
    """Append-only history of human changes to an editorial rule."""
    __tablename__ = "industry_brief_editorial_rule_audits"

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("industry_brief_editorial_rules.id"), index=True)
    action: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[int] = mapped_column(Integer)
    actor_name: Mapped[str] = mapped_column(String(100))
    actor_email: Mapped[str] = mapped_column(String(255))
    pattern: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(String(30))
    impact_issue_count: Mapped[int] = mapped_column(Integer, default=0)
    impact_article_count: Mapped[int] = mapped_column(Integer, default=0)
    impact_core_count: Mapped[int] = mapped_column(Integer, default=0)
    risk_level: Mapped[str] = mapped_column(String(20), default="SAFE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


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

    game_ai_analysis: Mapped[str] = mapped_column(Text)  # JSON-encoded {"summary": list[str], "opinion": str}

    signals: Mapped[str] = mapped_column(Text)  # JSON
    new_today: Mapped[str] = mapped_column(Text)  # JSON

    status: Mapped[str] = mapped_column(String(20), default="ok")  # "ok" | "stale" (see synthesis.py)

class ReferenceArticle(Base):
    """A historical article deliberately shared by the planning team.

    Kept separate from RSS articles: this is the team’s editorial baseline,
    not a second feed that should inflate today’s article count.
    """
    __tablename__ = "industry_brief_reference_articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    curator: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_domain: Mapped[str] = mapped_column(String(20), default="GAME")
    secondary_domains: Mapped[str] = mapped_column(Text, default="[]")
    axes: Mapped[str] = mapped_column(Text, default="[]")
    event_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    issue_key: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ArticleAnalysis(Base):
    """Industry-map classification for a live RSS article, isolated from
    Article’s existing Phase 3 fields so the original collector stays stable."""
    __tablename__ = "industry_brief_article_analysis"

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("industry_brief_articles.id"), unique=True, index=True)
    primary_domain: Mapped[str] = mapped_column(String(20))  # GAME | AI | GAME_AI
    secondary_domains: Mapped[str] = mapped_column(Text, default="[]")
    axes: Mapped[str] = mapped_column(Text, default="[]")
    event_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    change_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    impact_scope: Mapped[str | None] = mapped_column(String(20), nullable=True)
    impact_horizon: Mapped[str | None] = mapped_column(String(20), nullable=True)
    structural_impact_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    novelty_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_issue_keys: Mapped[str] = mapped_column(Text, default="[]")
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class IssueHistory(Base):
    """A durable observation of how an Issue changed at a point in time."""
    __tablename__ = "industry_brief_issue_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("industry_brief_issues.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    state: Mapped[str] = mapped_column(String(20))
    before_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    now_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_article_ids: Mapped[str] = mapped_column(Text, default="[]")


class DailyHighlightSnapshot(Base):
    """AI-judged "오늘의 핵심 이슈 + 추천 기사" for one category (see
    highlights.py) — replaces the old cross-verification-gated key summary
    for the rolling-24h "오늘" period. One row per (category, refresh); the
    latest row per category is what the API serves, older rows are kept as
    a simple history rather than overwritten in place."""
    __tablename__ = "industry_brief_highlight_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(10), index=True)  # "GAME" | "AI"
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    has_signal: Mapped[bool] = mapped_column(default=False)
    article_count: Mapped[int] = mapped_column(default=0)
    payload: Mapped[str] = mapped_column(Text)  # JSON-encoded DailyHighlights
