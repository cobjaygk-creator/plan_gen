import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.industry_brief.models import Article, DailyBrief, Issue, IssueArticle


def _login(client, make_user, email="user@example.com", password="hunter2"):
    make_user(email=email, password=password)
    client.post("/auth/login", json={"email": email, "password": password})


def _seed_brief(db):
    now = datetime.now(timezone.utc)
    issue = Issue(
        category="GAME", title="테스트 이슈", summary="이슈 요약", why_it_matters="중요한 이유",
        importance_score=90.0, confidence="STRONG", lifecycle="GROWING",
        first_seen_at=now, last_seen_at=now,
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)

    article = Article(
        source="Outlet A", source_type="media", category="GAME", title="관련 기사",
        url="https://example.com/1", is_relevant=True, importance_score=90.0,
        keywords="[]", entities="[]", classified_at=now, published_at=now,
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    db.add(IssueArticle(issue_id=issue.id, article_id=article.id))
    db.commit()

    brief = DailyBrief(
        brief_date="2026-08-10", period_start=now - timedelta(days=1), period_end=now,
        article_count=5, issue_count=1,
        game_headline="게임 헤드라인", game_briefing=json.dumps(["문단1"], ensure_ascii=False),
        game_changes=json.dumps([{"direction": "up", "topic": "토픽", "description": "설명"}], ensure_ascii=False),
        game_watchlist=json.dumps([{"topic": "워치", "description": "설명"}], ensure_ascii=False),
        ai_headline="AI 헤드라인", ai_briefing=json.dumps(["문단2"], ensure_ascii=False),
        ai_changes=json.dumps([], ensure_ascii=False), ai_watchlist=json.dumps([], ensure_ascii=False),
        game_ai_analysis=json.dumps(["연결된 신호"], ensure_ascii=False),
        signals=json.dumps([{"topic": "토픽", "direction": "up", "weight": 80}], ensure_ascii=False),
        new_today=json.dumps([], ensure_ascii=False),
        status="ok",
    )
    db.add(brief)
    db.commit()
    return brief, issue


def test_latest_requires_login(client):
    res = client.get("/industry-brief/latest")
    assert res.status_code == 401


def test_latest_returns_404_when_no_brief_exists(client, make_user, db_factory):
    _login(client, make_user)
    res = client.get("/industry-brief/latest")
    assert res.status_code == 404


def test_latest_returns_serialized_brief_matching_frontend_shape(client, make_user, db_factory):
    _login(client, make_user)
    db = db_factory()
    _seed_brief(db)

    res = client.get("/industry-brief/latest")
    assert res.status_code == 200
    body = res.json()

    assert body["briefDate"] == "2026-08-10"
    assert body["game"]["headline"] == "게임 헤드라인"
    assert body["game"]["briefing"] == ["문단1"]
    assert body["game"]["watchList"] == [{"rank": 1, "topic": "워치", "description": "설명"}]
    assert body["ai"]["headline"] == "AI 헤드라인"
    assert body["crossInsight"] == {"hasSignal": True, "summary": ["연결된 신호"]}
    assert body["signals"] == [{"topic": "토픽", "direction": "up", "weight": 80}]
    assert body["newToday"] == []

    assert len(body["issues"]) == 1
    issue_payload = body["issues"][0]
    assert issue_payload["title"] == "테스트 이슈"
    assert issue_payload["importance"] == "높음"
    assert issue_payload["whyItMatters"] == "중요한 이유"
    assert issue_payload["confidence"] == {
        "level": "STRONG", "articleCount": 1, "independentSources": 1, "officialCount": 0,
    }
    assert len(issue_payload["sources"]) == 1
    assert issue_payload["sources"][0]["outlet"] == "Outlet A"


def test_cross_insight_without_signal_reports_has_signal_false(client, make_user, db_factory):
    from app.industry_brief.synthesis import NO_CROSS_SIGNAL_TEXT

    _login(client, make_user)
    db = db_factory()
    brief, _ = _seed_brief(db)
    brief.game_ai_analysis = json.dumps([NO_CROSS_SIGNAL_TEXT], ensure_ascii=False)
    db.commit()

    res = client.get("/industry-brief/latest")
    assert res.json()["crossInsight"]["hasSignal"] is False


def test_issue_missing_why_it_matters_gets_fallback_text(client, make_user, db_factory):
    _login(client, make_user)
    db = db_factory()
    _, issue = _seed_brief(db)
    issue.why_it_matters = None
    db.commit()

    res = client.get("/industry-brief/latest")
    assert res.json()["issues"][0]["whyItMatters"] == "아직 분석되지 않았습니다."
