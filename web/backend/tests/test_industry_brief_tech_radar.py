import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.industry_brief.models import Article
from app.industry_brief.tech_radar import build_tech_radar


def _article(db, title, summary="", category="AI", hours_ago=1):
    a = Article(
        source="NAVER · 매체", source_type="media", category=category,
        title=title, url=f"https://example.com/{hash((title, summary, hours_ago))}",
        summary=summary, collected_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
    )
    db.add(a)
    return a


def _window(db):
    now = datetime.now(timezone.utc)
    return now - timedelta(hours=24), now


def test_tag_with_no_matching_articles_is_omitted(db_factory):
    db = db_factory()
    _article(db, "게임업계 실적 발표")
    db.commit()
    start, end = _window(db)
    radar = build_tech_radar(db, start, end)
    assert radar == []


def test_matched_articles_grouped_under_their_tag(db_factory):
    db = db_factory()
    _article(db, "지푸 GLM-5.2, 앤트로픽 턱밑 추격")
    _article(db, "AI 에이전트, 왜 파일럿 단계를 넘지 못하나")
    _article(db, "AI 에이전트가 업무를 자동화한다")
    db.commit()
    start, end = _window(db)
    radar = build_tech_radar(db, start, end)
    by_key = {item["key"]: item for item in radar}
    assert by_key["model"]["articleCount"] == 1
    assert by_key["agent"]["articleCount"] == 2


def test_sorted_by_article_count_descending(db_factory):
    db = db_factory()
    _article(db, "AI 에이전트 기사 1")
    _article(db, "AI 에이전트 기사 2")
    _article(db, "GPU 가격 인상 소식")
    db.commit()
    start, end = _window(db)
    radar = build_tech_radar(db, start, end)
    assert [item["key"] for item in radar] == ["agent", "gpu"]


def test_articles_outside_window_are_excluded(db_factory):
    db = db_factory()
    _article(db, "AI 에이전트 오래된 기사", hours_ago=48)
    db.commit()
    start, end = _window(db)
    assert build_tech_radar(db, start, end) == []


def test_game_category_articles_are_ignored(db_factory):
    db = db_factory()
    _article(db, "AI 에이전트 게임 소식", category="GAME")
    db.commit()
    start, end = _window(db)
    assert build_tech_radar(db, start, end) == []
