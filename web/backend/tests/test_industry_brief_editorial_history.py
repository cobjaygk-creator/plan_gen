import json
from datetime import datetime, timedelta, timezone

from app.industry_brief.editorial_history import closed_observation_payload, promotion_payload, record_editorial_states
from app.industry_brief.models import Article, Issue, IssueArticle, IssueHistory


def _seed(db, *, source: str, url: str, title: str):
    now = datetime.now(timezone.utc)
    issue = db.query(Issue).first()
    if issue is None:
        issue = Issue(category="GAME", title="신작 글로벌 출시", summary="정식 출시 일정 발표", importance_score=80,
                      confidence="WEAK", lifecycle="EMERGING", first_seen_at=now, last_seen_at=now)
        db.add(issue); db.commit(); db.refresh(issue)
    article = Article(source=source, source_type="media", category="GAME", title=title, url=url,
                      is_relevant=True, importance_score=80, keywords="[]", entities="[]",
                      classified_at=now, published_at=now)
    db.add(article); db.commit(); db.refresh(article)
    db.add(IssueArticle(issue_id=issue.id, article_id=article.id)); db.commit()
    return issue, article, now


def test_observation_is_promoted_after_independent_corroboration(db_factory):
    db = db_factory()
    issue, first, now = _seed(db, source="NAVER · zdnet.co.kr", url="https://zdnet.co.kr/view/1", title="신작 글로벌 출시 발표")
    start, end = now - timedelta(hours=1), now + timedelta(hours=1)
    record_editorial_states(db, start, end, now); db.commit()
    assert db.query(IssueHistory).one().state == "OBSERVING"

    _seed(db, source="NAVER · newsis.com", url="https://newsis.com/view/2", title="신작 글로벌 정식 출시")
    record_editorial_states(db, start, end, now + timedelta(minutes=10)); db.commit()

    states = [row.state for row in db.query(IssueHistory).order_by(IssueHistory.id)]
    assert states == ["OBSERVING", "PROMOTED"]
    payload = promotion_payload(db, "GAME", start, end)
    assert payload[0]["evidenceCount"] == 2
    assert "핵심 이슈로 승격" in payload[0]["reason"]


def test_unconfirmed_observation_closes_after_72_hours(db_factory):
    db = db_factory()
    issue, article, now = _seed(db, source="NAVER · zdnet.co.kr", url="https://zdnet.co.kr/view/stale", title="신작 글로벌 출시 발표")
    start, end = now - timedelta(hours=1), now + timedelta(hours=1)
    record_editorial_states(db, start, end, now); db.commit()

    later = now + timedelta(hours=73)
    empty_start, empty_end = later - timedelta(hours=1), later
    record_editorial_states(db, empty_start, empty_end, later); db.commit()

    states = [row.state for row in db.query(IssueHistory).order_by(IssueHistory.id)]
    assert states == ["OBSERVING", "CLOSED"]
    payload = closed_observation_payload(db, "GAME", later - timedelta(days=1), later + timedelta(minutes=1))
    assert payload[0]["title"] == issue.title
    assert "72시간" in payload[0]["reason"]
