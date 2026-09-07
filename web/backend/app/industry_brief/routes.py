"""Read-only API so the frontend can show the real AI-synthesized brief
(Phase 6's `DailyBrief` + `Issue` rows) instead of Phase 1's static mock.
Shares the existing session-cookie auth (`get_current_user`) with the rest
of the app — Industry Brief has no writes of its own, so that's the only
piece of existing infrastructure this reuses."""
import json
import math
from threading import Lock
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User
from .collector import collect_all
from .models import Article, DailyBrief, EditorialRule, EditorialRuleAudit, Issue, IssueArticle, IssueFeedback
from .highlights import list_all_window_articles, load_highlights_for_date, load_latest_highlights, refresh_and_save_highlights, to_api_dict
from .synthesis import NO_CROSS_OPINION_TEXT, NO_CROSS_SIGNAL_TEXT, TOP_ISSUES_PER_CATEGORY
from .landscape import build_issue_detail, build_landscape
from .comparison import build_market_comparison
from .tech_radar import build_tech_radar
from .sources import GAME_COMPANY_NAMES
from .refresh import refresh_industry_brief
from .periods import KST, PERIOD_LABELS, day_window, period_window
from .policy_intelligence import build_policy_updates
from .recommendation_policy import event_key, is_promotional, recommendation_score
from .trust import evaluate_evidence, source_tier, trusted_issue_score
from .cluster import _matches_issue
from .editorial_ranking import editorial_score, is_core_summary_candidate
from .editorial_history import closed_observation_payload, promotion_payload
from .feedback_rules import active_rule_match, rule_suggestions

router = APIRouter(prefix="/industry-brief", tags=["industry-brief"])

_IMPORTANCE_LABELS = [(75.0, "높음"), (45.0, "보통")]
_REFRESH_LOCK = Lock()


class IssueFeedbackIn(BaseModel):
    verdict: str = Field(pattern="^NOT_CORE$")
    reason: str = Field(default="OTHER", pattern="^(PROMOTIONAL|LOW_IMPORTANCE|DUPLICATE|LOW_IMPACT|OTHER)$")


class EditorialRuleIn(BaseModel):
    pattern: str = Field(min_length=2, max_length=80, pattern=r"^[가-힣A-Za-z0-9 _-]+$")
    reason: str = Field(pattern="^(PROMOTIONAL|LOW_IMPORTANCE|DUPLICATE|LOW_IMPACT|OTHER)$")
    confirmBroadImpact: bool = False

_TOPIC_RULES = (
    ("M&A", ("인수", "합병", "m&a", "acquisition", "merger")),
    ("보안", ("보안", "해킹", "취약점", "랜섬웨어", "security", "breach")),
    ("정책", ("정책", "규제", "법안", "정부", "등급분류", "표시의무", "regulation")),
    ("투자", ("투자", "펀딩", "자금조달", "투자유치", "investment", "funding")),
    ("업데이트", ("업데이트", "패치", "확장팩", "시즌", "update", "patch")),
    ("출시", ("출시", "공개", "발표", "신작", "론칭", "launch", "release")),
    ("기술", ("기술", "모델", "api", "오픈웨이트", "오픈소스", "반도체", "agent", "에이전트")),
)
_MARKETING_RANK_TERMS = (
    "앱스토어 인기", "인기 1위", "인기게임 1위", "인기 순위", "다운로드 순위",
    "사전 다운로드", "예약 다운로드", "매출 순위", "플레이스토어 인기",
    "구글 플레이 인기", "차트 1위", "흥행 1위", "톱10",
)


def _is_marketing_ranking_story(text: str) -> bool:
    """독립 출처 수·보도 집중도로는 못 걸러진다 — "제우스: 오만의 신" 도배는
    18개 서로 다른 도메인이 각자 "사전 다운로드 앱스토어 인기 1위"라는
    같은 마케팅 지표를 그대로 받아쓴 것이라, 신뢰도 점수로는 게임스컴처럼
    진짜 여러 매체가 취재한 이슈와 구분이 안 됐다(둘 다 100점). 대신
    앱스토어 순위·사전 다운로드 같은 마케팅 지표 언어 자체를 감점한다."""
    return any(term in text for term in _MARKETING_RANK_TERMS)


_GENERIC_CHART_KEYWORDS = {
    "ai", "게임", "기술", "산업", "시장", "기업", "서비스", "플랫폼", "투자", "출시",
    "업데이트", "game", "technology", "business", "korean tech",
    "nhn", "카카오", "네이버", "삼성전자", "삼성", "lg", "sk텔레콤",
    "openai", "google", "구글", "microsoft", "마이크로소프트", "nvidia", "엔비디아",
    "meta", "메타", "anthropic", "앤트로픽",
    # 게임사/AI 기업명 — 그 회사 관련 기사 전반에 두루 등장해서 빈도만
    # 보면 항상 이기지만, 정작 그 이슈가 "무엇에 대한" 이슈인지는 알려주지
    # 못한다 (예: "컴투스"보다 "제우스: 오만의 신"이 훨씬 더 구체적이고
    # 그 이슈를 식별해준다). 회사명은 후보에서 빼서 더 구체적인 제품·
    # 이벤트명이 뽑히도록 한다. 게임사 명단은 sources.py와 공유.
    *(name.casefold() for name in GAME_COMPANY_NAMES),
}


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


def _issue_payload(db: Session, issue: Issue, now: datetime, members: list[Article] | None = None) -> dict:
    period_scoped = members is not None
    members = members if members is not None else _issue_members(db, issue)
    sources = {m.source for m in members}
    evidence = evaluate_evidence(members)
    official_count = evidence.official_count
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
            "level": evidence.confidence if period_scoped else (issue.confidence or evidence.confidence),
            "articleCount": len(members),
            "independentSources": evidence.independent_sources,
            "officialCount": official_count,
        },
        "evidenceQuality": {
            "verificationStatus": evidence.verification_status,
            "synthesisEligible": evidence.synthesis_eligible,
            "establishedMediaCount": evidence.established_media_count,
            "discoveryMediaCount": evidence.discovery_count,
            "reason": evidence.reason,
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


def _top_issues(
    db: Session,
    category: str,
    period_start: datetime,
    period_end: datetime,
    limit: int = TOP_ISSUES_PER_CATEGORY,
) -> list[Issue]:
    """Rank corroborated events first; retain single-source items as clearly labelled leads."""
    rows=list(db.execute(
        select(Issue).where(
            Issue.category == category,
            Issue.last_seen_at >= period_start,
            Issue.last_seen_at <= period_end,
        ).order_by(Issue.last_seen_at.desc()).limit(limit * 8)
    ).scalars().all())
    ranked=[]
    for issue in rows:
        members=_issue_members(db,issue)
        quality=evaluate_evidence(members)
        ranked.append((quality.synthesis_eligible,trusted_issue_score(issue.importance_score,members),issue.last_seen_at,issue))
    ranked.sort(key=lambda item:(item[0],item[1],item[2]),reverse=True)
    return [item[3] for item in ranked[:limit]]


def _period_ranked_issues(
    db: Session, category: str, period_start: datetime, period_end: datetime, limit: int = 8,
    similarity_cache: dict[tuple[int, int], float] | None = None,
) -> list[dict]:
    """Rank issues using only evidence published inside the requested window.

    similarity_cache: 한 요청 안에서 이 함수가 여러 창(오늘/최근 1주 등)
    으로 반복 호출될 때 같은 (공식 후보 기사, 이슈 구성원) 쌍을 다시 비교
    하지 않도록 호출자가 공유 dict를 넘겨줄 수 있다 — _matches_issue의
    SequenceMatcher 비교가 프로파일링 결과 압도적 병목이었다."""
    start = _as_aware_utc(period_start)
    end = _as_aware_utc(period_end)
    assert start is not None and end is not None
    article_time = func.coalesce(Article.published_at, Article.collected_at)
    issues = list(db.execute(
        select(Issue).join(IssueArticle, IssueArticle.issue_id == Issue.id)
        .join(Article, Article.id == IssueArticle.article_id)
        .where(
            Issue.category == category,
            Article.is_relevant.is_(True),
            article_time >= start,
            article_time < end,
        ).distinct()
    ).scalars().all())
    category_total = db.execute(select(func.count(Article.id)).where(
        Article.category == category,
        Article.is_relevant.is_(True),
        article_time >= start,
        article_time < end,
    )).scalar_one()
    window_seconds = max(1.0, (end - start).total_seconds())
    window_days = max(1, math.ceil(window_seconds / 86400))
    previous_start = start - (end - start)
    official_candidates = [
        article for article in db.execute(select(Article).where(
            Article.category == category,
            Article.is_relevant.is_(True),
            article_time >= start,
            article_time < end,
        )).scalars().all()
        if source_tier(article) == "PRIMARY"
    ]
    ranked: list[dict] = []
    for issue in issues:
        all_members = _issue_members(db, issue)
        members = []
        previous_count = 0
        for article in all_members:
            published = _as_aware_utc(article.published_at or article.collected_at)
            if published is None:
                continue
            if start <= published < end and article.is_relevant is True:
                members.append(article)
            elif previous_start <= published < start and article.is_relevant is True:
                previous_count += 1
        if not members:
            continue
        member_ids = {article.id for article in members}
        for official in official_candidates:
            if official.id in member_ids:
                continue
            if _matches_issue(official, members, similarity_cache):
                members.append(official)
                member_ids.add(official.id)
        quality = evaluate_evidence(members)
        active_days = len({
            (_as_aware_utc(article.published_at or article.collected_at) or start).astimezone(KST).date()
            for article in members
        })
        average_importance = sum(article.importance_score or 0 for article in members) / len(members)
        evidence_score = {
            "CORROBORATED": 35.0, "OFFICIAL_ONLY": 27.0,
            "DISCOVERY_ONLY": 12.0, "SINGLE_SOURCE": 6.0,
        }[quality.verification_status]
        volume_score = min(25.0, math.log2(len(members) + 1) * 10.0)
        importance_score = min(20.0, average_importance * 0.2)
        persistence_score = min(12.0, active_days / window_days * 12.0)
        momentum = (len(members) - previous_count) / max(1, previous_count)
        momentum_score = max(0.0, min(8.0, 4.0 + momentum * 2.0))
        raw_score = round(min(100.0, evidence_score + volume_score + importance_score + persistence_score + momentum_score), 1)
        score = raw_score
        if category == "GAME":
            score = min(score, editorial_score(issue, members))
        score = round(score, 1)
        editorial_adjustment = round(score - raw_score, 1)
        has_negative_feedback = db.execute(select(func.count(IssueFeedback.id)).where(
            IssueFeedback.issue_id == issue.id,
            IssueFeedback.verdict == "NOT_CORE",
        )).scalar_one() > 0
        matched_rule = active_rule_match(db, issue, [article.title for article in members])
        feedback_penalty = -100.0 if has_negative_feedback else 0.0
        rule_penalty = -100.0 if matched_rule else 0.0
        score = max(0.0, round(score + feedback_penalty + rule_penalty, 1))
        score_breakdown = {
            "evidence": round(evidence_score, 1),
            "coverage": round(volume_score, 1),
            "importance": round(importance_score, 1),
            "persistence": round(persistence_score, 1),
            "momentum": round(momentum_score, 1),
            "editorialAdjustment": editorial_adjustment,
            "userFeedback": feedback_penalty,
            "approvedRule": rule_penalty,
            "total": score,
        }
        reason_parts = [f"기사 {len(members)}건", f"독립 매체 {quality.independent_sources}곳"]
        if quality.official_count:
            reason_parts.append(f"공식 근거 {quality.official_count}건")
        if window_days > 1:
            reason_parts.append(f"{active_days}일 관찰")
        reason_parts.append({
            "CORROBORATED": "교차 확인", "OFFICIAL_ONLY": "공식 확인",
            "DISCOVERY_ONLY": "추가 검증 필요", "SINGLE_SOURCE": "단일 출처",
        }[quality.verification_status])
        ranked.append({
            "issue": issue, "members": members, "quality": quality, "score": score,
            "articleCount": len(members), "previousCount": previous_count,
            "activeDays": active_days, "windowDays": window_days,
            "selectionReason": " · ".join(reason_parts),
            "scoreBreakdown": score_breakdown,
            "hasNegativeFeedback": has_negative_feedback,
            "matchedRule": matched_rule.pattern if matched_rule else None,
        })
    ranked.sort(key=lambda item: (
        item["quality"].synthesis_eligible, item["score"], item["articleCount"], item["issue"].last_seen_at,
    ), reverse=True)
    return ranked[:limit]


def _period_key_summary_details(ranked: list[dict], limit: int = 2) -> list[dict]:
    eligible = [
        item for item in ranked
        if item["quality"].synthesis_eligible
        and is_core_summary_candidate(item["issue"], item["members"])
        and not item["hasNegativeFeedback"]
        and not item["matchedRule"]
    ]
    if not eligible:
        candidate_count = len(ranked)
        return [{
            "text": "교차 확인된 핵심 이슈가 아직 없습니다.",
            "articleCount": sum(item["articleCount"] for item in ranked),
            "independentSources": 0,
            "officialCount": 0,
            "activeDays": 0,
            "selectionReason": f"관찰 후보 {candidate_count}건 · 공식·주요 매체 근거 보강 필요",
            "confidence": "WEAK",
            # 프론트가 "이 카테고리는 오늘 판단 이슈가 없다"를 텍스트 매칭 없이
            # 판단할 수 있도록 — 리드 카드가 게임/AI/게임×AI를 순환할 때
            # 이 표식이 있는 카테고리는 슬라이드에서 아예 뺀다.
            "noSignal": True,
        }]
    pool = eligible
    details = []
    seen_events: set[str] = set()
    for item in pool:
        issue = item["issue"]
        event = event_key(item["members"][0]) if item["members"] else issue.title.casefold()
        if event in seen_events:
            continue
        seen_events.add(event)
        text = " ".join((issue.summary or issue.title).split())
        if len(text) > 135:
            text = text[:134].rstrip() + "…"
        details.append({
            "issueId": issue.id,
            "text": text,
            "articleCount": item["articleCount"],
            "independentSources": item["quality"].independent_sources,
            "officialCount": item["quality"].official_count,
            "activeDays": item["activeDays"],
            "selectionReason": item["selectionReason"],
            "confidence": item["quality"].confidence,
            "scoreBreakdown": item["scoreBreakdown"],
        })
        if len(details) == limit:
            break
    return details


def _period_observations(ranked: list[dict], now: datetime, limit: int = 2) -> list[dict]:
    """Material single-source leads, separated from corroborated core facts."""
    observations = []
    for item in ranked:
        if item["quality"].synthesis_eligible:
            continue
        issue = item["issue"]
        members = item["members"]
        if not members or not is_core_summary_candidate(issue, members):
            continue
        best_tier = "PRIMARY" if any(source_tier(article) == "PRIMARY" for article in members) else (
            "ESTABLISHED_MEDIA" if any(source_tier(article) == "ESTABLISHED_MEDIA" for article in members) else None
        )
        if best_tier is None:
            continue
        observations.append({
            "title": issue.title,
            "description": issue.summary or issue.why_it_matters or "추가 보도를 관찰 중입니다.",
            "statusLabel": "공식 발표" if best_tier == "PRIMARY" else "주요 매체 단독",
            "selectionReason": f"{item['selectionReason']} · 교차 보도 대기",
            "sources": [{
                "outlet": article.source,
                "title": article.title,
                "publishedAgo": _published_ago(article.published_at, now),
                "url": article.url,
            } for article in members[:3]],
        })
        if len(observations) == limit:
            break
    return observations


def _period_watch_list(ranked: list[dict], now: datetime) -> list[dict]:
    result = []
    for rank, item in enumerate(ranked[2:5], 1):
        issue = item["issue"]
        result.append({
            "rank": rank,
            "topic": issue.title,
            "description": issue.why_it_matters or issue.summary or item["selectionReason"],
            "sources": [{
                "outlet": article.source, "title": article.title,
                "publishedAgo": _published_ago(article.published_at, now), "url": article.url,
            } for article in item["members"][:5]],
        })
    return result


def _period_signals(ranked: list[dict]) -> list[dict]:
    used: set[str] = set()
    result = []
    for item in ranked:
        issue = item["issue"]
        current = item["articleCount"]
        previous = item["previousCount"]
        if current > previous:
            direction, state, state_label = "up", "GROWING", "증가 중"
        elif current < previous:
            direction, state, state_label = "down", "DECLINING", "약화 중"
        else:
            direction, state, state_label = "flat", "CONTINUING", "지속 관찰"
        result.append({
            "topic": _issue_chart_keyword(issue, item["members"], used),
            "direction": direction, "weight": round(item["score"]),
            "kind": "INDUSTRY", "kindLabel": "기간 이슈",
            "eventType": _topic_name(item["members"][0]),
            "priorityReason": item["selectionReason"], "domain": issue.category,
            "state": state, "stateLabel": state_label,
            "todayCount": current, "baselineAverage": previous / max(1, item["windowDays"]),
            "sourceCount": item["quality"].independent_sources,
            "reason": issue.summary or item["selectionReason"],
            "evidence": [{"outlet": article.source, "title": article.title, "url": article.url} for article in item["members"][:5]],
        })
    return result


def _key_summaries(headline: str, issues: list[Issue], limit: int = 2) -> list[str]:
    """Build up to two concise, evidence-backed takeaways without another AI call."""
    summaries: list[str] = []
    seen: set[str] = set()

    def add(value: str | None) -> None:
        if not value or len(summaries) >= limit:
            return
        text = " ".join(value.split()).strip()
        if not text:
            return
        key = "".join(character.casefold() for character in text if character.isalnum())
        if not key or key in seen:
            return
        seen.add(key)
        summaries.append(text)

    add(headline)
    if "충분한 자료가 수집되지 않았습니다" in headline:
        return summaries
    for issue in issues:
        add(issue.summary or issue.title)
    return summaries


def _topic_name(article: Article) -> str:
    text = f"{article.title} {article.summary or ''} {article.keywords or ''}".casefold()
    for topic, needles in _TOPIC_RULES:
        if any(needle in text for needle in needles):
            return topic
    return "기타"


def _issue_chart_keyword(issue: Issue, members: list[Article], used: set[str]) -> str:
    # entities("기업/제품/인물 등 핵심 개체명")를 keywords보다 우선한다 —
    # keywords는 "MMORPG", "사전 다운로드"처럼 그 사건을 설명하는 일반적인
    # 장르/과정 용어까지 섞여 있어서, 같은 소식을 반복 보도한 기사가 많을
    # 때 그런 범용 용어가 실제 제품명(예: "제우스: 오만의 신")보다 더 자주
    # 등장해 버린다. entities는 회사/제품/인물명만 담겨 있어 그 잡음이 없다.
    candidates: dict[str, tuple[int, int]] = {}
    labels: dict[str, str] = {}
    for article in members:
        try:
            entities = json.loads(article.entities or "[]")
        except (json.JSONDecodeError, TypeError):
            entities = []
        if not isinstance(entities, list) or not entities:
            try:
                entities = json.loads(article.keywords or "[]")
            except (json.JSONDecodeError, TypeError):
                entities = []
        if not isinstance(entities, list):
            continue
        for position, raw in enumerate(entities[:8]):
            label = " ".join(str(raw).split()).strip(" -·")
            key = label.casefold()
            if not label or len(label) > 24 or key in _GENERIC_CHART_KEYWORDS:
                continue
            count, best_position = candidates.get(key, (0, position))
            candidates[key] = (count + 1, min(best_position, position))
            labels[key] = label
    title_text = issue.title.casefold()
    ranked = sorted(
        candidates,
        key=lambda key: (candidates[key][0] + (3 if key in title_text else 0), -candidates[key][1], len(key)),
        reverse=True,
    )
    for key in ranked:
        if key not in used:
            used.add(key)
            return labels[key]

    fallback = issue.title.removeprefix("[기획] ").split("…", 1)[0].split(",", 1)[0].strip()
    if "‘" in fallback and "’" in fallback:
        fallback = fallback.split("‘", 1)[1].split("’", 1)[0].strip()
    if len(fallback) > 18:
        fallback = fallback[:18].rstrip() + "…"
    used.add(fallback.casefold())
    return fallback


def _brief_analytics(
    db: Session,
    period_start: datetime,
    period_end: datetime,
) -> dict:
    """Deterministic charts built only from stored, relevant articles.

    core_issues에서 넘어온 이슈 목록을 그대로 쓰지 않는다 — 그 목록은
    "오늘 처음 기사가 붙은 이슈"만 담고 있어서, 매일 새로 생긴 단발성
    이슈만 뽑히고 실제 여러 날에 걸쳐 이어지는 이슈는 잡히지 않았다
    (예: 기사 1건짜리 이슈 3개가 마지막 하루에만 값을 가져 완전히
    겹쳐 보이던 문제). 대신 차트 자체의 30일 창 안에서 기사가 가장
    많이 쌓인 이슈를 직접 다시 골라, 실제 여러 날에 걸친 관심도 변화를
    보여준다."""
    period_start = _as_aware_utc(period_start)
    period_end = _as_aware_utc(period_end)
    assert period_start is not None and period_end is not None

    chart_start = min(period_start, period_end - timedelta(days=30))
    span_days = max(1, (period_end - chart_start).days + 1)
    weekly = span_days > 45
    bucket_days = 7 if weekly else 1
    bucket_count = min(14 if weekly else 31, (span_days + bucket_days - 1) // bucket_days)
    chart_start = period_end - timedelta(days=bucket_count * bucket_days)
    labels = [
        (chart_start + timedelta(days=index * bucket_days)).astimezone(KST).strftime("%m.%d")
        for index in range(bucket_count)
    ]

    article_time = func.coalesce(Article.published_at, Article.collected_at)
    candidate_ids = [row[0] for row in db.execute(
        select(IssueArticle.issue_id)
        .join(Article, Article.id == IssueArticle.article_id)
        .join(Issue, Issue.id == IssueArticle.issue_id)
        .where(
            Issue.category.in_(("GAME", "AI")),
            Article.is_relevant.is_(True),
            article_time >= chart_start,
            article_time < period_end,
        )
        .group_by(IssueArticle.issue_id)
        .order_by(func.count(IssueArticle.article_id).desc())
        .limit(30)
    ).all()]
    issue_by_id = {
        row.id: row for row in db.execute(
            select(Issue).where(Issue.id.in_(candidate_ids))
        ).scalars().all()
    } if candidate_ids else {}

    # 각 후보 이슈의 멤버 기사를 한 번만 불러와서 순위(마케팅 감점)와
    # 토픽 지형도(출처 수·지속일수) 양쪽에 재사용한다 — 같은 이슈를 두 번
    # 조회하지 않는다.
    candidates: list[dict] = []
    seen_issue_titles: set[str] = set()
    for issue_id in candidate_ids:
        issue = issue_by_id.get(issue_id)
        if issue is None:
            continue
        key = issue.title.strip().casefold()
        if not key or key in seen_issue_titles:
            continue
        seen_issue_titles.add(key)
        members = _issue_members(db, issue)
        window_members = [
            a for a in members
            if (pub := _as_aware_utc(a.published_at or a.collected_at)) is not None
            and chart_start <= pub < period_end
        ]
        if not window_members:
            continue
        is_marketing = any(
            _is_marketing_ranking_story(f"{a.title} {a.summary or ''}".casefold())
            for a in window_members
        )
        distinct_days = len({(_as_aware_utc(a.published_at or a.collected_at)).date() for a in window_members})
        quality = evaluate_evidence(window_members)
        first_seen = _as_aware_utc(issue.first_seen_at)
        age_days = (period_end - first_seen).days if first_seen else None
        candidates.append({
            "issue": issue, "members": window_members, "is_marketing": is_marketing,
            "count": len(window_members), "days": distinct_days,
            "sources": quality.independent_sources,
            # 신규 진입(이번 주 처음 생긴 이슈) vs 지속(2주 넘게 이어지는
            # 이슈) 구분 — Issue.first_seen_at은 클러스터링 시점에 한 번만
            # 찍히고 안 바뀌므로, "이 이슈가 언제 처음 등장했는가"를 그대로
            # 알려준다.
            "is_fresh": age_days is not None and age_days < 7,
            "is_ongoing": age_days is not None and age_days >= 14,
        })

    ranked_candidates = sorted(candidates, key=lambda item: (item["is_marketing"], -item["count"]))

    interest_series: list[dict] = []
    used_keywords: set[str] = set()
    for item in ranked_candidates:
        issue, members = item["issue"], item["members"]
        values = [0] * bucket_count
        for article in members:
            published = _as_aware_utc(article.published_at or article.collected_at)
            index = int((published - chart_start).total_seconds() // (bucket_days * 86400))
            if 0 <= index < bucket_count:
                values[index] += 1
        interest_series.append({
            "name": _issue_chart_keyword(issue, members, used_keywords),
            "originalTitle": issue.title,
            "category": issue.category,
            "values": values,
        })
        if len(interest_series) == 3:
            break

    landscape_keywords: set[str] = set()
    topic_landscape = [
        {
            "name": _issue_chart_keyword(item["issue"], item["members"], landscape_keywords),
            "category": item["issue"].category,
            "sources": item["sources"],
            "days": item["days"],
            "articleCount": item["count"],
            "isMarketing": item["is_marketing"],
            "isFresh": item["is_fresh"],
            "isOngoing": item["is_ongoing"],
            # 표의 모든 행을 클릭 가능하게 하려면 근거 기사가 있어야 한다
            # (예전엔 신규/지속 목록에만 articles가 있어서 "관찰" 행은
            # 클릭이 안 됐다) — 이미 메모리에 있는 window_members를 그대로
            # 재사용하니 추가 쿼리 없이 채울 수 있다.
            "articles": [
                {"title": a.title, "url": a.url, "source": a.source} for a in item["members"][:5]
            ],
        }
        for item in sorted(candidates, key=lambda item: -item["count"])[:20]
    ]

    # "신규 진입" 이슈는 갓 생겨서 기사가 몇 건 안 쌓였을 때가 많아, 위
    # top-20(기사 수 기준)에는 애초에 잘 안 들어온다 — 그래서 first_seen_at
    # 자체로 별도 조회해야 "이번 주 처음 등장" 목록이 실제로 채워진다.
    fresh_issue_ids = [row[0] for row in db.execute(
        select(IssueArticle.issue_id)
        .join(Article, Article.id == IssueArticle.article_id)
        .join(Issue, Issue.id == IssueArticle.issue_id)
        .where(
            Issue.category.in_(("GAME", "AI")),
            Issue.first_seen_at >= period_end - timedelta(days=7),
            Article.is_relevant.is_(True),
            article_time >= chart_start,
            article_time < period_end,
        )
        .group_by(IssueArticle.issue_id)
        .order_by(func.count(IssueArticle.article_id).desc())
        .limit(10)
    ).all()]
    fresh_issue_by_id = {
        row.id: row for row in db.execute(select(Issue).where(Issue.id.in_(fresh_issue_ids))).scalars().all()
    } if fresh_issue_ids else {}
    fresh_keywords: set[str] = set()
    fresh_seen_titles: set[str] = set()
    fresh_topics = []
    for issue_id in fresh_issue_ids:
        issue = fresh_issue_by_id.get(issue_id)
        if issue is None:
            continue
        key = issue.title.strip().casefold()
        if not key or key in fresh_seen_titles:
            continue
        fresh_seen_titles.add(key)
        members = [
            a for a in _issue_members(db, issue)
            if (pub := _as_aware_utc(a.published_at or a.collected_at)) is not None and chart_start <= pub < period_end
        ]
        if not members:
            continue
        fresh_topics.append({
            "name": _issue_chart_keyword(issue, members, fresh_keywords),
            "category": issue.category,
            "articleCount": len(members),
            "articles": [{"title": a.title, "url": a.url, "source": a.source} for a in members[:5]],
        })
        if len(fresh_topics) == 6:
            break

    ongoing_keywords: set[str] = set()
    ongoing_topics = [
        {
            "name": _issue_chart_keyword(item["issue"], item["members"], ongoing_keywords),
            "category": item["issue"].category,
            "articleCount": item["count"],
            "articles": [{"title": a.title, "url": a.url, "source": a.source} for a in item["members"][:5]],
        }
        for item in sorted(candidates, key=lambda item: -item["count"])
        if item["is_ongoing"]
    ][:6]

    return {
        "interest": {"labels": labels, "series": interest_series, "bucket": "주간" if weekly else "일간"},
        "topicLandscape": topic_landscape,
        "topicFreshness": {"fresh": fresh_topics, "ongoing": ongoing_topics},
    }


def _policy_impact(db: Session, policies: list[dict], period_end: datetime, limit: int = 2) -> list[dict]:
    """정책 발표 전후로 같은 카테고리 기사량이 실제로 바뀌었는지 확인한다.
    "발표는 했는데 반응은 없었다"와 "발표 직후 보도가 늘었다"를 구분하는
    게 목적이라, 발표일 기준 앞뒤 3일 평균만 비교하면 충분하다 — 정책·
    제도 탭의 최근 1주일 목록(policy_priority)에서 최신 것부터 쓴다.

    측정 기준이 "이 정책 자체에 대한 보도량"이 아니라 "같은 카테고리
    전체 기사량"이라, 같은 날 같은 카테고리에 발표된 정책이 여러 건이면
    (실제로 2026.09.01 AI 정책이 3건 동시 발표된 사례를 확인) 카드마다
    수치가 완전히 똑같아진다 — 서로 구분되지 않는 카드를 나란히 보여줘
    봐야 혼란만 주므로, (카테고리, 발표일)이 겹치는 후보는 건너뛰고 실제로
    구별되는 정책만 limit개 채운다."""
    article_time = func.coalesce(Article.published_at, Article.collected_at)
    impacts = []
    seen_slots: set[tuple[str, str]] = set()
    for policy in policies:
        if len(impacts) >= limit:
            break
        slot = (policy.get("category"), policy.get("publishedDate"))
        if slot in seen_slots:
            continue
        seen_slots.add(slot)
        try:
            event_date = datetime.strptime(policy["publishedDate"], "%Y.%m.%d").replace(tzinfo=KST).astimezone(timezone.utc)
        except (KeyError, ValueError):
            continue
        window_start = event_date - timedelta(days=5)
        window_end = min(event_date + timedelta(days=6), period_end)
        bucket_count = max(1, (window_end - window_start).days)
        if bucket_count < 2:
            continue
        labels = [(window_start + timedelta(days=i)).astimezone(KST).strftime("%m.%d") for i in range(bucket_count)]
        values = [0] * bucket_count
        published_dates = db.execute(
            select(article_time).where(
                Article.category == policy["category"],
                Article.is_relevant.is_(True),
                article_time >= window_start,
                article_time < window_end,
            )
        ).scalars().all()
        for published in published_dates:
            published = _as_aware_utc(published)
            if published is None:
                continue
            index = int((published - window_start).total_seconds() // 86400)
            if 0 <= index < bucket_count:
                values[index] += 1
        event_index = min(bucket_count - 1, int((event_date - window_start).total_seconds() // 86400))
        before = values[max(0, event_index - 3):event_index]
        after = values[event_index:event_index + 3]
        before_avg = round(sum(before) / len(before), 1) if before else 0.0
        after_avg = round(sum(after) / len(after), 1) if after else 0.0
        impacts.append({
            "policyTitle": policy["title"],
            "policyUrl": policy.get("url"),
            "implication": policy.get("implication"),
            "publishedDate": policy["publishedDate"],
            "category": policy["category"],
            "labels": labels,
            "values": values,
            "eventIndex": event_index,
            "beforeAvg": before_avg,
            "afterAvg": after_avg,
        })
    return impacts


def _evidence_sources(db: Session, issue_ids: list[int], now: datetime) -> list[dict]:
    """Resolve only the articles explicitly cited by synthesis issue IDs."""
    if not issue_ids:
        return []
    articles = db.execute(
        select(Article)
        .join(IssueArticle, IssueArticle.article_id == Article.id)
        .where(IssueArticle.issue_id.in_(issue_ids))
        .order_by(Article.published_at.desc().nulls_last())
    ).scalars().all()

    sources = []
    seen_urls: set[str] = set()
    for article in articles:
        if article.url in seen_urls:
            continue
        seen_urls.add(article.url)
        sources.append({
            "outlet": article.source,
            "title": article.title,
            "publishedAgo": _published_ago(article.published_at, now),
            "url": article.url,
        })
        if len(sources) == 5:
            break
    return sources


def _change_list(db: Session, raw_json: str, now: datetime) -> list[dict]:
    items = json.loads(raw_json) if raw_json else []
    return [
        {
            "direction": item["direction"],
            "topic": item["topic"],
            "description": item["description"],
            "sources": _evidence_sources(db, item.get("evidence_issue_ids", []), now),
        }
        for item in items
    ]


def _watch_list(db: Session, raw_json: str, now: datetime) -> list[dict]:
    items = json.loads(raw_json) if raw_json else []
    return [
        {
            "rank": i + 1,
            "topic": item["topic"],
            "description": item["description"],
            "sources": _evidence_sources(db, item.get("evidence_issue_ids", []), now),
        }
        for i, item in enumerate(items)
    ]


def _analysis_stats(db: Session, period_start: datetime, period_end: datetime, ranked: list[dict]) -> dict:
    article_time = func.coalesce(Article.published_at, Article.collected_at)
    period_filter = (article_time >= period_start, article_time < period_end)
    collected = db.execute(
        select(func.count(Article.id)).where(*period_filter)
    ).scalar_one()
    analyzed = db.execute(
        select(func.count(Article.id)).where(Article.classified_at.is_not(None), *period_filter)
    ).scalar_one()
    relevant = db.execute(
        select(func.count(Article.id)).where(Article.is_relevant.is_(True), *period_filter)
    ).scalar_one()
    verified = sum(1 for item in ranked if item["quality"].synthesis_eligible)
    single_source = len(ranked) - verified
    pending=max(0,collected-analyzed)
    completion=round(analyzed * 100 / collected) if collected else 100
    state="COMPLETE" if completion >= 80 else "PARTIAL" if completion >= 40 else "INSUFFICIENT"
    return {
        "collected": collected,
        "analyzed": analyzed,
        "pending": pending,
        "completionRate": completion,
        "analysisStatus": state,
        "relevant": relevant,
        "issues": len(ranked),
        "verifiedIssues": verified,
        "singleSourceIssues": single_source,
    }


def _recommended_articles(db: Session, category: str, period_start: datetime, period_end: datetime) -> list[dict]:
    """Five readable articles without lowering the editorial relevance bar.

    The selected range's relevant articles always lead.  A quiet day is filled
    from the preceding seven days of *already relevant* articles, instead of
    exposing off-topic search candidates merely because they were collected.
    """
    article_time = func.coalesce(Article.published_at, Article.collected_at)
    current_filters = (
        Article.category == category,
        Article.is_relevant.is_(True),
        article_time >= period_start,
        article_time < period_end,
    )
    current = db.execute(
        select(Article)
        .where(*current_filters)
        .order_by(Article.importance_score.desc().nulls_last(), article_time.desc(), Article.id.desc())
        .limit(40)
    ).scalars().all()
    history_start = period_start - timedelta(days=7)
    recent_history = db.execute(
        select(Article)
        .where(
            Article.category == category,
            Article.is_relevant.is_(True),
            article_time >= history_start,
            article_time < period_start,
        )
        .order_by(Article.importance_score.desc().nulls_last(), article_time.desc(), Article.id.desc())
        .limit(60)
    ).scalars().all()

    current_ids = {article.id for article in current}
    candidates = sorted(
        [*current, *recent_history],
        key=lambda article: recommendation_score(article, current_period=article.id in current_ids),
        reverse=True,
    )
    seen_titles: set[str] = set()
    seen_events: set[str] = set()
    recommended: list[dict] = []
    for article in candidates:
        title_key = article.title.strip().casefold()
        article_event = event_key(article)
        if not title_key or title_key in seen_titles or article_event in seen_events or is_promotional(article):
            continue
        seen_titles.add(title_key)
        seen_events.add(article_event)
        published = _as_aware_utc(article.published_at or article.collected_at)
        recommended.append({
            "category": category,
            "title": article.title,
            "url": article.url,
            "publishedDate": published.astimezone(KST).strftime("%Y.%m.%d") if published else "날짜 미상",
        })
        if len(recommended) == 5:
            break
    return recommended

def _serialize_brief(
    db: Session, brief: DailyBrief, stats_period_start: datetime | None = None, stats_period_end: datetime | None = None,
) -> dict:
    now = datetime.now(timezone.utc)
    stats_period_start = stats_period_start or _as_aware_utc(brief.period_start)
    stats_period_end = stats_period_end or _as_aware_utc(brief.period_end)
    game_ai_analysis_raw = json.loads(brief.game_ai_analysis)
    # game_ai_analysis used to store a bare list[str] (the summary paragraphs
    # only) before the "AI 의견" field was split out into its own opinion
    # text — briefs generated before that change still have the old shape
    # in the DB, so handle both rather than breaking their detail view.
    if isinstance(game_ai_analysis_raw, dict):
        game_analysis = game_ai_analysis_raw.get("summary", [])
        game_ai_opinion = game_ai_analysis_raw.get("opinion") or NO_CROSS_OPINION_TEXT
    else:
        game_analysis = game_ai_analysis_raw
        game_ai_opinion = NO_CROSS_OPINION_TEXT
    has_signal = game_analysis != [NO_CROSS_SIGNAL_TEXT]

    # "주요 시그널"을 한때 별도의 최근 1주일 창으로 다시 계산했었는데(모든
    # 신호가 "기사 1건"으로만 나오는 문제를 고치려고) — 실제로 재보니
    # 이슈 클러스터링 비교 비용 때문에 페이지 로딩이 0.23초→3.8초로
    # 크게 느려졌다. 화면이 바로 뜨는 게 더 중요하다는 판단이라, 원래
    # 방식(오늘 창 재사용)으로 되돌린다 — "기사 1건" 문제를 다시 고치고
    # 싶으면, 매 페이지 로드마다 라이브로 재계산하는 대신 refresh_industry_brief
    # 쪽에서 미리 계산해 저장해두는 방식으로 다시 접근해야 한다.
    similarity_cache: dict[tuple[int, int], float] = {}
    game_ranked = _period_ranked_issues(db, "GAME", stats_period_start, stats_period_end, similarity_cache=similarity_cache)
    ai_ranked = _period_ranked_issues(db, "AI", stats_period_start, stats_period_end, similarity_cache=similarity_cache)
    game_details = _period_key_summary_details(game_ranked)
    ai_details = _period_key_summary_details(ai_ranked)
    same_window = (
        abs((_as_aware_utc(brief.period_start) - stats_period_start).total_seconds()) < 60
        and abs((_as_aware_utc(brief.period_end) - stats_period_end).total_seconds()) < 3600
    )
    if not same_window:
        game_analysis = [NO_CROSS_SIGNAL_TEXT]
        game_ai_opinion = NO_CROSS_OPINION_TEXT
        has_signal = False

    period_hours = round((stats_period_end - stats_period_start).total_seconds() / 3600)
    recommended_articles = (
        _recommended_articles(db, "GAME", stats_period_start, stats_period_end)
        + _recommended_articles(db, "AI", stats_period_start, stats_period_end)
    )
    # "주요 정책"과 "변화 타임라인"은 서로 다른 기준 기간을 쓴다 — 주요
    # 정책은 최근 1주일, 타임라인은 올해(1/1~) 전체 흐름을 보여줘야 해서
    # stats_period_start/end 하나로 공유하지 않고 각자의 기간으로 따로
    # 조회한다.
    policy_week_start = stats_period_end - timedelta(days=7)
    policy_priority = build_policy_updates(db, policy_week_start, stats_period_end, limit=30)
    policy_year_start = stats_period_end.astimezone(KST).replace(
        month=1, day=1, hour=0, minute=0, second=0, microsecond=0,
    ).astimezone(timezone.utc)
    policy_timeline = build_policy_updates(db, policy_year_start, stats_period_end, limit=30)

    return {
        "briefDate": brief.brief_date,
        "generatedAt": _as_aware_utc(brief.generated_at).isoformat(),
        "periodLabel": f"지난 {period_hours}시간",
        "articleCount": brief.article_count,
        "analysisStats": _analysis_stats(db, stats_period_start, stats_period_end, game_ranked + ai_ranked),
        "analytics": _brief_analytics(db, stats_period_start, stats_period_end),
        "game": {
            "headline": game_details[0]["text"] if game_details else brief.game_headline,
            "hasSignal": not (len(game_details) == 1 and game_details[0].get("noSignal")),
            "keySummaries": [item["text"] for item in game_details],
            "keySummaryDetails": game_details,
            "observations": _period_observations(game_ranked, now),
            "promotions": promotion_payload(db, "GAME", stats_period_start, stats_period_end),
            "closedObservations": closed_observation_payload(db, "GAME", stats_period_start, stats_period_end),
            "briefing": [item["text"] for item in game_details] or json.loads(brief.game_briefing),
            "changes": _change_list(db, brief.game_changes, now),
            "watchList": _period_watch_list(game_ranked, now),
        },
        "ai": {
            "headline": ai_details[0]["text"] if ai_details else brief.ai_headline,
            "hasSignal": not (len(ai_details) == 1 and ai_details[0].get("noSignal")),
            "keySummaries": [item["text"] for item in ai_details],
            "keySummaryDetails": ai_details,
            "observations": _period_observations(ai_ranked, now),
            "promotions": promotion_payload(db, "AI", stats_period_start, stats_period_end),
            "closedObservations": closed_observation_payload(db, "AI", stats_period_start, stats_period_end),
            "briefing": [item["text"] for item in ai_details] or json.loads(brief.ai_briefing),
            "changes": _change_list(db, brief.ai_changes, now),
            "watchList": _period_watch_list(ai_ranked, now),
        },
        "crossInsight": {"hasSignal": has_signal, "summary": game_analysis, "opinion": game_ai_opinion},
        "recommendedArticles": recommended_articles,
        "signals": _period_signals(game_ranked[:4] + ai_ranked[:4]),
        "newToday": json.loads(brief.new_today),
        "issues": [
            _issue_payload(db, item["issue"], now, item["members"])
            for item in game_ranked + ai_ranked
        ],
        "landscape": build_landscape(db),
        "techRadar": build_tech_radar(db, stats_period_start, stats_period_end),
        "marketComparison": build_market_comparison(db, stats_period_start, stats_period_end),
        "policyUpdates": policy_priority[:6],
        "policyTimeline": sorted(
            policy_timeline, key=lambda item: item["publishedDate"], reverse=True
        ),
        "policyImpact": _policy_impact(db, policy_priority, stats_period_end),
    }


@router.get("/landscape")
def get_industry_landscape(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Historical map based on the planning team’s curated scrape baseline."""
    return build_landscape(db)

@router.get("/landscape/{issue_key}/articles")
def get_landscape_issue_articles(
    issue_key: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return build_issue_detail(db, issue_key)

@router.post("/period/{period}")
def get_period_brief(period: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Read stored articles immediately; period-tab clicks never collect or call AI."""
    if period not in PERIOD_LABELS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "지원하지 않는 기간입니다.")
    start, end, _cache_key = period_window(period)
    base = db.execute(
        select(DailyBrief).where(~DailyBrief.brief_date.contains(":"))
        .order_by(DailyBrief.generated_at.desc(), DailyBrief.id.desc())
    ).scalars().first()
    if base is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "아직 생성된 브리핑이 없습니다.")
    payload = _serialize_brief(db, base, stats_period_start=start, stats_period_end=end)
    payload["periodLabel"] = PERIOD_LABELS[period]
    return payload


@router.post("/day/{date}")
def get_day_brief(date: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The single-date browser that replaced the 오늘/3일/이번주 tabs —
    same computation as /period/{period}, just windowed to one KST calendar
    day instead of a rolling period. `date` is "YYYY-MM-DD"."""
    try:
        start, end = day_window(date)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).")
    base = db.execute(
        select(DailyBrief).where(~DailyBrief.brief_date.contains(":"))
        .order_by(DailyBrief.generated_at.desc(), DailyBrief.id.desc())
    ).scalars().first()
    if base is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "아직 생성된 브리핑이 없습니다.")
    payload = _serialize_brief(db, base, stats_period_start=start, stats_period_end=end)
    payload["periodLabel"] = date
    return payload


@router.get("/highlights/day/{date}")
def get_day_highlights(date: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """핵심 이슈/추천 기사 for one specific calendar date, from whichever
    snapshot(s) were generated that day — see DailyHighlightSnapshot's
    "kept as history, not overwritten" note. Placeholder (hasSignal=false,
    articleCount=0) when no snapshot was ever generated that day, same
    shape as a low-signal day so the frontend needs no separate case."""
    try:
        start, end = day_window(date)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).")
    now = datetime.now(timezone.utc)
    return {
        "game": to_api_dict(load_highlights_for_date(db, "GAME", start, end), "GAME", now),
        "ai": to_api_dict(load_highlights_for_date(db, "AI", start, end), "AI", now),
    }


@router.post("/refresh")
def refresh_latest_brief(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Collect and analyze newly available industry news, then return its brief.

    This is intentionally synchronous so the UI only changes once one coherent,
    evidence-backed snapshot has been persisted. A process-local lock prevents
    duplicate AI calls when the same local user clicks twice.
    """
    if not _REFRESH_LOCK.acquire(blocking=False):
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 업계 동향을 업데이트하고 있습니다.")
    try:
        result = refresh_industry_brief(db)
        brief = db.execute(select(DailyBrief).where(DailyBrief.id == result.brief_id)).scalars().one()
        return {
            "brief": _serialize_brief(db, brief),
            "refresh": {
                "collected": result.collected,
                "classified": result.classified,
                "newIssues": result.new_issues,
                "appendedToIssues": result.appended_to_issues,
            },
        }
    finally:
        _REFRESH_LOCK.release()


@router.get("/highlights")
def get_daily_highlights(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """AI-judged 핵심 이슈(3~5) + 추천 기사 for the last 24h, per category — see
    highlights.py. Serves the latest saved snapshot; use the refresh endpoint
    to recompute. Returns has_signal=false placeholders for a category with
    no snapshot yet rather than triggering an LLM call on a simple page load."""
    now = datetime.now(timezone.utc)
    return {
        "game": to_api_dict(load_latest_highlights(db, "GAME"), "GAME", now),
        "ai": to_api_dict(load_latest_highlights(db, "AI"), "AI", now),
    }


@router.get("/highlights/collected")
def list_collected_articles(
    category: str, db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    """추천 기사 "더보기" 팝업 — 핵심이슈/추천 9건으로 추려지기 전, AI 판단이
    실제로 훑어본 최근 24시간 수집분 전체를 그대로 보여준다."""
    if category not in ("GAME", "AI"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "category는 GAME 또는 AI여야 합니다.")
    now = datetime.now(timezone.utc)
    articles = list_all_window_articles(db, category, now)
    return {
        "category": category,
        "articleCount": len(articles),
        "articles": [{"title": a.title, "url": a.url, "source": a.source} for a in articles],
    }


@router.post("/highlights/refresh")
def refresh_daily_highlights(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Collects fresh articles from the two NAVER sections, then has the AI
    re-judge today's 핵심 이슈/추천 기사 for both categories. Reuses the same
    process-local lock as /refresh so the two can't run concurrently.

    Deliberately skips classify_pending(): _fetch_window_articles() in
    highlights.py reads straight off category/source/collected_at, not
    classified_at, so classification adds nothing here — it was only
    burning minutes grinding through the (large, mostly unrelated)
    classification backlog shared with /refresh, which made this endpoint
    look hung and left every concurrent refresh attempt bouncing off the
    shared lock with a 409."""
    if not _REFRESH_LOCK.acquire(blocking=False):
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 업계 동향을 업데이트하고 있습니다.")
    try:
        collect_all(db)
        now = datetime.now(timezone.utc)
        game = refresh_and_save_highlights(db, "GAME", now)
        ai = refresh_and_save_highlights(db, "AI", now)
        return {"game": to_api_dict(game, "GAME", now), "ai": to_api_dict(ai, "AI", now)}
    finally:
        _REFRESH_LOCK.release()


@router.post("/issues/{issue_id}/feedback")
def submit_issue_feedback(
    issue_id: int,
    payload: IssueFeedbackIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    issue = db.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "이슈를 찾을 수 없습니다.")
    feedback = db.execute(select(IssueFeedback).where(
        IssueFeedback.issue_id == issue_id,
        IssueFeedback.user_id == user.id,
        IssueFeedback.verdict == payload.verdict,
    )).scalar_one_or_none()
    if feedback is None:
        feedback = IssueFeedback(
            issue_id=issue_id, user_id=user.id, verdict=payload.verdict, reason=payload.reason,
        )
        db.add(feedback)
    else:
        feedback.reason = payload.reason
    db.commit()
    return {"issueId": issue_id, "verdict": payload.verdict, "applied": True}


@router.get("/feedback")
def list_issue_feedback(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(IssueFeedback, Issue).join(Issue, Issue.id == IssueFeedback.issue_id)
        .where(IssueFeedback.verdict == "NOT_CORE")
        .order_by(IssueFeedback.created_at.desc())
    ).all()
    grouped: dict[int, dict] = {}
    for feedback, issue in rows:
        item = grouped.setdefault(issue.id, {
            "issueId": issue.id,
            "title": issue.title,
            "category": issue.category,
            "feedbackCount": 0,
            "createdAt": _as_aware_utc(feedback.created_at).isoformat(),
            "reasonCounts": {},
        })
        item["feedbackCount"] += 1
        reason = feedback.reason or "OTHER"
        item["reasonCounts"][reason] = item["reasonCounts"].get(reason, 0) + 1
    return list(grouped.values())


def _preview_risk(issue_count: int, article_count: int, core_count: int) -> tuple[str, list[str]]:
    warnings = []
    if core_count >= 3:
        warnings.append(f"현재 핵심 후보 {core_count}개가 제외될 수 있습니다.")
    if issue_count >= 8:
        warnings.append(f"현재 이슈 {issue_count}개에 영향을 줍니다.")
    if article_count >= 30:
        warnings.append(f"연결 기사 {article_count}건이 영향을 받습니다.")
    return ("CAUTION" if warnings else "SAFE", warnings)


def _build_rule_preview(db: Session, pattern_value: str, reason: str) -> dict:
    start, end, _ = period_window("today")
    pattern = pattern_value.strip().casefold()
    matched = []
    article_ids: set[int] = set()
    core_candidates = 0
    for category in ("GAME", "AI"):
        ranked = _period_ranked_issues(db, category, start, end, limit=100)
        for item in ranked:
            issue = item["issue"]
            members = item["members"]
            text = " ".join([issue.title, issue.summary or "", *(article.title for article in members)]).casefold()
            if pattern not in text:
                continue
            eligible = (
                item["quality"].synthesis_eligible
                and is_core_summary_candidate(issue, members)
                and not item["hasNegativeFeedback"]
            )
            core_candidates += int(eligible)
            article_ids.update(article.id for article in members)
            matched.append({
                "issueId": issue.id,
                "category": issue.category,
                "title": issue.title,
                "articleCount": len(members),
                "coreCandidate": eligible,
                "sources": list(dict.fromkeys(article.source for article in members))[:3],
            })
    matched.sort(key=lambda item: (item["coreCandidate"], item["articleCount"]), reverse=True)
    risk_level, warnings = _preview_risk(len(matched), len(article_ids), core_candidates)
    return {
        "pattern": pattern,
        "reason": reason,
        "issueCount": len(matched),
        "articleCount": len(article_ids),
        "coreCandidateCount": core_candidates,
        "riskLevel": risk_level,
        "warnings": warnings,
        "issues": matched[:20],
    }


@router.get("/feedback/rules")
def get_feedback_rules(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    active = db.execute(
        select(EditorialRule).where(EditorialRule.status == "ACTIVE").order_by(EditorialRule.created_at.desc())
    ).scalars().all()
    audits = db.execute(
        select(EditorialRuleAudit).order_by(EditorialRuleAudit.created_at.desc()).limit(30)
    ).scalars().all()
    return {
        "suggestions": rule_suggestions(db),
        "activeRules": [{
            "id": rule.id, "pattern": rule.pattern, "reason": rule.reason,
            "createdAt": _as_aware_utc(rule.created_at).isoformat(),
            "impact": _build_rule_preview(db, rule.pattern, rule.reason),
        } for rule in active],
        "history": [{
            "id": audit.id,
            "ruleId": audit.rule_id,
            "action": audit.action,
            "actorName": audit.actor_name,
            "actorEmail": audit.actor_email,
            "pattern": audit.pattern,
            "reason": audit.reason,
            "issueCount": audit.impact_issue_count,
            "articleCount": audit.impact_article_count,
            "coreCandidateCount": audit.impact_core_count,
            "riskLevel": audit.risk_level,
            "createdAt": _as_aware_utc(audit.created_at).isoformat(),
        } for audit in audits],
    }


@router.post("/feedback/rules/preview")
def preview_feedback_rule(
    payload: EditorialRuleIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _build_rule_preview(db, payload.pattern, payload.reason)


@router.post("/feedback/rules")
def approve_feedback_rule(
    payload: EditorialRuleIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    preview = _build_rule_preview(db, payload.pattern, payload.reason)
    if preview["riskLevel"] == "CAUTION" and not payload.confirmBroadImpact:
        raise HTTPException(status.HTTP_409_CONFLICT, {
            "message": "영향 범위가 넓어 확인이 필요합니다.",
            "preview": preview,
        })
    pattern = payload.pattern.strip().casefold()
    rule = db.execute(select(EditorialRule).where(
        EditorialRule.pattern == pattern, EditorialRule.reason == payload.reason,
    )).scalar_one_or_none()
    if rule is None:
        rule = EditorialRule(pattern=pattern, reason=payload.reason, status="ACTIVE", created_by=user.id)
        db.add(rule)
        db.flush()
        action = "APPROVED"
    else:
        action = "REACTIVATED" if rule.status != "ACTIVE" else "APPROVED"
        rule.status = "ACTIVE"
        rule.created_by = user.id
    db.add(EditorialRuleAudit(
        rule_id=rule.id, action=action, actor_id=user.id, actor_name=user.name,
        actor_email=user.email, pattern=rule.pattern, reason=rule.reason,
        impact_issue_count=preview["issueCount"], impact_article_count=preview["articleCount"],
        impact_core_count=preview["coreCandidateCount"], risk_level=preview["riskLevel"],
    ))
    db.commit(); db.refresh(rule)
    return {"id": rule.id, "pattern": rule.pattern, "reason": rule.reason, "status": rule.status}


@router.delete("/feedback/rules/{rule_id}")
def deactivate_feedback_rule(
    rule_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rule = db.get(EditorialRule, rule_id)
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "편집 규칙을 찾을 수 없습니다.")
    preview = _build_rule_preview(db, rule.pattern, rule.reason)
    rule.status = "INACTIVE"
    db.add(EditorialRuleAudit(
        rule_id=rule.id, action="DEACTIVATED", actor_id=user.id, actor_name=user.name,
        actor_email=user.email, pattern=rule.pattern, reason=rule.reason,
        impact_issue_count=preview["issueCount"], impact_article_count=preview["articleCount"],
        impact_core_count=preview["coreCandidateCount"], risk_level=preview["riskLevel"],
    ))
    db.commit()
    return {"id": rule_id, "active": False}


@router.delete("/issues/{issue_id}/feedback")
def clear_issue_feedback(
    issue_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    deleted = db.execute(delete(IssueFeedback).where(
        IssueFeedback.issue_id == issue_id,
        IssueFeedback.verdict == "NOT_CORE",
    )).rowcount
    db.commit()
    return {"issueId": issue_id, "restored": bool(deleted)}

@router.get("/latest")
def get_latest_brief(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Range-tab snapshots use keys such as "2026-08-12:3d".  The latest
    # endpoint must never return one of them for the default daily board.
    brief = db.execute(
        select(DailyBrief)
        .where(~DailyBrief.brief_date.contains(":"))
        .order_by(DailyBrief.brief_date.desc(), DailyBrief.id.desc())
    ).scalars().first()
    if brief is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "아직 생성된 브리핑이 없습니다.")
    now = datetime.now(timezone.utc)
    today_start, _, _ = period_window("today", now)
    return _serialize_brief(db, brief, stats_period_start=today_start, stats_period_end=now)






