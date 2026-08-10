"""Phase 5: day-over-day topic trends (design doc section 36 "Daily
Intelligence" — Today Changed, New Today, Today's Signals, Lifecycle).

No new persistent table for signals/changes — design doc section 28's
`daily_briefs.signals`/`new_today` are JSON columns, i.e. computed at
brief-generation time and snapshotted, not their own normalized entity.
So this module is pure computation over Article.keywords within time
windows; nothing here writes to the DB except refresh_issue_lifecycles(),
which updates each Issue's own lifecycle field from its dominant topic's
trend (Issue itself IS persisted, from Phase 4).

Threshold-based up/flat/down (spec section 8 explicitly warns: "단순 기사
건수 하나만으로 상승/하락을 판단하지 않는다" — this uses today's count vs a
7-day baseline average, not a single day-to-day delta) is a plain
percentage-change rule, not a real trend model — an intentional MVP
choice, revisit if the categories it produces feel wrong on real data."""
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Article, Issue, IssueArticle

UP_THRESHOLD = 0.3  # +30% vs baseline -> "up"
DOWN_THRESHOLD = -0.3  # -30% vs baseline -> "down"
DEFAULT_BASELINE_DAYS = 7


@dataclass
class TopicTrend:
    topic: str
    category: str
    today_count: int
    baseline_avg: float
    direction: str  # "up" | "flat" | "down"
    lifecycle: str  # "EMERGING" | "GROWING" | "STABLE" | "DECLINING"
    is_new: bool  # zero presence in the baseline window at all


def _topic_counts(db: Session, category: str, start: datetime, end: datetime) -> Counter:
    articles = db.execute(
        select(Article).where(
            Article.category == category,
            Article.is_relevant.is_(True),
            Article.published_at >= start,
            Article.published_at < end,
        )
    ).scalars().all()
    counts: Counter = Counter()
    for article in articles:
        for keyword in json.loads(article.keywords) if article.keywords else []:
            counts[keyword] += 1
    return counts


def _classify(today_count: int, baseline_avg: float) -> tuple[str, str, bool]:
    if baseline_avg <= 0:
        return ("up", "EMERGING", True) if today_count > 0 else ("flat", "STABLE", False)
    pct_change = (today_count - baseline_avg) / baseline_avg
    if pct_change >= UP_THRESHOLD:
        return "up", "GROWING", False
    if pct_change <= DOWN_THRESHOLD:
        return "down", "DECLINING", False
    return "flat", "STABLE", False


def compute_daily_trends(
    db: Session, category: str, reference_date: datetime,
    window_days: int = 1, baseline_days: int = DEFAULT_BASELINE_DAYS,
) -> list[TopicTrend]:
    """reference_date is the end of "today" (exclusive). "Today" is the
    window_days before it; the baseline is the baseline_days immediately
    before that, averaged per window_days-sized period — so a topic with
    zero baseline presence is genuinely new, not just under-sampled."""
    today_start = reference_date - timedelta(days=window_days)
    baseline_start = today_start - timedelta(days=baseline_days)

    today_counts = _topic_counts(db, category, today_start, reference_date)
    baseline_counts = _topic_counts(db, category, baseline_start, today_start)
    baseline_periods = max(1, baseline_days // window_days)

    topics = set(today_counts) | set(baseline_counts)
    trends = []
    for topic in topics:
        today_count = today_counts.get(topic, 0)
        baseline_avg = baseline_counts.get(topic, 0) / baseline_periods
        direction, lifecycle, is_new = _classify(today_count, baseline_avg)
        trends.append(TopicTrend(topic, category, today_count, baseline_avg, direction, lifecycle, is_new))

    trends.sort(key=lambda t: t.today_count, reverse=True)
    return trends


def new_today(trends: list[TopicTrend], min_count: int = 2) -> list[TopicTrend]:
    """Spec section 9: a topic that had zero baseline presence and shows
    up at a *meaningful* level today — min_count filters out one-off
    mentions that technically have no history but aren't really "new"."""
    return [t for t in trends if t.is_new and t.today_count >= min_count]


def refresh_issue_lifecycles(db: Session, reference_date: datetime) -> int:
    """Sets each Issue's lifecycle from its own dominant keyword's trend
    (its member articles' most common keyword). Returns how many issues
    were updated."""
    updated = 0
    for category in ("GAME", "AI"):
        trends_by_topic = {t.topic: t for t in compute_daily_trends(db, category, reference_date)}
        issues = db.execute(select(Issue).where(Issue.category == category)).scalars().all()
        for issue in issues:
            members = db.execute(
                select(Article).join(IssueArticle, IssueArticle.article_id == Article.id)
                .where(IssueArticle.issue_id == issue.id)
            ).scalars().all()
            keyword_counts: Counter = Counter()
            for member in members:
                for keyword in json.loads(member.keywords) if member.keywords else []:
                    keyword_counts[keyword] += 1
            if not keyword_counts:
                continue
            dominant_topic = keyword_counts.most_common(1)[0][0]
            trend = trends_by_topic.get(dominant_topic)
            if trend is not None:
                issue.lifecycle = trend.lifecycle
                updated += 1
    db.commit()
    return updated
