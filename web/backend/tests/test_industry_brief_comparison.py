import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.industry_brief.comparison import build_market_comparison
from app.industry_brief.models import Article


def _article(db, source, title, keywords, url):
    now = datetime.now(timezone.utc)
    db.add(Article(
        source=source, source_type="media", category="GAME", title=title, url=url,
        is_relevant=True, published_at=now, classified_at=now,
        keywords=json.dumps(keywords), entities="[]",
    ))
    db.commit()


def test_market_comparison_separates_korean_global_and_shared_topics(db_factory):
    db = db_factory()
    _article(db, "NAVER · game.example", "Korea article", ["Korea focus", "Shared"], "https://example.com/kr")
    _article(db, "PC Gamer", "Global article", ["Global focus", "Shared"], "https://example.com/global")

    panels = build_market_comparison(db, datetime.now(timezone.utc) - timedelta(days=1), datetime.now(timezone.utc) + timedelta(minutes=1))
    game = panels[0]

    assert game["koreaArticleCount"] == 1
    assert game["globalArticleCount"] == 1
    assert game["koreaFocus"] == [{"topic": "Korea focus", "count": 1}]
    assert game["globalFocus"] == [{"topic": "Global focus", "count": 1}]
    assert game["sharedTopics"] == [{"topic": "Shared", "koreaCount": 1, "globalCount": 1}]