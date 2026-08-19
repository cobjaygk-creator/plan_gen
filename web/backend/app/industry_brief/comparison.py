"""Korea vs global topic comparison for the Industry Brief reporting window."""
import json
from collections import Counter
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Article
from .sources import is_korean_source


def _counts_by_region(db: Session, category: str, start: datetime, end: datetime) -> tuple[Counter, Counter, int, int]:
    articles = db.execute(
        select(Article).where(
            Article.category == category,
            Article.is_relevant.is_(True),
            Article.published_at >= start,
            Article.published_at < end,
        )
    ).scalars().all()
    korea, global_ = Counter(), Counter()
    korea_articles = global_articles = 0
    for article in articles:
        target = korea if is_korean_source(article.source) else global_
        if is_korean_source(article.source):
            korea_articles += 1
        else:
            global_articles += 1
        for keyword in json.loads(article.keywords) if article.keywords else []:
            target[keyword] += 1
    return korea, global_, korea_articles, global_articles


def _topics(counter: Counter, other: Counter, limit: int = 3) -> list[dict]:
    return [
        {"topic": topic, "count": count}
        for topic, count in sorted(counter.items(), key=lambda item: (item[1] - other.get(item[0], 0), item[1]), reverse=True)
        if count > other.get(topic, 0)
    ][:limit]


def build_market_comparison(db: Session, period_start: datetime, period_end: datetime) -> list[dict]:
    """Return only observed keyword distribution; no inferred causality."""
    panels = []
    for category, label in (("GAME", "게임"), ("AI", "AI")):
        korea, global_, korea_articles, global_articles = _counts_by_region(db, category, period_start, period_end)
        shared = [
            {"topic": topic, "koreaCount": korea[topic], "globalCount": global_[topic]}
            for topic in (set(korea) & set(global_))
            if korea[topic] + global_[topic] >= 2
        ]
        shared.sort(key=lambda item: item["koreaCount"] + item["globalCount"], reverse=True)
        panels.append({
            "category": category,
            "label": label,
            "koreaArticleCount": korea_articles,
            "globalArticleCount": global_articles,
            "koreaFocus": _topics(korea, global_),
            "globalFocus": _topics(global_, korea),
            "sharedTopics": shared[:3],
        })
    return panels