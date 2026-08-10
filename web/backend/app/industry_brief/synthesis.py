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

BRIEF_AI_PROVIDER = os.environ.get("BRIEF_AI_PROVIDER", "openai")
# A step up from CLASSIFIER_MODEL (classifier.py) — this synthesizes across
# several issues at once rather than judging one article, so it gets the
# more capable "analysis tier" model. Not hardcoded (spec section 22).
ANALYSIS_MODEL = os.environ.get("BRIEF_ANALYSIS_MODEL", "gpt-4o")

NO_DATA_HEADLINE = "오늘은 분석할 만큼 충분한 자료가 수집되지 않았습니다."
NO_DATA_BRIEFING = "오늘 수집된 관련 기사가 부족해 의미 있는 브리핑을 작성할 수 없습니다. 다음 수집 주기를 기다려주세요."
NO_CROSS_SIGNAL_TEXT = "오늘은 두 산업을 연결할 만큼 뚜렷한 공통 신호가 확인되지 않았습니다."

TOP_ISSUES_PER_CATEGORY = 8
MAX_TRENDS_IN_PROMPT = 10

SYSTEM_PROMPT = """\
너는 게임업계 또는 AI업계 동향을 종합해서 하루짜리 산업 브리핑을 작성하는
시니어 애널리스트다. 아래로 주어지는 실제 이슈 목록(제목/요약/출처 수/신뢰도)과
오늘의 키워드 트렌드(전일 대비 상승/유지/하락)만 근거로 삼아라.

- headline: 오늘 이 산업에서 가장 특징적인 흐름을 한국어 1~2문장으로.
- briefing: 2~3개 문단. 개별 이슈를 나열하지 말고, 여러 이슈를 관통하는
  흐름으로 종합해라.
- changes: 주어진 트렌드 목록 중 의미 있는 것만 골라 up/flat/down과 설명을
  붙여라. 트렌드 목록에 없는 주제를 새로 만들어내지 마라.
- watchlist: 앞으로 지켜볼 만한 주제 1~3개, 순위와 이유.
- issue_why: 주어진 각 이슈 id에 대해, 이 이슈가 왜 업계에 중요한지 한국어
  한 문장. 주어진 이슈 id 전부에 대해 작성해라.

주어진 자료에 실제로 없는 사실은 만들어내지 마라. 근거가 부족하면 신중하게
표현해라 (예: "~로 보입니다" 대신 확정적으로 단정하지 않기)."""

CROSS_SYSTEM_PROMPT = """\
너는 게임업계와 AI업계를 함께 보는 애널리스트다. 아래 게임업계 이슈 목록과
AI업계 이슈 목록을 보고, 두 산업을 실제로 연결하는 뚜렷한 공통 신호가
있는지 판단해라.

- 억지로 연결고리를 만들어내지 마라. 두 목록 사이에 실질적인 공통 주제나
  인과관계가 보이지 않으면 has_signal=false로 답하고 summary는 빈 배열로
  둬라.
- has_signal=true인 경우, summary는 한국어 1~2문단으로 두 산업이 어떻게
  연결되는지 설명해라 (주어진 이슈 내용에 근거해서만)."""


class ChangeItemOut(BaseModel):
    direction: Literal["up", "flat", "down"]
    topic: str
    description: str


class WatchItemOut(BaseModel):
    topic: str
    description: str


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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _top_issues(db: Session, category: str, limit: int = TOP_ISSUES_PER_CATEGORY) -> list[Issue]:
    return list(
        db.execute(
            select(Issue)
            .where(Issue.category == category)
            .order_by(Issue.importance_score.desc().nulls_last())
            .limit(limit)
        ).scalars().all()
    )


def _issue_sources(db: Session, issue: Issue) -> list[Article]:
    return list(
        db.execute(
            select(Article).join(IssueArticle, IssueArticle.article_id == Article.id)
            .where(IssueArticle.issue_id == issue.id)
        ).scalars().all()
    )


def _issue_block(db: Session, issue: Issue) -> str:
    members = _issue_sources(db, issue)
    sources = ", ".join(sorted({m.source for m in members})) or "알 수 없음"
    return (
        f"- id={issue.id} | {issue.title}\n"
        f"  요약: {issue.summary or '(없음)'}\n"
        f"  신뢰도: {issue.confidence or 'WEAK'} | 출처: {sources} | 라이프사이클: {issue.lifecycle}"
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


def _signals_payload(trends: list[TopicTrend]) -> list[dict]:
    max_count = max((t.today_count for t in trends), default=0)
    return [
        {
            "topic": t.topic,
            "direction": t.direction,
            "weight": round((t.today_count / max_count) * 100) if max_count else 0,
        }
        for t in trends[:MAX_TRENDS_IN_PROMPT]
    ]


def _new_today_payload(trends: list[TopicTrend]) -> list[dict]:
    return [{"topic": t.topic, "todayCount": t.today_count} for t in new_today(trends)]


def generate_daily_brief(db: Session, reference_date: datetime | None = None) -> DailyBrief:
    """Generates and persists one DailyBrief snapshot, and backfills
    Issue.why_it_matters for every issue the AI was asked about. Safe to
    call repeatedly (e.g. once a day from a future scheduler) — each call
    inserts a new row rather than updating a prior one, since a brief is a
    point-in-time snapshot."""
    reference_date = reference_date or _utcnow()
    period_start = reference_date - timedelta(days=1)
    period_end = reference_date

    game_issues = _top_issues(db, "GAME")
    ai_issues = _top_issues(db, "AI")
    game_trends = compute_daily_trends(db, "GAME", reference_date)
    ai_trends = compute_daily_trends(db, "AI", reference_date)

    game_panel = _synthesize_panel(db, "GAME", game_issues, game_trends)
    ai_panel = _synthesize_panel(db, "AI", ai_issues, ai_trends)
    cross = _synthesize_cross_insight(db, game_issues, ai_issues)

    _apply_issue_why(db, game_panel)
    _apply_issue_why(db, ai_panel)

    article_count = db.execute(
        select(func.count(Article.id)).where(
            Article.is_relevant.is_(True),
            Article.published_at >= period_start,
            Article.published_at < period_end,
        )
    ).scalar_one()

    cross_summary = cross.summary if cross.has_signal else [NO_CROSS_SIGNAL_TEXT]

    brief = DailyBrief(
        brief_date=reference_date.strftime("%Y-%m-%d"),
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
        game_ai_analysis=json.dumps(cross_summary, ensure_ascii=False),
        signals=json.dumps(_signals_payload(game_trends + ai_trends), ensure_ascii=False),
        new_today=json.dumps(_new_today_payload(game_trends + ai_trends), ensure_ascii=False),
        status="ok",
    )
    db.add(brief)
    db.commit()
    db.refresh(brief)
    return brief
