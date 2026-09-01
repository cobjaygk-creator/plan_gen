import json
import sys
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.industry_brief.models import Article, DailyBrief, EditorialRule, Issue, IssueArticle, IssueFeedback
from app.industry_brief.routes import _period_key_summary_details, _period_ranked_issues


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
        game_changes=json.dumps([{
            "direction": "up", "topic": "토픽", "description": "설명",
            "evidence_issue_ids": [issue.id],
        }], ensure_ascii=False),
        game_watchlist=json.dumps([{
            "topic": "워치", "description": "설명", "evidence_issue_ids": [issue.id],
        }], ensure_ascii=False),
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
    assert body["generatedAt"].endswith("+00:00")
    assert body["game"]["headline"] == "교차 확인된 핵심 이슈가 아직 없습니다."
    assert body["game"]["keySummaries"] == ["교차 확인된 핵심 이슈가 아직 없습니다."]
    assert body["game"]["keySummaryDetails"][0]["articleCount"] == 1
    assert body["game"]["observations"] == []
    assert body["game"]["promotions"] == []
    assert body["game"]["closedObservations"] == []
    assert "관찰 후보 1건" in body["game"]["keySummaryDetails"][0]["selectionReason"]
    assert body["game"]["briefing"] == ["교차 확인된 핵심 이슈가 아직 없습니다."]
    assert body["game"]["watchList"] == []
    assert body["game"]["changes"][0]["sources"][0]["title"] == "관련 기사"
    assert body["ai"]["headline"] == "교차 확인된 핵심 이슈가 아직 없습니다."
    assert body["ai"]["keySummaries"] == ["교차 확인된 핵심 이슈가 아직 없습니다."]
    assert body["ai"]["observations"] == []
    assert body["ai"]["promotions"] == []
    assert body["ai"]["closedObservations"] == []
    assert body["crossInsight"]["hasSignal"] is False
    assert body["crossInsight"]["opinion"]
    assert body["signals"][0]["topic"] == "테스트 이슈"
    assert body["signals"][0]["todayCount"] == 1
    assert body["newToday"] == []
    assert body["policyUpdates"] == []
    assert body["policyTimeline"] == []
    assert body["analytics"]["interest"]["series"][0]["name"] == "테스트 이슈"
    assert body["analytics"]["interest"]["series"][0]["originalTitle"] == "테스트 이슈"
    assert len(body["analytics"]["interest"]["labels"]) == 31
    assert "topicShare" not in body["analytics"]

    assert len(body["issues"]) == 1
    issue_payload = body["issues"][0]
    assert issue_payload["title"] == "테스트 이슈"
    assert issue_payload["importance"] == "높음"
    assert issue_payload["whyItMatters"] == "중요한 이유"
    assert issue_payload["confidence"] == {
        "level": "WEAK", "articleCount": 1, "independentSources": 1, "officialCount": 0,
    }
    assert len(issue_payload["sources"]) == 1
    assert issue_payload["sources"][0]["outlet"] == "Outlet A"


def test_latest_excludes_issues_outside_brief_period(client, make_user, db_factory):
    _login(client, make_user)
    db = db_factory()
    brief, issue = _seed_brief(db)
    article = db.query(Article).one()
    article.published_at = brief.period_start - timedelta(seconds=1)
    db.commit()

    res = client.get("/industry-brief/latest")

    assert res.status_code == 200
    assert res.json()["issues"] == []


def test_period_tab_reads_stored_data_without_creating_brief(client, make_user, db_factory):
    _login(client, make_user)
    db = db_factory()
    _seed_brief(db)
    before = db.query(DailyBrief).count()

    res = client.post("/industry-brief/period/3d")

    assert res.status_code == 200
    assert res.json()["periodLabel"] == "최근 3일"
    assert db.query(DailyBrief).count() == before


def test_day_endpoint_reads_stored_data_without_creating_brief(client, make_user, db_factory):
    _login(client, make_user)
    db = db_factory()
    _seed_brief(db)
    before = db.query(DailyBrief).count()

    res = client.post("/industry-brief/day/2026-08-10")

    assert res.status_code == 200
    assert res.json()["periodLabel"] == "2026-08-10"
    assert db.query(DailyBrief).count() == before


def test_day_endpoint_rejects_malformed_date(client, make_user, db_factory):
    _login(client, make_user)
    db_factory()
    res = client.post("/industry-brief/day/not-a-date")
    assert res.status_code == 422


def test_day_endpoint_404s_when_no_brief_exists(client, make_user, db_factory):
    _login(client, make_user)
    db_factory()
    res = client.post("/industry-brief/day/2026-08-10")
    assert res.status_code == 404


def test_day_highlights_placeholder_when_nothing_generated_that_day(client, make_user, db_factory):
    _login(client, make_user)
    db_factory()
    res = client.get("/industry-brief/highlights/day/2026-08-10")
    assert res.status_code == 200
    body = res.json()
    assert body["game"]["hasSignal"] is False
    assert body["game"]["articleCount"] == 0
    assert body["ai"]["hasSignal"] is False


def test_day_highlights_rejects_malformed_date(client, make_user, db_factory):
    _login(client, make_user)
    db_factory()
    res = client.get("/industry-brief/highlights/day/20260810")
    assert res.status_code == 422


def test_period_ranking_attaches_matching_first_party_announcement(db_factory):
    db = db_factory()
    now = datetime.now(timezone.utc)
    media_issue = Issue(
        category="GAME", title="KRAFTON Project Nova launch", summary="launch",
        importance_score=70.0, first_seen_at=now, last_seen_at=now,
    )
    official_issue = Issue(
        category="GAME", title="Project Nova official announcement", summary="launch",
        importance_score=70.0, first_seen_at=now, last_seen_at=now,
    )
    db.add_all([media_issue, official_issue])
    db.flush()
    common = {
        "source_type": "media", "category": "GAME", "is_relevant": True,
        "importance_score": 70.0, "keywords": json.dumps(["launch", "project nova"]),
        "entities": json.dumps(["KRAFTON", "Project Nova"]), "published_at": now,
    }
    media_a = Article(source="NAVER · a.example", title="KRAFTON unveils Project Nova launch", url="https://a.example/nova", **common)
    media_b = Article(source="NAVER · b.example", title="Project Nova launch unveiled by KRAFTON", url="https://b.example/nova", **common)
    official = Article(
        source="NAVER · krafton.com", title="KRAFTON officially announces Project Nova launch",
        url="https://www.krafton.com/news/press/project-nova/", **common,
    )
    db.add_all([media_a, media_b, official])
    db.flush()
    db.add_all([
        IssueArticle(issue_id=media_issue.id, article_id=media_a.id),
        IssueArticle(issue_id=media_issue.id, article_id=media_b.id),
        IssueArticle(issue_id=official_issue.id, article_id=official.id),
    ])
    db.commit()

    ranked = _period_ranked_issues(db, "GAME", now - timedelta(days=1), now + timedelta(minutes=1))
    media_result = next(item for item in ranked if item["issue"].id == media_issue.id)

    assert {article.id for article in media_result["members"]} == {media_a.id, media_b.id, official.id}
    assert media_result["quality"].official_count == 1
    assert media_result["quality"].synthesis_eligible is True
    assert media_result["scoreBreakdown"]["total"] == media_result["score"]
    assert media_result["scoreBreakdown"]["evidence"] == 35.0
    assert set(media_result["scoreBreakdown"]) == {
        "evidence", "coverage", "importance", "persistence", "momentum", "editorialAdjustment", "userFeedback", "approvedRule", "total",
    }


def test_not_core_feedback_excludes_issue_from_key_summary(client, make_user, db_factory):
    _login(client, make_user)
    db = db_factory()
    _, issue = _seed_brief(db)

    response = client.post(f"/industry-brief/issues/{issue.id}/feedback", json={"verdict": "NOT_CORE", "reason": "LOW_IMPACT"})

    assert response.status_code == 200
    assert db.query(IssueFeedback).filter_by(issue_id=issue.id, verdict="NOT_CORE").count() == 1
    now = datetime.now(timezone.utc)
    ranked = _period_ranked_issues(db, "GAME", now - timedelta(days=1), now + timedelta(minutes=1))
    assert ranked[0]["hasNegativeFeedback"] is True
    assert _period_key_summary_details(ranked)[0]["text"] == "교차 확인된 핵심 이슈가 아직 없습니다."

    listed = client.get("/industry-brief/feedback")
    assert listed.status_code == 200
    assert listed.json()[0]["issueId"] == issue.id
    assert listed.json()[0]["feedbackCount"] == 1
    assert listed.json()[0]["reasonCounts"] == {"LOW_IMPACT": 1}

    restored = client.delete(f"/industry-brief/issues/{issue.id}/feedback")
    assert restored.status_code == 200
    assert restored.json()["restored"] is True
    assert db.query(IssueFeedback).filter_by(issue_id=issue.id).count() == 0


def test_issue_feedback_requires_login(client, db_factory):
    assert client.post("/industry-brief/issues/1/feedback", json={"verdict": "NOT_CORE"}).status_code == 401


def test_editorial_rule_can_be_approved_and_deactivated(client, make_user, db_factory):
    _login(client, make_user)
    created = client.post("/industry-brief/feedback/rules", json={"pattern": "배우", "reason": "PROMOTIONAL"})
    assert created.status_code == 200
    rule_id = created.json()["id"]

    listed = client.get("/industry-brief/feedback/rules")
    assert listed.status_code == 200
    assert listed.json()["activeRules"][0]["pattern"] == "배우"
    assert listed.json()["history"][0]["action"] == "APPROVED"

    removed = client.delete(f"/industry-brief/feedback/rules/{rule_id}")
    assert removed.status_code == 200
    assert removed.json()["active"] is False
    after = client.get("/industry-brief/feedback/rules").json()
    assert after["activeRules"] == []
    assert after["history"][0]["action"] == "DEACTIVATED"
    assert after["history"][0]["pattern"] == "배우"


def test_editorial_rule_preview_is_read_only(client, make_user, db_factory):
    _login(client, make_user)
    db = db_factory()
    _seed_brief(db)
    before = db.query(EditorialRule).count()

    preview = client.post("/industry-brief/feedback/rules/preview", json={"pattern": "테스트", "reason": "LOW_IMPACT"})

    assert preview.status_code == 200
    assert preview.json()["issueCount"] == 1
    assert preview.json()["articleCount"] == 1
    assert preview.json()["issues"][0]["title"] == "테스트 이슈"
    assert preview.json()["riskLevel"] == "SAFE"
    assert preview.json()["warnings"] == []
    assert db.query(EditorialRule).count() == before

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


def test_refresh_requires_login(client):
    res = client.post("/industry-brief/refresh")
    assert res.status_code == 401


def test_refresh_runs_pipeline_and_returns_new_brief(client, make_user, db_factory, monkeypatch):
    _login(client, make_user)
    db = db_factory()
    brief, _ = _seed_brief(db)

    def fake_refresh(_db):
        return SimpleNamespace(
            collected=7, classified=4, new_issues=2, appended_to_issues=1, brief_id=brief.id,
        )

    monkeypatch.setattr("app.industry_brief.routes.refresh_industry_brief", fake_refresh)
    res = client.post("/industry-brief/refresh")

    assert res.status_code == 200
    assert res.json()["brief"]["briefDate"] == "2026-08-10"
    assert res.json()["refresh"] == {
        "collected": 7, "classified": 4, "newIssues": 2, "appendedToIssues": 1,
    }
