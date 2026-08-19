import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.industry_brief.models import Article
from app.industry_brief.naver_news import collect_naver_news


def test_naver_news_stores_original_url_and_deduplicates(db_factory, monkeypatch):
    monkeypatch.setenv("NAVER_CLIENT_ID", "test-id")
    monkeypatch.setenv("NAVER_CLIENT_SECRET", "test-secret")
    db = db_factory()
    items = [{
        "title": "<b>AI</b> game launch", "description": "A <b>summary</b>",
        "originallink": "https://publisher.example/article/1", "link": "https://n.news.naver.com/x",
        "pubDate": "Mon, 10 Aug 2026 10:00:00 +0900",
    }]
    with patch("app.industry_brief.naver_news._fetch", return_value=items):
        result = collect_naver_news(db, queries=[("AI game", "GAME")])

    assert result.error is None
    assert result.new == 1
    article = db.query(Article).one()
    assert article.url == "https://publisher.example/article/1"
    assert article.title == "AI game launch"
    assert article.summary == "A summary"
    assert article.source == "NAVER · publisher.example"

    with patch("app.industry_brief.naver_news._fetch", return_value=items):
        second = collect_naver_news(db, queries=[("AI game", "GAME")])
    assert second.new == 0
    assert second.duplicates == 1


def test_naver_news_reports_missing_credentials(db_factory, monkeypatch):
    monkeypatch.delenv("NAVER_CLIENT_ID", raising=False)
    monkeypatch.delenv("NAVER_CLIENT_SECRET", raising=False)
    result = collect_naver_news(db_factory(), queries=[])
    assert result.error is not None