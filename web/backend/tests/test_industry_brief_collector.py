import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.industry_brief.collector import collect_all
from app.industry_brief.models import Article
from app.industry_brief.sources import SOURCES, Source


def _fake_feed(entries, bozo=False):
    return SimpleNamespace(entries=entries, bozo=bozo, bozo_exception=Exception("bad feed") if bozo else None)


def _entry(title, link, summary="", published=True):
    return {
        "title": title, "link": link, "summary": summary,
        "published_parsed": time.gmtime() if published else None,
    }


SRC = Source("Test Outlet", "https://example.com/feed", "GAME", "media")


def test_verified_samsung_newsroom_rss_is_configured_as_official_ai_source():
    source = next(item for item in SOURCES if item.name == "삼성전자 뉴스룸")
    assert source.feed_url == "https://news.samsung.com/kr/feed/rss"
    assert source.category == "AI"
    assert source.source_type == "official"


def test_collect_stores_new_articles(db_factory):
    db = db_factory()
    feed = _fake_feed([_entry("기사 1", "https://example.com/1"), _entry("기사 2", "https://example.com/2")])
    with patch("app.industry_brief.collector.feedparser.parse", return_value=feed):
        result = collect_all(db, sources=[SRC])

    assert result.total_new == 2
    assert result.sources[0].fetched == 2
    assert result.sources[0].duplicates == 0
    stored = db.query(Article).all()
    assert len(stored) == 2
    assert {a.url for a in stored} == {"https://example.com/1", "https://example.com/2"}
    assert stored[0].category == "GAME"
    assert stored[0].source == "Test Outlet"


def test_collect_dedups_against_existing_db_rows(db_factory):
    db = db_factory()
    db.add(Article(source="Test Outlet", source_type="media", category="GAME", title="기존 기사", url="https://example.com/1"))
    db.commit()

    feed = _fake_feed([_entry("기존 기사", "https://example.com/1"), _entry("새 기사", "https://example.com/2")])
    with patch("app.industry_brief.collector.feedparser.parse", return_value=feed):
        result = collect_all(db, sources=[SRC])

    assert result.total_new == 1
    assert result.sources[0].duplicates == 1
    assert db.query(Article).count() == 2


def test_collect_dedups_within_same_feed(db_factory):
    # a feed listing the same link twice (real-world messiness) must not
    # crash on the url column's unique constraint
    db = db_factory()
    feed = _fake_feed([_entry("기사", "https://example.com/1"), _entry("기사(중복)", "https://example.com/1")])
    with patch("app.industry_brief.collector.feedparser.parse", return_value=feed):
        result = collect_all(db, sources=[SRC])

    assert result.total_new == 1
    assert db.query(Article).count() == 1


def test_collect_skips_entries_without_link_or_title(db_factory):
    db = db_factory()
    feed = _fake_feed([{"title": "제목만 있음", "link": None}, {"title": None, "link": "https://example.com/no-title"}])
    with patch("app.industry_brief.collector.feedparser.parse", return_value=feed):
        result = collect_all(db, sources=[SRC])

    assert result.total_new == 0
    assert db.query(Article).count() == 0


def test_collect_records_error_without_crashing_other_sources(db_factory):
    db = db_factory()
    good_feed = _fake_feed([_entry("기사", "https://example.com/1")])
    other_source = Source("Broken Outlet", "https://broken.example.com/feed", "AI", "media")

    def fake_parse(url):
        if "broken" in url:
            raise ConnectionError("피드 서버에 연결할 수 없음")
        return good_feed

    with patch("app.industry_brief.collector.feedparser.parse", side_effect=fake_parse):
        result = collect_all(db, sources=[SRC, other_source])

    assert result.sources[0].error is None
    assert result.sources[0].new == 1
    assert result.sources[1].error is not None
    assert result.total_new == 1


def test_collect_records_bozo_parse_failure(db_factory):
    db = db_factory()
    feed = _fake_feed([], bozo=True)
    with patch("app.industry_brief.collector.feedparser.parse", return_value=feed):
        result = collect_all(db, sources=[SRC])

    assert result.sources[0].error is not None
    assert result.total_new == 0
