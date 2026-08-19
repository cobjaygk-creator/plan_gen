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
from .trust import evaluate_evidence, source_key, trusted_issue_score

TITLE_WEIGHT = 0.6
TAG_WEIGHT = 0.4
SIMILARITY_THRESHOLD = 0.55


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_title(title: str) -> str:
    return re.sub(r"[^\w\s]", "", title.lower()).strip()


_GENERIC_TAGS = {"ai", "game", "\uac8c\uc784", "\uc778\uacf5\uc9c0\ub2a5", "\ud55c\uad6d", "industry", "\uc0b0\uc5c5"}
_GENERIC_ORGANIZATIONS = {
    "openai", "오픈ai", "오픈에이아이",
    "nvidia", "엔비디아", "microsoft", "마이크로소프트",
    "google", "구글", "meta", "메타", "anthropic", "앤트로픽",
    "samsung", "samsung electronics", "\uc0bc\uc131\uc804\uc790",
    "krafton", "\ud06c\ub798\ud504\ud1a4", "nexon", "\ub125\uc2a8", "\ub125\uc2a8\uac8c\uc784\uc988",
    "netmarble", "\ub137\ub9c8\ube14", "ncsoft", "\uc5d4\uc528\uc18c\ud504\ud2b8", "nc",
}
_EVENT_TERMS = {
    "RELEASE": ("\ucd9c\uc2dc", "\uacf5\uac1c", "\ubc1c\ud45c", "release", "launch", "unveil", "ship"),
    "UPDATE": ("\uc5c5\ub370\uc774\ud2b8", "\ud328\uce58", "update", "patch"),
    "INVESTMENT": ("\ud22c\uc790", "\uc9c0\ubd84", "\uc790\uae08 \uc870\ub2ec", "investment", "funding", "stake"),
    "MNA": ("\uc778\uc218", "\ud569\ubcd1", "acquisition", "acquire", "merger"),
    "EARNINGS": ("\uc2e4\uc801", "\ub9e4\ucd9c", "\uc601\uc5c5\uc774\uc775", "earnings", "revenue"),
    "POLICY": ("\uaddc\uc81c", "\uc815\ucc45", "\ubc95\uc548", "regulation", "policy", "law"),
    "SECURITY": ("\ubcf4\uc548", "\ucde8\uc57d\uc810", "\uc720\ucd9c", "security", "vulnerability", "breach"),
    "PARTNERSHIP": ("\ud611\ub825", "\uc81c\ud734", "\ud30c\ud2b8\ub108\uc2ed", "partnership", "collaboration"),
}


def _json_tags(value: str | None) -> set[str]:
    try:
        items=json.loads(value or "[]")
    except (TypeError, ValueError):
        items=[]
    return {str(item).strip().casefold() for item in items if len(str(item).strip()) > 1}


def _keywords(article: Article) -> set[str]:
    return _json_tags(article.keywords) - _GENERIC_TAGS


def _entities(article: Article) -> set[str]:
    return _json_tags(article.entities) - _GENERIC_TAGS - _GENERIC_ORGANIZATIONS


def _overlap_min(left: set[str], right: set[str]) -> float:
    return len(left & right) / max(1, min(len(left), len(right))) if left and right else 0.0


def _event_types(article: Article) -> set[str]:
    text=f"{article.title} {article.summary or ''}".casefold()
    return {kind for kind,terms in _EVENT_TERMS.items() if any(term.casefold() in text for term in terms)}


def _near_in_time(a: Article,b: Article,days: int=7) -> bool:
    left=a.published_at or a.collected_at; right=b.published_at or b.collected_at
    if left is None or right is None: return True
    if left.tzinfo is None: left=left.replace(tzinfo=timezone.utc)
    if right.tzinfo is None: right=right.replace(tzinfo=timezone.utc)
    return abs((left-right).total_seconds()) <= days*86400


def _similarity(a: Article, b: Article) -> float:
    normalized_a = _normalize_title(a.title)
    normalized_b = _normalize_title(b.title)
    title_sim=SequenceMatcher(None,normalized_a,normalized_b).ratio()
    keyword_overlap=_overlap_min(_keywords(a),_keywords(b))
    shared_entities = _entities(a) & _entities(b)
    entity_overlap=_overlap_min(_entities(a),_entities(b))
    score=.45*title_sim + .25*keyword_overlap + .30*entity_overlap
    # Repeated posts from one outlet are not independent corroboration.
    # Only near-duplicate titles may share an issue; a publisher's separate
    # updates about the same company or franchise remain distinct events.
    if source_key(a) == source_key(b) and title_sim < .95:
        return min(score, .49)
    events_a,events_b=_event_types(a),_event_types(b)
    if events_a and events_b and not (events_a & events_b):
        return min(score,.34)
    shared_entity_in_both_titles = any(
        entity in normalized_a and entity in normalized_b
        for entity in shared_entities
    )
    if shared_entities and not shared_entity_in_both_titles and title_sim < .55:
        return min(score, .49)
    near=_near_in_time(a,b)
    if (
        near and entity_overlap > 0 and events_a & events_b
        and (keyword_overlap >= .5 or title_sim >= .62)
    ):
        score=max(score,.62)
    elif near and entity_overlap > 0 and keyword_overlap >= .5:
        score=max(score,.55)
    return score


def _matches_issue(article: Article, members: list[Article]) -> bool:
    """Prevent single-link chains from merging several different events."""
    if not members:
        return False
    same_source_members = [member for member in members if source_key(article) == source_key(member)]
    if same_source_members:
        same_source_title_scores = [
            SequenceMatcher(
                None,
                _normalize_title(article.title),
                _normalize_title(member.title),
            ).ratio()
            for member in same_source_members
        ]
        if max(same_source_title_scores) < .95:
            return False
    scores = [_similarity(article, member) for member in members]
    if max(scores) < SIMILARITY_THRESHOLD:
        return False
    anchor_matches = scores[0] >= SIMILARITY_THRESHOLD
    supporting_ratio = sum(score >= SIMILARITY_THRESHOLD for score in scores) / len(scores)
    return anchor_matches or supporting_ratio >= .5


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
    raw_importance = max((m.importance_score or 0.0) for m in members)
    issue.importance_score = trusted_issue_score(raw_importance, members)
    published_dates = [m.published_at for m in members if m.published_at is not None]
    if published_dates:
        issue.last_seen_at = max(published_dates)


@dataclass
class ClusterResult:
    new_issues: int = 0
    appended: int = 0


def cluster_pending(db: Session, limit: int = 200) -> ClusterResult:
    # Filter clustered articles in SQL before applying the limit.  Applying the
    # limit first could inspect only old, already-linked rows and starve every
    # newly classified article from the issue map indefinitely.
    clustered_article_ids = select(IssueArticle.article_id)
    candidates = db.execute(
        select(Article)
        .where(Article.is_relevant.is_(True))
        .where(Article.classified_at.isnot(None))
        .where(Article.id.not_in(clustered_article_ids))
        .order_by(Article.classified_at.desc(), Article.id.desc())
        .limit(limit)
    ).scalars().all()

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
            issue_members = members_by_issue.get(issue.id, [])
            score = max((_similarity(article, m) for m in issue_members), default=0.0)
            if _matches_issue(article, issue_members) and score > best_score:
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
