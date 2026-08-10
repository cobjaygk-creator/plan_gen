import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.industry_brief.cluster import cluster_pending
from app.industry_brief.models import Article
from app.industry_brief.trends import compute_daily_trends, new_today, refresh_issue_lifecycles

NOW = datetime(2026, 8, 10, tzinfo=timezone.utc)


def _article(db, keywords, days_ago, category="GAME", url=None, title=None):
    n = db.query(Article).count()
    a = Article(
        source="Test", source_type="media", category=category,
        title=title or f"기사 {n}", url=url or f"https://example.com/{n}",
        is_relevant=True, importance_score=60.0,
        keywords=json.dumps(keywords, ensure_ascii=False), entities=json.dumps([]),
        classified_at=NOW, published_at=NOW - timedelta(days=days_ago),
    )
    db.add(a)
    db.commit()
    return a


def test_new_topic_with_zero_baseline_is_emerging(db_factory):
    db = db_factory()
    _article(db, ["AI Browser"], days_ago=0.1)
    _article(db, ["AI Browser"], days_ago=0.2)

    trends = compute_daily_trends(db, "GAME", NOW)
    trend = next(t for t in trends if t.topic == "AI Browser")

    assert trend.is_new is True
    assert trend.direction == "up"
    assert trend.lifecycle == "EMERGING"
    assert trend.today_count == 2


def test_topic_flat_when_today_matches_baseline_average(db_factory):
    db = db_factory()
    # ~1/day for the last 7 days (baseline), and 1 today
    for d in range(1, 8):
        _article(db, ["Live Service"], days_ago=d + 0.5)
    _article(db, ["Live Service"], days_ago=0.1)

    trends = compute_daily_trends(db, "GAME", NOW)
    trend = next(t for t in trends if t.topic == "Live Service")

    assert trend.direction == "flat"
    assert trend.lifecycle == "STABLE"
    assert trend.is_new is False


def test_topic_growing_when_today_significantly_exceeds_baseline(db_factory):
    db = db_factory()
    for d in range(1, 8):
        _article(db, ["AI Coding"], days_ago=d + 0.5)  # 1/day baseline
    for _ in range(10):
        _article(db, ["AI Coding"], days_ago=0.1)  # 10 today, way above baseline avg (1)

    trends = compute_daily_trends(db, "GAME", NOW)
    trend = next(t for t in trends if t.topic == "AI Coding")

    assert trend.direction == "up"
    assert trend.lifecycle == "GROWING"
    assert trend.is_new is False


def test_topic_declining_when_today_significantly_below_baseline(db_factory):
    db = db_factory()
    for d in range(1, 8):
        for _ in range(3):
            _article(db, ["Web3"], days_ago=d + 0.5)  # 3/day baseline
    # nothing today at all

    trends = compute_daily_trends(db, "GAME", NOW)
    trend = next(t for t in trends if t.topic == "Web3")

    assert trend.direction == "down"
    assert trend.lifecycle == "DECLINING"
    assert trend.today_count == 0


def test_new_today_filters_out_low_count_one_off_mentions(db_factory):
    db = db_factory()
    _article(db, ["Barely Mentioned"], days_ago=0.1)  # only 1 mention today, no baseline
    _article(db, ["AI Browser"], days_ago=0.1)
    _article(db, ["AI Browser"], days_ago=0.2)

    trends = compute_daily_trends(db, "GAME", NOW)
    fresh = new_today(trends, min_count=2)

    topics = {t.topic for t in fresh}
    assert "AI Browser" in topics
    assert "Barely Mentioned" not in topics


def test_categories_are_isolated(db_factory):
    db = db_factory()
    _article(db, ["AI Agent"], days_ago=0.1, category="AI")
    _article(db, ["AI Agent"], days_ago=0.1, category="AI")

    game_trends = compute_daily_trends(db, "GAME", NOW)
    ai_trends = compute_daily_trends(db, "AI", NOW)

    assert "AI Agent" not in {t.topic for t in game_trends}
    assert "AI Agent" in {t.topic for t in ai_trends}


def test_refresh_issue_lifecycles_updates_from_dominant_keyword_trend(db_factory):
    db = db_factory()
    for _ in range(10):
        _article(db, ["AI Coding"], days_ago=0.1)
    cluster_pending(db)  # creates issue(s) from those articles

    updated = refresh_issue_lifecycles(db, NOW)

    assert updated >= 1
    from app.industry_brief.models import Issue
    issue = db.query(Issue).first()
    assert issue.lifecycle == "EMERGING"  # zero baseline for a brand-new topic
