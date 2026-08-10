import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.industry_brief.models import Article, Issue, IssueArticle
from app.industry_brief.synthesis import (
    NO_CROSS_SIGNAL_TEXT,
    NO_DATA_HEADLINE,
    ChangeItemOut,
    CrossInsightOut,
    IssueWhyItem,
    PanelSynthesis,
    WatchItemOut,
    generate_daily_brief,
)
from tools.ai_client import ClassificationError


def _issue(db, category="GAME", title="테스트 이슈", importance=80.0, confidence="STRONG"):
    now = datetime.now(timezone.utc)
    issue = Issue(
        category=category, title=title, summary=f"{title} 요약", importance_score=importance,
        confidence=confidence, lifecycle="GROWING", first_seen_at=now, last_seen_at=now,
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)

    article = Article(
        source="Outlet A", source_type="media", category=category, title=title,
        url=f"https://example.com/{title}-{issue.id}", is_relevant=True,
        importance_score=importance, keywords=json.dumps([], ensure_ascii=False),
        entities=json.dumps([], ensure_ascii=False), classified_at=now, published_at=now,
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    db.add(IssueArticle(issue_id=issue.id, article_id=article.id))
    db.commit()
    return issue


def _fake_panel(issue_ids):
    return PanelSynthesis(
        headline="합성된 헤드라인",
        briefing=["문단 1", "문단 2"],
        changes=[ChangeItemOut(direction="up", topic="토픽", description="설명")],
        watchlist=[WatchItemOut(topic="워치", description="설명")],
        issue_why=[IssueWhyItem(issue_id=i, why_it_matters=f"이슈 {i}가 중요한 이유") for i in issue_ids],
    )


def _classify_by_schema(panel_return, cross_return):
    def _fake(system_prompt, user_prompt, schema_model, model, provider=None):
        if schema_model is PanelSynthesis:
            return panel_return
        if schema_model is CrossInsightOut:
            return cross_return
        raise AssertionError(f"unexpected schema_model: {schema_model}")
    return _fake


def test_no_issues_in_either_category_uses_fallback_without_ai_call(db_factory):
    db = db_factory()

    with patch("app.industry_brief.synthesis.classify") as mock_classify:
        brief = generate_daily_brief(db)

    assert mock_classify.call_count == 0
    assert brief.game_headline == NO_DATA_HEADLINE
    assert brief.ai_headline == NO_DATA_HEADLINE
    assert json.loads(brief.game_ai_analysis) == [NO_CROSS_SIGNAL_TEXT]
    assert brief.issue_count == 0


def test_issues_present_synthesizes_panel_and_backfills_why_it_matters(db_factory):
    db = db_factory()
    game_issue = _issue(db, category="GAME", title="게임 이슈")

    fake = _classify_by_schema(
        panel_return=_fake_panel([game_issue.id]),
        cross_return=CrossInsightOut(has_signal=False, summary=[]),
    )
    with patch("app.industry_brief.synthesis.classify", side_effect=fake):
        brief = generate_daily_brief(db)

    assert brief.game_headline == "합성된 헤드라인"
    assert json.loads(brief.game_briefing) == ["문단 1", "문단 2"]
    changes = json.loads(brief.game_changes)
    assert changes == [{"direction": "up", "topic": "토픽", "description": "설명"}]
    # AI side had no issues, so it must stay the fixed fallback and not call the AI for it
    assert brief.ai_headline == NO_DATA_HEADLINE

    db.refresh(game_issue)
    assert game_issue.why_it_matters == f"이슈 {game_issue.id}가 중요한 이유"


def test_cross_insight_not_requested_when_one_category_has_no_issues(db_factory):
    db = db_factory()
    _issue(db, category="GAME", title="게임만 있음")

    with patch(
        "app.industry_brief.synthesis.classify",
        side_effect=_classify_by_schema(_fake_panel([]), CrossInsightOut(has_signal=True, summary=["안됨"])),
    ) as mock_classify:
        brief = generate_daily_brief(db)

    # only the GAME panel call should have happened — no AI category, so no
    # AI panel call and no cross-insight call either
    assert mock_classify.call_count == 1
    assert json.loads(brief.game_ai_analysis) == [NO_CROSS_SIGNAL_TEXT]


def test_cross_insight_without_signal_falls_back_to_fixed_text_even_if_summary_present(db_factory):
    db = db_factory()
    _issue(db, category="GAME", title="게임 이슈")
    _issue(db, category="AI", title="AI 이슈")

    fake = _classify_by_schema(
        panel_return=_fake_panel([]),
        # has_signal=False but summary is non-empty — must still use the fixed
        # fallback text, not the model's own (unused) summary
        cross_return=CrossInsightOut(has_signal=False, summary=["이건 쓰이면 안됨"]),
    )
    with patch("app.industry_brief.synthesis.classify", side_effect=fake):
        brief = generate_daily_brief(db)

    assert json.loads(brief.game_ai_analysis) == [NO_CROSS_SIGNAL_TEXT]


def test_cross_insight_with_signal_uses_model_summary(db_factory):
    db = db_factory()
    _issue(db, category="GAME", title="게임 이슈")
    _issue(db, category="AI", title="AI 이슈")

    fake = _classify_by_schema(
        panel_return=_fake_panel([]),
        cross_return=CrossInsightOut(has_signal=True, summary=["연결된 신호 설명"]),
    )
    with patch("app.industry_brief.synthesis.classify", side_effect=fake):
        brief = generate_daily_brief(db)

    assert json.loads(brief.game_ai_analysis) == ["연결된 신호 설명"]


def test_ai_failure_falls_back_to_fixed_panel_without_crashing(db_factory):
    db = db_factory()
    game_issue = _issue(db, category="GAME", title="게임 이슈")

    with patch("app.industry_brief.synthesis.classify", side_effect=ClassificationError("boom")):
        brief = generate_daily_brief(db)

    assert brief.game_headline == NO_DATA_HEADLINE
    db.refresh(game_issue)
    assert game_issue.why_it_matters is None  # fallback panel has no issue_why, so nothing overwritten


def test_article_count_only_counts_articles_within_the_period(db_factory):
    db = db_factory()
    now = datetime.now(timezone.utc)
    db.add(Article(
        source="A", source_type="media", category="GAME", title="최근 기사",
        url="https://example.com/recent", is_relevant=True, published_at=now - timedelta(minutes=5),
        classified_at=now, keywords="[]", entities="[]",
    ))
    db.add(Article(
        source="A", source_type="media", category="GAME", title="오래된 기사",
        url="https://example.com/old", is_relevant=True, published_at=now - timedelta(days=10),
        classified_at=now, keywords="[]", entities="[]",
    ))
    db.commit()

    with patch("app.industry_brief.synthesis.classify") as mock_classify:
        brief = generate_daily_brief(db, reference_date=now)

    assert mock_classify.call_count == 0  # no Issues exist, only loose Articles
    assert brief.article_count == 1
