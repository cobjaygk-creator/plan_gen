import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.industry_brief.classifier import ArticleClassification, classify_pending
from app.industry_brief.models import Article
from tools.ai_client import ClassificationError


def _article(db, title="테스트 기사", url="https://example.com/a", category="GAME", classified=False):
    a = Article(
        source="Test Outlet", source_type="media", category=category, title=title, url=url,
        summary="원본 RSS 요약문",
    )
    if classified:
        from datetime import datetime, timezone
        a.classified_at = datetime.now(timezone.utc)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _fake_classification(**overrides):
    defaults = dict(
        is_relevant=True, category="AI", summary="AI 요약 결과",
        keywords=["AI Agent"], entities=["OpenAI"], importance="high",
    )
    defaults.update(overrides)
    return ArticleClassification(**defaults)


def test_classify_pending_updates_article_fields(db_factory):
    db = db_factory()
    article = _article(db, category="GAME")

    with patch("app.industry_brief.classifier.classify", return_value=_fake_classification()):
        done = classify_pending(db, limit=10)

    assert done == 1
    db.refresh(article)
    assert article.category == "AI"
    assert article.is_relevant is True
    assert article.summary == "AI 요약 결과"
    assert json.loads(article.keywords) == ["AI Agent"]
    assert json.loads(article.entities) == ["OpenAI"]
    assert article.importance_score == 90.0
    assert article.classified_at is not None


def test_classify_pending_skips_already_classified(db_factory):
    db = db_factory()
    _article(db, url="https://example.com/done", classified=True)
    _article(db, url="https://example.com/pending", classified=False)

    with patch("app.industry_brief.classifier.classify", return_value=_fake_classification()) as mock_classify:
        done = classify_pending(db, limit=10)

    assert done == 1
    assert mock_classify.call_count == 1


def test_classify_pending_respects_limit(db_factory):
    db = db_factory()
    for i in range(5):
        _article(db, url=f"https://example.com/{i}")

    with patch("app.industry_brief.classifier.classify", return_value=_fake_classification()):
        done = classify_pending(db, limit=2)

    assert done == 2
    remaining_pending = db.query(Article).filter(Article.classified_at.is_(None)).count()
    assert remaining_pending == 3


def test_classify_pending_leaves_failed_article_still_pending(db_factory):
    db = db_factory()
    article = _article(db)

    with patch("app.industry_brief.classifier.classify", side_effect=ClassificationError("bad response")):
        done = classify_pending(db, limit=10)

    assert done == 0
    db.refresh(article)
    assert article.classified_at is None  # left in the queue, not silently marked done


def test_classify_pending_keeps_original_category_when_ai_says_other(db_factory):
    db = db_factory()
    article = _article(db, category="GAME")

    with patch("app.industry_brief.classifier.classify", return_value=_fake_classification(category="OTHER")):
        classify_pending(db, limit=10)

    db.refresh(article)
    assert article.category == "GAME"  # unchanged, since OTHER isn't a real category to overwrite with
    assert article.is_relevant is True  # is_relevant is still the real filter signal
