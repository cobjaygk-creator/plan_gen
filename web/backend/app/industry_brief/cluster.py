"""Phase 4: group articles covering the same event into an Issue (design
doc section 27/36 "Issue Cluster"). Spec section 26 explicitly allows an
MVP-level heuristic ("MVP에서는 URL + 제목 유사도로 시작") — this combines
title similarity with keyword/entity overlap, since Phase 3 already
extracted those per article at effectively no extra cost. No AI/embedding
call here; that's an explicitly deferred later refinement per the spec.

why_it_matters (Phase 6, AI synthesis) is left null — this module only
clusters, it doesn't write narrative text."""
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Article, Issue, IssueArticle

TITLE_WEIGHT = 0.6
TAG_WEIGHT = 0.4
SIMILARITY_THRESHOLD = 0.45


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_title(title: str) -> str:
    return re.sub(r"[^\w\s]", "", title.lower()).strip()


def _tags(article: Article) -> set[str]:
    keywords = json.loads(article.keywords) if article.keywords else []
    entities = json.loads(article.entities) if article.entities else []
    return {t.lower() for t in [*keywords, *entities]}


def _similarity(a: Article, b: Article) -> float:
    title_sim = SequenceMatcher(None, _normalize_title(a.title), _normalize_title(b.title)).ratio()
    tags_a, tags_b = _tags(a), _tags(b)
    tag_overlap = len(tags_a & tags_b) / len(tags_a | tags_b) if (tags_a | tags_b) else 0.0
    return TITLE_WEIGHT * title_sim + TAG_WEIGHT * tag_overlap


def _compute_confidence(source_count: int, has_official: bool) -> str:
    if source_count >= 5 or (source_count >= 3 and has_official):
        return "STRONG"
    if source_count >= 2:
        return "MODERATE"
    return "WEAK"


def _refresh_issue_stats(issue: Issue, members: list[Article]) -> None:
    """Takes the member list directly rather than re-querying the DB —
    the session this runs in has autoflush=False (see database.py), so a
    query run right after adding a not-yet-flushed IssueArticle row for
    this same issue would come back empty and silently no-op here."""
    if not members:
        return
    sources = {m.source for m in members}
    has_official = any(m.source_type == "official" for m in members)
    issue.confidence = _compute_confidence(len(sources), has_official)
    issue.importance_score = max((m.importance_score or 0.0) for m in members)
    published_dates = [m.published_at for m in members if m.published_at is not None]
    if published_dates:
        issue.last_seen_at = max(published_dates)


@dataclass
class ClusterResult:
    new_issues: int = 0
    appended: int = 0


def cluster_pending(db: Session, limit: int = 200) -> ClusterResult:
    already_clustered = {row[0] for row in db.execute(select(IssueArticle.article_id))}

    candidates = db.execute(
        select(Article)
        .where(Article.is_relevant.is_(True))
        .where(Article.classified_at.isnot(None))
        .limit(limit)
    ).scalars().all()
    candidates = [a for a in candidates if a.id not in already_clustered]

    open_issues = list(db.execute(select(Issue)).scalars().all())
    members_by_issue: dict[int, list[Article]] = {
        issue.id: db.execute(
            select(Article).join(IssueArticle, IssueArticle.article_id == Article.id)
            .where(IssueArticle.issue_id == issue.id)
        ).scalars().all()
        for issue in open_issues
    }

    result = ClusterResult()
    for article in candidates:
        best_issue, best_score = None, 0.0
        for issue in open_issues:
            if issue.category != article.category:
                continue
            score = max((_similarity(article, m) for m in members_by_issue.get(issue.id, [])), default=0.0)
            if score > best_score:
                best_issue, best_score = issue, score

        if best_issue is not None and best_score >= SIMILARITY_THRESHOLD:
            db.add(IssueArticle(issue_id=best_issue.id, article_id=article.id))
            members_by_issue[best_issue.id].append(article)
            _refresh_issue_stats(best_issue, members_by_issue[best_issue.id])
            result.appended += 1
        else:
            when = article.published_at or _utcnow()
            issue = Issue(
                category=article.category, title=article.title, summary=article.summary,
                importance_score=article.importance_score, lifecycle="EMERGING",
                first_seen_at=when, last_seen_at=when,
            )
            db.add(issue)
            db.flush()  # populate issue.id before the join row references it
            db.add(IssueArticle(issue_id=issue.id, article_id=article.id))
            open_issues.append(issue)
            members_by_issue[issue.id] = [article]
            _refresh_issue_stats(issue, members_by_issue[issue.id])
            result.new_issues += 1

    db.commit()
    return result
