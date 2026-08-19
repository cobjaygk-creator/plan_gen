"""Phase 6: AI Brief synthesis (design doc section 36 "AI 브리핑 종합" —
GAME Brief, AI Brief, GAME×AI cross-insight, Watch List, Why It Matters).
Reuses tools/ai_client.py's classify() like Phase 3, but with a larger
"analysis tier" model (BRIEF_ANALYSIS_MODEL) since this synthesizes across
several issues instead of classifying one article.

Grounding discipline: the AI only ever sees real Issue/Article data already
in the DB (titles, summaries, source counts, Phase 5 trend directions) and
is told explicitly not to invent facts beyond it. When a category has zero
relevant issues today, no AI call is made at all — a fixed Korean fallback
string is used instead, so the model never has to (and can't) hallucinate
a briefing from nothing. Same for the cross-insight when either side is
empty (spec section 12's exact fallback text)."""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.ai_client import classify, ClassificationError

from .models import Article, DailyBrief, Issue, IssueArticle
from .trends import DEFAULT_BASELINE_DAYS, TopicTrend, compute_daily_trends, new_today
from .keyword_taxonomy import classify_signal_keyword
from .ai_editorial_policy import is_ai_brief_context_issue
from .editorial_ranking import editorial_score, is_core_summary_candidate, issue_event_key
from .editorial_history import record_editorial_states
from .trust import evaluate_evidence, trusted_issue_score
from .periods import KST, period_window

BRIEF_AI_PROVIDER = os.environ.get("BRIEF_AI_PROVIDER", "openai")
# A step up from CLASSIFIER_MODEL (classifier.py) — this synthesizes across
# several issues at once rather than judging one article, so it gets the
# more capable "analysis tier" model. Not hardcoded (spec section 22).
ANALYSIS_MODEL = os.environ.get("BRIEF_ANALYSIS_MODEL", "gpt-4o")

NO_DATA_HEADLINE = "오늘은 분석할 만큼 충분한 자료가 수집되지 않았습니다."
NO_DATA_BRIEFING = "오늘 수집된 관련 기사가 부족해 의미 있는 브리핑을 작성할 수 없습니다. 다음 수집 주기를 기다려주세요."
NO_CROSS_SIGNAL_TEXT = "오늘은 두 산업을 연결할 만큼 뚜렷한 공통 신호가 확인되지 않았습니다."
NO_CROSS_OPINION_TEXT = "현재는 두 산업을 직접 연결할 만큼 충분한 근거가 없습니다. 각 산업의 개별 변화가 누적되는지 계속 관찰합니다."

TOP_ISSUES_PER_CATEGORY = 8
MAX_TRENDS_IN_PROMPT = 10
MIN_RELEVANT_ARTICLES = 50
PERIOD_CANDIDATE_HOURS = (24, 36, 48)

SYSTEM_PROMPT = """\
너는 게임업계 또는 AI업계 동향을 종합해서 하루짜리 산업 브리핑을 작성하는
시니어 애널리스트다. 아래로 주어지는 실제 이슈 목록(제목/요약/출처 수/신뢰도)과
오늘의 키워드 트렌드(전일 대비 상승/유지/하락)만 근거로 삼아라.

- headline: 카드의 "오늘의 핵심"에 들어갈 한국어 한 문장 브리핑(최대 55자). 반드시 입력 이슈의 고유명(모델·제품·기업·프로젝트명) 1개 이상과 실제 사건을 포함해라. "AI 혁신", "경쟁 심화" 같은 포괄 표현만으로 쓰지 마라.
- headline은 기사 제목을 그대로 복사하면 안 된다. 가능하면 두 개 이상의 실제 이슈를 "A 등 B"로 연결하고, 반드시 "주목받고 있습니다" 또는 "확대되고 있습니다" 같은 브리핑 종결형으로 끝내라.
- briefing: 2~3개 문단. 개별 이슈를 나열하지 말고, 여러 이슈를 관통하는
  흐름으로 종합해라.
- changes: 주어진 트렌드 목록 중 의미 있는 것만 골라 up/flat/down과 설명을
  붙여라. 트렌드 목록에 없는 주제를 새로 만들어내지 마라. 각 항목의 판단
  근거가 된 이슈 id를 evidence_issue_ids에 1개 이상 넣어라.
- watchlist: 앞으로 지켜볼 만한 주제 1~3개. description은 카드에 들어갈 최대 42자의 짧은 한 문장으로, 배경 설명을 늘어놓지 말고 관찰 포인트만 써라. 각 항목의 판단
  근거가 된 이슈 id를 evidence_issue_ids에 1개 이상 넣어라.
- evidence_issue_ids에는 반드시 위 이슈 목록에 실제로 있는 id만 넣어라.
- issue_why: 주어진 각 이슈 id에 대해, 이 이슈가 왜 업계에 중요한지 한국어
  한 문장. 주어진 이슈 id 전부에 대해 작성해라.

주어진 자료에 실제로 없는 사실은 만들어내지 마라. 근거 기사에 공통으로 확인되는
사실과 한 기사에만 존재하는 주장을 구분해라. 단일 출처 주장은 핵심 결론으로 사용하지
말고, 근거가 부족하거나 상충하면 무엇이 미확인인지 명시해라."""

CROSS_SYSTEM_PROMPT = """\
너는 게임업계와 AI업계를 함께 보는 시니어 애널리스트다. 아래 게임업계 이슈
목록과 AI업계 이슈 목록을 보고, 두 산업을 실제로 연결하는 뚜렷한 공통 신호가
있는지 판단해라.

- 억지로 연결고리를 만들어내지 마라. 두 목록 사이에 실질적인 공통 주제나
  인과관계가 보이지 않으면 has_signal=false로 답하고 summary와 opinion은
  빈 값으로 둬라.
- has_signal=true인 경우:
  - summary는 한국어 1~2문단으로 두 산업이 실제로 어떻게 연결되는지
    사실관계 위주로 설명해라 (주어진 이슈 내용에 근거해서만).
  - opinion은 summary와 다른 내용이어야 한다. "관찰하세요" 같은 뻔한
    권고나 summary 재진술은 금지한다. 반드시 3문장(최소 150자, 최대 280자)의
    짧은 애널리스트 메모로 작성한다.
    1) [영향] 이 신호가 게임의 개발·운영·콘텐츠·비즈니스 중 어디를 어떻게
       바꿀 가능성이 있는지,
    2) [기회·리스크] 수혜 가능 주체와 실행·비용·품질·권리 측면의 제약 중
       실제 자료로 뒷받침되는 것을,
    3) [확인 지표] 제품 출시·도입 사례·파트너십·이용자 반응 등 다음 단계에서
       무엇을 확인하면 판단을 갱신할 수 있는지를 순서대로 담아라.
    이슈 목록에 실제로 없는 사실은 만들어내지 말고, 근거가 약하면 "~로 보인다"
    같은 신중한 표현을 써라."""


class ChangeItemOut(BaseModel):
    direction: Literal["up", "flat", "down"]
    topic: str
    description: str
    evidence_issue_ids: list[int] = Field(
        min_length=1, description="이 판단의 근거가 된 입력 이슈 id 목록"
    )


class WatchItemOut(BaseModel):
    topic: str
    description: str
    evidence_issue_ids: list[int] = Field(
        min_length=1, description="이 판단의 근거가 된 입력 이슈 id 목록"
    )


class IssueWhyItem(BaseModel):
    issue_id: int
    why_it_matters: str = Field(description="이 이슈가 왜 중요한지 한국어 한 문장")


class PanelSynthesis(BaseModel):
    headline: str
    briefing: list[str] = Field(description="2~3개의 한국어 문단")
    changes: list[ChangeItemOut] = Field(default_factory=list)
    watchlist: list[WatchItemOut] = Field(default_factory=list)
    issue_why: list[IssueWhyItem] = Field(default_factory=list)


class CrossInsightOut(BaseModel):
    has_signal: bool
    summary: list[str] = Field(default_factory=list)
    opinion: str = Field(
        default="", description="정확히 3문장의 애널리스트 메모(150~280자): 영향, 기회·리스크, 확인 지표 순서"
    )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _top_issues(
    db: Session,
    category: str,
    period_start: datetime,
    period_end: datetime,
    limit: int = TOP_ISSUES_PER_CATEGORY,
) -> list[Issue]:
    # Fetch a wider candidate set, then rank distinct real-world events rather
    # than letting syndicated coverage of one announcement occupy many slots.
    rows = list(
        db.execute(
            select(Issue)
            .where(
                Issue.category == category,
                Issue.last_seen_at >= period_start,
                Issue.last_seen_at < period_end,
            )
            .order_by(Issue.importance_score.desc().nulls_last(), Issue.last_seen_at.desc())
            .limit(limit * 20)
        ).scalars().all()
    )
    candidates: list[tuple[Issue, list[Article], float, str | None]] = []
    for issue in rows:
        if category == "AI" and is_ai_brief_context_issue(issue.title):
            continue
        members = _issue_sources(db, issue)
        if not is_core_summary_candidate(issue, members):
            continue
        quality = evaluate_evidence(members)
        if not quality.synthesis_eligible and issue.confidence != "STRONG":
            continue
        score = trusted_issue_score(editorial_score(issue, members), members)
        candidates.append((issue, members, score, issue_event_key(issue, members)))

    candidates.sort(key=lambda item: (item[2], item[0].last_seen_at), reverse=True)
    selected: list[Issue] = []
    seen_events: set[str] = set()
    for issue, _members, _score, event_key in candidates:
        if event_key and event_key in seen_events:
            continue
        if event_key:
            seen_events.add(event_key)
        selected.append(issue)
        if len(selected) == limit:
            break
    return selected

def _effective_article_time():
    return func.coalesce(Article.published_at, Article.collected_at)


def _select_period(db: Session, period_end: datetime) -> tuple[datetime, int]:
    """Use 24h normally, expanding to 36h/48h only below the 50-article floor."""
    article_time = _effective_article_time()
    for hours in PERIOD_CANDIDATE_HOURS:
        period_start = period_end - timedelta(hours=hours)
        relevant_count = db.execute(
            select(func.count(Article.id)).where(
                Article.is_relevant.is_(True),
                article_time >= period_start,
                article_time < period_end,
            )
        ).scalar_one()
        if relevant_count >= MIN_RELEVANT_ARTICLES or hours == PERIOD_CANDIDATE_HOURS[-1]:
            return period_start, relevant_count
    raise AssertionError("period candidates must not be empty")


def _issue_sources(db: Session, issue: Issue) -> list[Article]:
    return list(
        db.execute(
            select(Article).join(IssueArticle, IssueArticle.article_id == Article.id)
            .where(IssueArticle.issue_id == issue.id)
        ).scalars().all()
    )


def _issue_block(db: Session, issue: Issue) -> str:
    members = sorted(
        _issue_sources(db, issue),
        key=lambda article: article.published_at or article.collected_at,
        reverse=True,
    )
    quality = evaluate_evidence(members)
    sources = ", ".join(sorted({m.source for m in members})) or "\uc54c \uc218 \uc5c6\uc74c"
    evidence_lines = []
    for article in members[:5]:
        published = article.published_at or article.collected_at
        evidence_lines.append(
            f"    * [{article.source}] {article.title} | {published.date().isoformat() if published else '\ub0a0\uc9dc \ubbf8\uc0c1'} | "
            f"{(article.summary or '\uc694\uc57d \uc5c6\uc74c')[:260]}"
        )
    return (
        f"- id={issue.id} | {issue.title}\n"
        f"  \uc694\uc57d: {issue.summary or '(\uc5c6\uc74c)'}\n"
        f"  \uac80\uc99d: {quality.verification_status} | \ub3c5\ub9bd \ucd9c\ucc98 {quality.independent_sources}\uac1c | "
        f"\uacf5\uc2dd {quality.official_count}\uac74 | \ucd9c\ucc98: {sources}\n"
        f"  \ub77c\uc774\ud504\uc0ac\uc774\ud074: {issue.lifecycle}\n"
        f"  \uadfc\uac70 \uae30\uc0ac:\n" + "\n".join(evidence_lines)
    )

def _trend_block(trends: list[TopicTrend]) -> str:
    lines = [
        f"- {t.topic}: {t.direction} (오늘 {t.today_count}건, 최근 {DEFAULT_BASELINE_DAYS}일 평균 {t.baseline_avg:.1f}건)"
        for t in trends[:MAX_TRENDS_IN_PROMPT]
    ]
    return "\n".join(lines) if lines else "(트렌드 데이터 없음)"


def _fallback_panel() -> PanelSynthesis:
    return PanelSynthesis(headline=NO_DATA_HEADLINE, briefing=[NO_DATA_BRIEFING])


def _synthesize_panel(db: Session, category: str, issues: list[Issue], trends: list[TopicTrend]) -> PanelSynthesis:
    if not issues:
        return _fallback_panel()

    issue_blocks = "\n".join(_issue_block(db, issue) for issue in issues)
    user_prompt = (
        f"업종: {category}\n\n이슈 목록:\n{issue_blocks}\n\n"
        f"오늘의 키워드 트렌드:\n{_trend_block(trends)}"
    )
    try:
        return classify(SYSTEM_PROMPT, user_prompt, PanelSynthesis, ANALYSIS_MODEL, provider=BRIEF_AI_PROVIDER)
    except ClassificationError:
        return _fallback_panel()


def _synthesize_cross_insight(db: Session, game_issues: list[Issue], ai_issues: list[Issue]) -> CrossInsightOut:
    if not game_issues or not ai_issues:
        return CrossInsightOut(has_signal=False, summary=[])

    user_prompt = (
        "게임업계 이슈:\n" + "\n".join(_issue_block(db, i) for i in game_issues) +
        "\n\nAI업계 이슈:\n" + "\n".join(_issue_block(db, i) for i in ai_issues)
    )
    try:
        return classify(CROSS_SYSTEM_PROMPT, user_prompt, CrossInsightOut, ANALYSIS_MODEL, provider=BRIEF_AI_PROVIDER)
    except ClassificationError:
        return CrossInsightOut(has_signal=False, summary=[])


def _apply_issue_why(db: Session, panel: PanelSynthesis) -> None:
    for item in panel.issue_why:
        issue = db.get(Issue, item.issue_id)
        if issue is not None:
            issue.why_it_matters = item.why_it_matters


def _signal_state(trend: TopicTrend, source_count: int) -> tuple[str, str]:
    if trend.is_new:
        return "NEW", "새로 등장"
    if trend.direction == "up" and source_count >= 3:
        return "EXPANDING", "확산 중"
    if trend.direction == "up":
        return "GROWING", "증가 중"
    if trend.direction == "down":
        return "DECLINING", "약화 중"
    return "CONTINUING", "지속 관찰"


def _signal_title(title: str, summary: str | None, event_type: str) -> str:
    """Card label: concrete subject + event, never a clipped news sentence."""
    text = f"{title} {summary or ''}"
    if "'" in title and title.count("'") >= 2:
        subject = title.split("'")[1].strip()
    elif "‘" in title and "’" in title:
        subject = title.split("‘", 1)[1].split("’", 1)[0].strip()
    else:
        subject = title.split(",", 1)[0].split("…", 1)[0].strip()
    normalized = text.casefold()
    if "유상 증자" in normalized:
        event = "AI반도체 증자" if "반도체" in text else "유상증자"
    elif "투자" in text or "출자" in text:
        event = "투자"
    elif "인수" in text or "합병" in text:
        event = "인수·합병"
    elif "보안" in text or "취약" in text or "해킹" in text:
        event = "보안 이슈"
    elif "규제" in text or "등급" in text or "정책" in text:
        event = "규제 이슈"
    elif "판매" in text or "매출" in text or "실적" in text:
        event = "판매·실적"
    elif "업데이트" in text or "패치" in text:
        event = "업데이트"
    else:
        event = "공개" if "공개" in text else ("출시" if "출시" in text or "신작" in text else event_type)
    label = f"{subject} {event}".strip()
    return label if len(label) <= 24 else label[:23].rstrip() + "…"

def _signal_domain(issue: Issue, members: list[Article]) -> str:
    text = " ".join([issue.title, issue.summary or "", *(article.title for article in members)]).casefold()
    has_ai = any(term in text for term in (" ai", "ai ", "인공지능", "생성형", "llm", "모델"))
    has_game = any(term in text for term in ("게임", "game", "mmorpg", "게임사", "npc"))
    if has_ai and has_game:
        return "GAME_AI"
    return issue.category

def _event_type(title: str, summary: str | None) -> str:
    """A compact, evidence-derived event label for scanning signal cards."""
    text = f"{title} {summary or ''}".casefold()
    if any(term in text for term in ("해킹", "취약", "보안", "유출", "랜섬")):
        return "보안"
    if any(term in text for term in ("인수", "합병", "m&a", "투자", "유상 증자", "펀딩", "출자")):
        return "투자·M&A"
    if any(term in text for term in ("규제", "정책", "등급", "법안", "제재")):
        return "정책·규제"
    if any(term in text for term in ("업데이트", "패치", "개선", "버전", "업그레이드")):
        return "업데이트"
    if any(term in text for term in ("출시", "공개", "신작", "론칭", "release", "launch")):
        return "출시·공개"
    if any(term in text for term in ("매출", "실적", "판매", "수익", "배당")):
        return "실적·시장"
    return "업계 이슈"

_EVENT_IMPACT_BONUS = {
    "보안": 35, "정책·규제": 32, "출시·공개": 28,
    "투자·M&A": 24, "업데이트": 16, "실적·시장": 14, "업계 이슈": 8,
}


def _signal_priority(issue: Issue, event_type: str, members: list[Article], source_count: int) -> int:
    """Rank by decision impact, not merely the frequency of a broad keyword."""
    official_count = sum(article.source_type == "official" for article in members)
    base = round(issue.importance_score or 0)
    return base + _EVENT_IMPACT_BONUS[event_type] + min(source_count, 5) * 9 + min(official_count, 2) * 10

def _priority_reason(issue: Issue, event_type: str, members: list[Article], source_count: int) -> str:
    reasons = [event_type]
    if any(article.source_type == "official" for article in members):
        reasons.append("공식 발표")
    elif source_count >= 2:
        reasons.append(f"{source_count}개 매체 확인")
    elif (issue.importance_score or 0) >= 75:
        reasons.append("핵심 이슈")
    else:
        reasons.append("최근 포착")
    return " · ".join(reasons)

def _issue_signal_payload(
    db: Session, issues: list[Issue], period_start: datetime, period_end: datetime,
) -> list[dict]:
    """Turn concrete clustered events into the dashboard's primary signals.

    A title such as a model launch, free-tier change or security incident is
    deliberately retained. Generic keyword frequency remains a fallback only,
    because it says little when "AI" is present every day of the year.
    """
    payload: list[dict] = []
    for issue in issues:
        members = db.execute(
            select(Article).join(IssueArticle, IssueArticle.article_id == Article.id)
            .where(IssueArticle.issue_id == issue.id)
            .where(Article.published_at >= period_start, Article.published_at < period_end)
            .order_by(Article.published_at.desc().nulls_last())
        ).scalars().all()
        if not members:
            continue
        sources = {article.source for article in members}
        kind, kind_label = classify_signal_keyword(issue.title, members)
        event_type = _event_type(issue.title, issue.summary)
        domain = _signal_domain(issue, members)
        domain = _signal_domain(issue, members)
        priority = _signal_priority(issue, event_type, members, len(sources))
        priority_reason = _priority_reason(issue, event_type, members, len(sources))
        state, state_label = (
            ("EXPANDING", "확산 중") if len(sources) >= 3 else ("NEW", "새로 등장")
        )
        payload.append({
            "topic": _signal_title(issue.title, issue.summary, event_type),
            "direction": "up",
            "weight": priority,
            "kind": kind,
            "kindLabel": kind_label,
            "eventType": event_type,
            "domain": domain,
            "priorityReason": priority_reason,
            "state": state,
            "stateLabel": state_label,
            "todayCount": len(members),
            "baselineAverage": 0,
            "sourceCount": len(sources),
            "reason": issue.summary or "이번 기간에 새롭게 포착된 업계 이슈입니다.",
            "evidence": [
                {"outlet": article.source, "title": article.title, "url": article.url}
                for article in members[:3]
            ],
        })
    return sorted(payload, key=lambda item: (item["weight"], item["sourceCount"], item["todayCount"]), reverse=True)[:16]


def _keyword_signals_payload(db: Session, trends: list[TopicTrend], reference_date: datetime) -> list[dict]:
    """Fallback only when no concrete issue has enough evidence."""
    max_count = max((t.today_count for t in trends), default=0)
    start = reference_date - timedelta(days=1)
    payload = []
    for trend in trends[:MAX_TRENDS_IN_PROMPT]:
        articles = db.execute(
            select(Article).where(
                Article.category == trend.category, Article.is_relevant.is_(True),
                Article.published_at >= start, Article.published_at < reference_date,
            ).order_by(Article.published_at.desc().nulls_last())
        ).scalars().all()
        matching = [article for article in articles if trend.topic in (json.loads(article.keywords) if article.keywords else [])]
        source_count = len({article.source for article in matching})
        kind, kind_label = classify_signal_keyword(trend.topic, matching)
        state, state_label = _signal_state(trend, source_count)
        payload.append({
            "topic": trend.topic, "direction": trend.direction,
            "weight": round((trend.today_count / max_count) * 100) if max_count else 0,
            "kind": kind, "kindLabel": kind_label, "eventType": "키워드", "domain": trend.category, "priorityReason": "반복 관찰", "state": state, "stateLabel": state_label,
            "todayCount": trend.today_count, "baselineAverage": round(trend.baseline_avg, 1),
            "sourceCount": source_count,
            "reason": f"최근 24시간 {trend.today_count}건으로, 직전 7일 일평균 {trend.baseline_avg:.1f}건과 비교해 {state_label} 상태입니다.",
            "evidence": [{"outlet": article.source, "title": article.title, "url": article.url} for article in matching[:3]],
        })
    return payload

def _topic_source_stats(db: Session, category: str, topic: str, start: datetime, end: datetime) -> tuple[int, int]:
    """(independent source count, official source count) for articles that
    carry `topic` as a keyword within [start, end) — used to give New Today
    items the same source-diversity context the frontend's IssueCard shows,
    without an extra AI call (pure DB aggregation)."""
    articles = db.execute(
        select(Article).where(
            Article.category == category,
            Article.is_relevant.is_(True),
            Article.published_at >= start,
            Article.published_at < end,
        )
    ).scalars().all()
    matching = [a for a in articles if topic in (json.loads(a.keywords) if a.keywords else [])]
    sources = {a.source for a in matching}
    officials = sum(1 for a in matching if a.source_type == "official")
    return len(sources), officials


def _new_today_payload(db: Session, trends: list[TopicTrend], period_start: datetime, period_end: datetime) -> list[dict]:
    payload = []
    for t in new_today(trends):
        independent_sources, official_count = _topic_source_stats(db, t.category, t.topic, period_start, period_end)
        payload.append({
            "topic": t.topic,
            "description": "오늘 관련 발표와 보도가 처음 크게 증가했습니다.",
            "articleCount": t.today_count,
            "independentSources": independent_sources,
            "officialCount": official_count,
        })
    return payload


def generate_daily_brief(
    db: Session, reference_date: datetime | None = None, period_start_override: datetime | None = None,
    brief_date_override: str | None = None,
) -> DailyBrief:
    """Generates and persists one DailyBrief snapshot, and backfills
    Issue.why_it_matters for every issue the AI was asked about. Safe to
    call repeatedly (e.g. once a day from a future scheduler) — each call
    inserts a new row rather than updating a prior one, since a brief is a
    point-in-time snapshot."""
    reference_date = reference_date or _utcnow()
    period_end = reference_date
    if period_start_override is None:
        # The default dashboard snapshot means the KST calendar day, not a
        # rolling 24–48 hour fallback. This keeps it comparable with range tabs.
        period_start, _, _ = period_window("today", period_end)
        article_time = _effective_article_time()
        article_count = db.execute(
            select(func.count(Article.id)).where(
                Article.is_relevant.is_(True), article_time >= period_start, article_time < period_end,
            )
        ).scalar_one()
    else:
        period_start = period_start_override
        article_time = _effective_article_time()
        article_count = db.execute(
            select(func.count(Article.id)).where(
                Article.is_relevant.is_(True), article_time >= period_start, article_time < period_end,
            )
        ).scalar_one()
    game_issues = _top_issues(db, "GAME", period_start, period_end)
    ai_issues = _top_issues(db, "AI", period_start, period_end)
    game_trends = compute_daily_trends(db, "GAME", reference_date)
    ai_trends = compute_daily_trends(db, "AI", reference_date)

    game_panel = _synthesize_panel(db, "GAME", game_issues, game_trends)
    ai_panel = _synthesize_panel(db, "AI", ai_issues, ai_trends)
    cross = _synthesize_cross_insight(db, game_issues, ai_issues)

    _apply_issue_why(db, game_panel)
    _apply_issue_why(db, ai_panel)


    cross_summary = cross.summary if cross.has_signal else [NO_CROSS_SIGNAL_TEXT]
    cross_opinion = cross.opinion if cross.has_signal and cross.opinion else NO_CROSS_OPINION_TEXT

    brief = DailyBrief(
        brief_date=brief_date_override or reference_date.astimezone(KST).strftime("%Y-%m-%d"),
        period_start=period_start,
        period_end=period_end,
        article_count=article_count,
        issue_count=len(game_issues) + len(ai_issues),
        game_headline=game_panel.headline,
        game_briefing=json.dumps(game_panel.briefing, ensure_ascii=False),
        game_changes=json.dumps([c.model_dump() for c in game_panel.changes], ensure_ascii=False),
        game_watchlist=json.dumps([w.model_dump() for w in game_panel.watchlist], ensure_ascii=False),
        ai_headline=ai_panel.headline,
        ai_briefing=json.dumps(ai_panel.briefing, ensure_ascii=False),
        ai_changes=json.dumps([c.model_dump() for c in ai_panel.changes], ensure_ascii=False),
        ai_watchlist=json.dumps([w.model_dump() for w in ai_panel.watchlist], ensure_ascii=False),
        game_ai_analysis=json.dumps({"summary": cross_summary, "opinion": cross_opinion}, ensure_ascii=False),
        signals=json.dumps(_issue_signal_payload(db, game_issues + ai_issues, period_start, period_end) or _keyword_signals_payload(db, game_trends + ai_trends, reference_date), ensure_ascii=False),
        new_today=json.dumps(
            _new_today_payload(db, game_trends + ai_trends, period_start, period_end), ensure_ascii=False
        ),
        status="ok",
    )
    record_editorial_states(db, period_start, period_end, reference_date)
    db.add(brief)
    db.commit()
    db.refresh(brief)
    return brief






