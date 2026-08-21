from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base

def utcnow(): return datetime.now(timezone.utc)

class SentimentPost(Base):
    __tablename__ = "sentiment_checker_posts"
    __table_args__ = (UniqueConstraint("source", "post_id", name="uq_sentiment_source_post"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(40), index=True)
    post_id: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    author_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    url: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    views: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    upvotes: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[str] = mapped_column(String(30), default="OTHER", index=True)
    sentiment: Mapped[str] = mapped_column(String(10), default="NEUTRAL", index=True)
    sentiment_value: Mapped[float] = mapped_column(Float, default=0.0)
    score_eligible: Mapped[bool] = mapped_column(default=True)
    exclusion_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    issue_key: Mapped[str] = mapped_column(String(120), default="OTHER", index=True)
    keywords: Mapped[str] = mapped_column(Text, default="[]")
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class SentimentReference(Base):
    __tablename__ = "sentiment_checker_references"
    id: Mapped[int] = mapped_column(primary_key=True)
    reference_id: Mapped[str] = mapped_column(String(100), unique=True)
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(1000))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SentimentAIAnalysis(Base):
    __tablename__ = "sentiment_checker_ai_analysis"
    id: Mapped[int] = mapped_column(primary_key=True)
    post_db_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    model: Mapped[str] = mapped_column(String(80))
    category: Mapped[str] = mapped_column(String(30))
    sentiment: Mapped[str] = mapped_column(String(10))
    sentiment_value: Mapped[float] = mapped_column(Float)
    score_eligible: Mapped[bool] = mapped_column()
    issue_name: Mapped[str] = mapped_column(String(160))
    keywords: Mapped[str] = mapped_column(Text, default="[]")
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SentimentSnapshot(Base):
    __tablename__ = "sentiment_checker_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    period_hours: Mapped[int] = mapped_column(Integer, default=24)
    post_count: Mapped[int] = mapped_column(Integer, default=0)
    eligible_count: Mapped[int] = mapped_column(Integer, default=0)
    sentiment_score: Mapped[float] = mapped_column(Float, default=50.0)
    positive_count: Mapped[int] = mapped_column(Integer, default=0)
    neutral_count: Mapped[int] = mapped_column(Integer, default=0)
    negative_count: Mapped[int] = mapped_column(Integer, default=0)


class SentimentComment(Base):
    __tablename__ = "sentiment_checker_comments"
    __table_args__ = (UniqueConstraint("post_db_id", "comment_id", name="uq_sentiment_post_comment"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    post_db_id: Mapped[int] = mapped_column(Integer, index=True)
    comment_id: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(40))
    content: Mapped[str] = mapped_column(Text)
    author_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    upvotes: Mapped[int] = mapped_column(Integer, default=0)
    sentiment: Mapped[str] = mapped_column(String(10), default="NEUTRAL")
    sentiment_value: Mapped[float] = mapped_column(Float, default=0.0)
    stance: Mapped[str] = mapped_column(String(10), default="NEUTRAL")
