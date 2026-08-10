"""Read-only API so the frontend can show the real AI-synthesized brief
(Phase 6's `DailyBrief` + `Issue` rows) instead of Phase 1's static mock.
Shares the existing session-cookie auth (`get_current_user`) with the rest
of the app — Industry Brief has no writes of its own, so that's the only
piece of existing infrastructure this reuses."""
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User
from .models import Article, DailyBrief, Issue, IssueArticle
from .synthesis import NO_CROSS_SIGNAL_TEXT, TOP_ISSUES_PER_CATEGORY

router = APIRouter(prefix="/industry-brief", tags=["industry-brief"])

_IMPORTANCE_LABELS = [(75.0, "높음"), (45.0, "보통")]


def _importance_label(score: Optional[float]) -> str:
    for threshold, label in _IMPORTANCE_LABELS:
        if score is not None and score >= threshold:
            return label
    return "낮음"


def _as_aware_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """SQLite silently drops tzinfo on storage even for DateTime(timezone=True)
    columns, so a value round-tripped through the DB comes back naive even
    though every datetime in this app is UTC end-to-end (see trends.py's
    module docstring for the same quirk)."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _published_ago(published_at: Optional[datetime], now: datetime) -> str:
    published_at = _as_aware_utc(published_at)
    if published_at is None:
        return "시간 미상"
    delta = now - published_at
    minutes = int(delta.total_seconds() // 60)
    if minutes < 60:
        return f"{max(minutes, 0)}분 전"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}시간 전"
    return f"{hours // 24}일 전"


def _issue_members(db: Session, issue: Issue) -> list[Article]:
    return list(
        db.execute(
            select(Article).join(IssueArticle, IssueArticle.article_id == Article.id)
            .where(IssueArticle.issue_id == issue.id)
        ).scalars().all()
    )


def _issue_payload(db: Session, issue: Issue, now: datetime) -> dict:
    members = _issue_members(db, issue)
    sources = {m.source for m in members}
    official_count = sum(1 for m in members if m.source_type == "official")
    members_by_recency = sorted(members, key=lambda m: _as_aware_utc(m.published_at) or now, reverse=True)

    return {
        "id": f"issue-{issue.id}",
        "category": issue.category,
        "importance": _importance_label(issue.importance_score),
        "title": issue.title,
        "summary": issue.summary or "",
        "whyItMatters": issue.why_it_matters or "아직 분석되지 않았습니다.",
        "lifecycle": issue.lifecycle,
        "relatedBriefing": f"{'GAME INDUSTRY' if issue.category == 'GAME' else 'AI INDUSTRY'} / {issue.title[:24]}",
        "confidence": {
            "level": issue.confidence or "WEAK",
            "articleCount": len(members),
            "independentSources": len(sources),
            "officialCount": official_count,
        },
        "sources": [
            {
                "outlet": m.source,
                "title": m.title,
                "publishedAgo": _published_ago(m.published_at, now),
                "url": m.url,
            }
            for m in members_by_recency[:5]
        ],
    }


def _top_issues(db: Session, category: str, limit: int = TOP_ISSUES_PER_CATEGORY) -> list[Issue]:
    return list(
        db.execute(
            select(Issue)
            .where(Issue.category == category)
            .order_by(Issue.importance_score.desc().nulls_last())
            .limit(limit)
        ).scalars().all()
    )


def _watch_list(raw_json: str) -> list[dict]:
    items = json.loads(raw_json) if raw_json else []
    return [{"rank": i + 1, "topic": item["topic"], "description": item["description"]} for i, item in enumerate(items)]


def _serialize_brief(db: Session, brief: DailyBrief) -> dict:
    now = datetime.now(timezone.utc)
    game_analysis = json.loads(brief.game_ai_analysis)
    has_signal = game_analysis != [NO_CROSS_SIGNAL_TEXT]

    issues = _top_issues(db, "GAME") + _top_issues(db, "AI")

    return {
        "briefDate": brief.brief_date,
        "generatedAt": brief.generated_at.isoformat(),
        "periodLabel": "지난 24시간",
        "articleCount": brief.article_count,
        "game": {
            "headline": brief.game_headline,
            "briefing": json.loads(brief.game_briefing),
            "changes": json.loads(brief.game_changes),
            "watchList": _watch_list(brief.game_watchlist),
        },
        "ai": {
            "headline": brief.ai_headline,
            "briefing": json.loads(brief.ai_briefing),
            "changes": json.loads(brief.ai_changes),
            "watchList": _watch_list(brief.ai_watchlist),
        },
        "crossInsight": {"hasSignal": has_signal, "summary": game_analysis},
        "signals": json.loads(brief.signals),
        "newToday": json.loads(brief.new_today),
        "issues": [_issue_payload(db, issue, now) for issue in issues],
    }


@router.get("/latest")
def get_latest_brief(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    brief = db.execute(select(DailyBrief).order_by(DailyBrief.id.desc())).scalars().first()
    if brief is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "아직 생성된 브리핑이 없습니다.")
    return _serialize_brief(db, brief)
