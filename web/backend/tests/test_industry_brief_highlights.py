import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.industry_brief.highlights import (
    DailyHighlights, _CoreIssue, _HighlightsResult, _RecommendedArticle,
    generate_daily_highlights, load_latest_highlights, refresh_and_save_highlights, to_api_dict,
)
from app.industry_brief.models import Article
from tools.ai_client import ClassificationError


def _naver_article(db, i, category="GAME", hours_ago=1):
    a = Article(
        source=f"NAVER · 매체{i}", source_type="media", category=category,
        title=f"기사 제목 {i}", url=f"https://n.news.naver.com/mnews/article/000/{i:07d}",
        summary=f"기사 {i} 요약", collected_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
    )
    db.add(a)
    return a


def _fill(db, count, category="GAME", hours_ago=1):
    for i in range(count):
        _naver_article(db, i, category=category, hours_ago=hours_ago)
    db.commit()


def test_too_few_articles_skips_ai_call(db_factory):
    db = db_factory()
    _fill(db, 3, "GAME")
    with patch("app.industry_brief.highlights.classify") as mock_classify:
        result = generate_daily_highlights(db, "GAME")
    mock_classify.assert_not_called()
    assert result.has_signal is False
    assert result.article_count == 3


def test_articles_outside_24h_window_are_excluded(db_factory):
    db = db_factory()
    _fill(db, 10, "GAME", hours_ago=30)
    with patch("app.industry_brief.highlights.classify") as mock_classify:
        result = generate_daily_highlights(db, "GAME")
    mock_classify.assert_not_called()
    assert result.article_count == 0


def test_generates_issues_and_recommendations_from_model_output(db_factory):
    db = db_factory()
    _fill(db, 6, "GAME")
    fake_result = _HighlightsResult(
        has_signal=True,
        core_issues=[_CoreIssue(title="핵심 이슈", summary="요약", article_indices=[0, 1])],
        recommended=[_RecommendedArticle(index=2, one_line_reason="추천 이유")],
    )
    with patch("app.industry_brief.highlights.classify", return_value=fake_result):
        result = generate_daily_highlights(db, "GAME")
    assert result.has_signal is True
    assert len(result.core_issues) == 1
    assert len(result.core_issues[0].articles) == 2
    assert len(result.recommended) == 1
    assert result.recommended[0].reason == "추천 이유"


def test_model_reports_no_signal(db_factory):
    db = db_factory()
    _fill(db, 10, "AI")
    fake_result = _HighlightsResult(has_signal=False, core_issues=[], recommended=[])
    with patch("app.industry_brief.highlights.classify", return_value=fake_result):
        result = generate_daily_highlights(db, "AI")
    assert result.has_signal is False


def test_classification_error_falls_back_to_no_signal(db_factory):
    db = db_factory()
    _fill(db, 10, "GAME")
    with patch("app.industry_brief.highlights.classify", side_effect=ClassificationError("boom")):
        result = generate_daily_highlights(db, "GAME")
    assert result.has_signal is False


def test_out_of_range_indices_from_model_are_dropped(db_factory):
    db = db_factory()
    _fill(db, 6, "GAME")
    fake_result = _HighlightsResult(
        has_signal=True,
        core_issues=[_CoreIssue(title="이슈", summary="요약", article_indices=[0, 99])],
        recommended=[_RecommendedArticle(index=99, one_line_reason="무효 인덱스")],
    )
    with patch("app.industry_brief.highlights.classify", return_value=fake_result):
        result = generate_daily_highlights(db, "GAME")
    assert len(result.core_issues[0].articles) == 1  # only index 0 survives
    assert result.recommended == []  # index 99 dropped entirely


def test_save_and_load_roundtrip(db_factory):
    db = db_factory()
    _fill(db, 6, "AI")
    fake_result = _HighlightsResult(
        has_signal=True,
        core_issues=[_CoreIssue(title="이슈", summary="요약", article_indices=[0])],
        recommended=[],
    )
    with patch("app.industry_brief.highlights.classify", return_value=fake_result):
        saved = refresh_and_save_highlights(db, "AI")
    loaded = load_latest_highlights(db, "AI")
    assert loaded is not None
    assert loaded.article_count == saved.article_count
    assert loaded.core_issues[0].title == "이슈"


def test_load_latest_returns_none_when_no_snapshot_exists(db_factory):
    db = db_factory()
    assert load_latest_highlights(db, "GAME") is None


def test_to_api_dict_uses_camel_case_keys(db_factory):
    db = db_factory()
    _fill(db, 6, "GAME")
    fake_result = _HighlightsResult(has_signal=True, core_issues=[_CoreIssue(title="이슈", summary="요약", article_indices=[0])], recommended=[])
    with patch("app.industry_brief.highlights.classify", return_value=fake_result):
        highlights = generate_daily_highlights(db, "GAME")
    payload = to_api_dict(highlights, "GAME", datetime.now(timezone.utc))
    assert set(payload.keys()) == {"category", "hasSignal", "articleCount", "generatedAt", "coreIssues", "recommended"}


def test_to_api_dict_placeholder_for_missing_snapshot():
    now = datetime.now(timezone.utc)
    payload = to_api_dict(None, "AI", now)
    assert payload == {"category": "AI", "hasSignal": False, "articleCount": 0, "generatedAt": now.isoformat(), "coreIssues": [], "recommended": []}
