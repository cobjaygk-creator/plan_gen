"""Persist auditable observation-to-core transitions for Industry Brief."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .editorial_ranking import is_core_summary_candidate
from .models import Article, Issue, IssueArticle, IssueHistory
from .trust import evaluate_evidence, source_tier


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _window_members(db: Session, issue_id: int, start: datetime, end: datetime) -> list[Article]:
    article_time = func.coalesce(Article.published_at, Article.collected_at)
    return list(db.execute(
        select(Article).join(IssueArticle, IssueArticle.article_id == Article.id).where(
            IssueArticle.issue_id == issue_id,
            Article.is_relevant.is_(True),
            article_time >= start,
            article_time < end,
        )
    ).scalars().all())


def _editorial_state(issue: Issue, members: list[Article]) -> str | None:
    if not members or not is_core_summary_candidate(issue, members):
        return None
    quality = evaluate_evidence(members)
    if quality.synthesis_eligible:
        return "CORE"
    if any(source_tier(article) in {"PRIMARY", "ESTABLISHED_MEDIA"} for article in members):
        return "OBSERVING"
    return None


def record_editorial_states(
    db: Session,
    period_start: datetime,
    period_end: datetime,
    observed_at: datetime,
    stale_after: timedelta = timedelta(hours=72),
) -> None:
    article_time = func.coalesce(Article.published_at, Article.collected_at)
    issues = db.execute(
        select(Issue).join(IssueArticle, IssueArticle.issue_id == Issue.id)
        .join(Article, Article.id == IssueArticle.article_id)
        .where(Article.is_relevant.is_(True), article_time >= period_start, article_time < period_end)
        .distinct()
    ).scalars().all()
    active_issue_ids: set[int] = set()
    for issue in issues:
        members = _window_members(db, issue.id, period_start, period_end)
        current = _editorial_state(issue, members)
        if current is None:
            continue
        active_issue_ids.add(issue.id)
        latest = db.execute(
            select(IssueHistory).where(IssueHistory.issue_id == issue.id)
            .order_by(IssueHistory.observed_at.desc(), IssueHistory.id.desc()).limit(1)
        ).scalar_one_or_none()
        prior = "CORE" if latest and latest.state == "PROMOTED" else (latest.state if latest else None)
        evidence_ids = sorted(article.id for article in members)
        if prior == current:
            try:
                prior_evidence_ids = sorted(json.loads(latest.evidence_article_ids or "[]")) if latest else []
            except (TypeError, ValueError):
                prior_evidence_ids = []
            if prior_evidence_ids == evidence_ids:
                continue
        state = "PROMOTED" if prior == "OBSERVING" and current == "CORE" else current
        db.add(IssueHistory(
            issue_id=issue.id,
            observed_at=observed_at,
            state=state,
            before_summary=latest.now_summary if latest else None,
            now_summary=issue.summary or issue.title,
            evidence_article_ids=json.dumps(evidence_ids),
        ))

    # An observation expires only when it has left the active window and no
    # new evidence has refreshed it for 72 hours. Promoted/core issues never
    # enter this path.
    latest_by_issue: dict[int, IssueHistory] = {}
    histories = db.execute(
        select(IssueHistory).order_by(IssueHistory.observed_at.desc(), IssueHistory.id.desc())
    ).scalars().all()
    for history in histories:
        latest_by_issue.setdefault(history.issue_id, history)
    cutoff = _aware(observed_at) - stale_after
    for issue_id, latest in latest_by_issue.items():
        if issue_id in active_issue_ids or latest.state != "OBSERVING":
            continue
        if _aware(latest.observed_at) > cutoff:
            continue
        issue = db.get(Issue, issue_id)
        if issue is None:
            continue
        db.add(IssueHistory(
            issue_id=issue_id,
            observed_at=observed_at,
            state="CLOSED",
            before_summary=latest.now_summary,
            now_summary=issue.summary or issue.title,
            evidence_article_ids=latest.evidence_article_ids or "[]",
        ))


def promotion_payload(db: Session, category: str, period_start: datetime, period_end: datetime, limit: int = 3) -> list[dict]:
    rows = db.execute(
        select(IssueHistory, Issue).join(Issue, Issue.id == IssueHistory.issue_id).where(
            Issue.category == category,
            IssueHistory.state == "PROMOTED",
            IssueHistory.observed_at >= period_start,
            IssueHistory.observed_at < period_end,
        ).order_by(IssueHistory.observed_at.desc()).limit(limit)
    ).all()
    result = []
    for history, issue in rows:
        try:
            evidence_count = len(json.loads(history.evidence_article_ids or "[]"))
        except (TypeError, ValueError):
            evidence_count = 0
        result.append({
            "title": issue.title,
            "summary": history.now_summary or issue.summary or issue.title,
            "promotedAt": _aware(history.observed_at).isoformat(),
            "evidenceCount": evidence_count,
            "reason": f"주요 원문 관찰 후 독립 출처가 추가되어 핵심 이슈로 승격 · 근거 {evidence_count}건",
        })
    return result


def closed_observation_payload(db: Session, category: str, period_start: datetime, period_end: datetime, limit: int = 3) -> list[dict]:
    rows = db.execute(
        select(IssueHistory, Issue).join(Issue, Issue.id == IssueHistory.issue_id).where(
            Issue.category == category,
            IssueHistory.state == "CLOSED",
            IssueHistory.observed_at >= period_start,
            IssueHistory.observed_at < period_end,
        ).order_by(IssueHistory.observed_at.desc()).limit(limit)
    ).all()
    return [{
        "title": issue.title,
        "closedAt": _aware(history.observed_at).isoformat(),
        "reason": "72시간 동안 추가 근거나 교차 보도가 확인되지 않아 관찰을 종료했습니다.",
    } for history, issue in rows]
