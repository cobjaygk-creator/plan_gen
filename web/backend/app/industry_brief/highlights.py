"""Daily highlights for the redesigned 업계 동향 page: instead of requiring
an issue to be corroborated by multiple outlets before it can appear (see
trust.py), an LLM reads every article collected from the two curated NAVER
section pages (게임/리뷰, IT/과학 — see official_html.NAVER_SECTION_SOURCES)
in the last 24h and directly judges (a) 3-5 핵심 이슈 for the day and (b) a
"추천 기사" reading list of individually noteworthy articles that don't
cluster into an issue with anything else but are still worth surfacing
(e.g. an industry revenue report, an opinion column, a Gamescom preview —
exactly the kind of single-source-but-substantive piece the old
cross-verification gate used to bury). Ads and product-announcement fluff
are excluded; new titles and new AI models/techniques are prioritized.

No persistence yet — computed on demand from the Article table."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.ai_client import classify, ClassificationError

from .models import Article, DailyHighlightSnapshot

HIGHLIGHTS_AI_PROVIDER = os.environ.get("BRIEF_AI_PROVIDER", "openai")
HIGHLIGHTS_MODEL = os.environ.get("BRIEF_HIGHLIGHTS_MODEL", "gpt-4o")

NO_DATA_TEXT = "지난 24시간 동안 분석할 만큼 충분한 기사가 수집되지 않았습니다."

_ARTICLE_WINDOW_HOURS = 24
_MAX_ARTICLES_TO_MODEL = 120
_MAX_RECOMMENDED = 6
_MAX_CORE_ISSUES = 5

SYSTEM_PROMPT = """\
너는 게임업계·AI업계 뉴스를 매일 정리하는 시니어 에디터다. 아래 기사 목록(지난
24시간 동안 네이버 뉴스 게임/AI 섹션에서 수집됨)을 전체적으로 훑어보고 두 가지를
선정해라.

1. core_issues (핵심 이슈, 3~5개): 오늘 업계에서 가장 중요한 사건/발표/흐름.
   여러 기사가 같은 사건을 다뤄도 되고, 단 하나의 기사가 다루는 중요한 발표나
   데이터여도 된다 — 다른 매체가 같은 내용을 보도했는지는 선정 기준이 아니다.
   각 이슈마다 title(제목), summary(1~2문장 요약, 왜 중요한지 포함),
   article_indices(근거가 된 기사의 index 목록, 1개 이상)를 작성해라.

2. recommended (추천 기사, 정확히 6개 — 후보가 부족한 경우가 아니면 6개를
   채워라): 핵심 이슈로 묶이진 않지만 오늘 업계 동향을 파악하는 데 도움이
   되는 개별 기사. 예: 산업 실적/통계 기사, 업계 전망·칼럼, 행사 프리뷰,
   트렌드 분석 기사. 각각 index, one_line_reason(왜 추천하는지 한 줄)을
   작성해라.

선정 기준:
- 제외: 광고성 기사, 단순 상품/아이템 소개, 이벤트 홍보 목적의 보도자료성 기사
- 우선: 신작 게임 발표, AI 신규 모델/기술, 산업 데이터·분석·전망, 의미 있는
  정책/규제 변화
- 기사 목록에 실제로 없는 내용은 만들어내지 마라. article_indices와 index는
  반드시 제공된 목록의 index 값이어야 한다.
- 오늘 자료가 너무 적거나(예: 10건 미만) 의미 있는 이슈를 뽑기 어려우면
  has_signal을 false로 설정하고 core_issues/recommended는 빈 배열로 둬라.
{category_priority}"""

# 실제 8개월치 공유 이력(461건)을 훑어 확인한 카테고리별 우선순위 — 단신 발표보다
# "왜 중요한가" 프레이밍이 있는 기사가 실제로 선택되어 온 패턴, AI 쪽은 게임과
# 무관한 순수 LLM/인프라 뉴스도 꾸준히 선택되어 온 패턴을 반영한다.
_CATEGORY_PRIORITY = {
    "GAME": (
        "GAME 카테고리 추가 기준: 이벤트 참가·신작 출시 발표 자체보다, 그 사건이 "
        "산업적으로 왜 중요한지를 짚은 기사를 우선한다 (예: 단순 '게임스컴 참가' "
        "보다 '게임스컴이 특별한 이유'나 실적·글로벌 진출·정책 변화 관점을 담은 "
        "기사). 반복 축: 글로벌·중국 시장 진출, 정책/규제 변화, 게임사 실적."
    ),
    "AI": (
        "AI 카테고리 추가 기준: 게임과 무관한 순수 LLM/AI 인프라 뉴스(모델 경쟁 "
        "구도, GPU/컴퓨팅 비용, AI 에이전트 등)도 게임 산업과의 접점이 없다는 "
        "이유만으로 배제하지 마라 — 조직/업무 방식의 변화를 다루는 기사도 이 "
        "카테고리의 핵심 축이다."
    ),
}


def _system_prompt_for(category: str) -> str:
    return SYSTEM_PROMPT.format(category_priority=_CATEGORY_PRIORITY.get(category, ""))


class _CoreIssue(BaseModel):
    title: str
    summary: str
    article_indices: list[int] = Field(default_factory=list)


class _RecommendedArticle(BaseModel):
    index: int
    one_line_reason: str


class _HighlightsResult(BaseModel):
    has_signal: bool
    core_issues: list[_CoreIssue] = Field(default_factory=list)
    recommended: list[_RecommendedArticle] = Field(default_factory=list)


def _fetch_window_articles(db: Session, category: str, now: datetime) -> list[Article]:
    start = now - timedelta(hours=_ARTICLE_WINDOW_HOURS)
    return list(db.scalars(
        select(Article)
        .where(
            Article.category == category,
            Article.source.like("NAVER · %"),
            Article.collected_at >= start,
            Article.collected_at <= now,
        )
        .order_by(Article.collected_at.desc())
        .limit(_MAX_ARTICLES_TO_MODEL)
    ))


def _build_user_prompt(articles: list[Article]) -> str:
    lines = []
    for i, article in enumerate(articles):
        summary = (article.summary or "").strip().replace("\n", " ")[:200]
        lines.append(f"[{i}] {article.title} | {article.source} | {article.url}" + (f"\n    요약: {summary}" if summary else ""))
    return "\n".join(lines)


class HighlightIssue(BaseModel):
    title: str
    summary: str
    articles: list[dict]


class RecommendedArticle(BaseModel):
    title: str
    url: str
    source: str
    reason: str


class DailyHighlights(BaseModel):
    category: str
    has_signal: bool
    article_count: int
    generated_at: datetime
    core_issues: list[HighlightIssue] = Field(default_factory=list)
    recommended: list[RecommendedArticle] = Field(default_factory=list)


def generate_daily_highlights(db: Session, category: str, now: datetime | None = None) -> DailyHighlights:
    now = now or datetime.now(timezone.utc)
    articles = _fetch_window_articles(db, category, now)

    if len(articles) < 5:
        return DailyHighlights(category=category, has_signal=False, article_count=len(articles), generated_at=now)

    try:
        result = classify(
            _system_prompt_for(category), _build_user_prompt(articles), _HighlightsResult,
            HIGHLIGHTS_MODEL, provider=HIGHLIGHTS_AI_PROVIDER,
        )
    except ClassificationError:
        return DailyHighlights(category=category, has_signal=False, article_count=len(articles), generated_at=now)

    if not result.has_signal:
        return DailyHighlights(category=category, has_signal=False, article_count=len(articles), generated_at=now)

    core_issues = []
    # The prompt already asks for 3-5, but nothing stops the model from
    # returning more on an unusually busy day — enforce the cap here rather
    # than trust it, since the frontend grid assumes a bounded list.
    for issue in result.core_issues[:_MAX_CORE_ISSUES]:
        members = [articles[i] for i in issue.article_indices if 0 <= i < len(articles)]
        if not members:
            continue
        core_issues.append(HighlightIssue(
            title=issue.title,
            summary=issue.summary,
            articles=[{"title": a.title, "url": a.url, "source": a.source} for a in members],
        ))

    recommended = []
    for rec in result.recommended[:_MAX_RECOMMENDED]:
        if not (0 <= rec.index < len(articles)):
            continue
        article = articles[rec.index]
        recommended.append(RecommendedArticle(
            title=article.title, url=article.url, source=article.source, reason=rec.one_line_reason,
        ))

    return DailyHighlights(
        category=category, has_signal=bool(core_issues or recommended), article_count=len(articles),
        generated_at=now, core_issues=core_issues, recommended=recommended,
    )


def save_highlights(db: Session, highlights: DailyHighlights) -> DailyHighlightSnapshot:
    row = DailyHighlightSnapshot(
        category=highlights.category,
        generated_at=highlights.generated_at,
        has_signal=highlights.has_signal,
        article_count=highlights.article_count,
        payload=highlights.model_dump_json(),
    )
    db.add(row)
    db.commit()
    return row


def refresh_and_save_highlights(db: Session, category: str, now: datetime | None = None) -> DailyHighlights:
    highlights = generate_daily_highlights(db, category, now)
    save_highlights(db, highlights)
    return highlights


def load_latest_highlights(db: Session, category: str) -> DailyHighlights | None:
    row = db.scalar(
        select(DailyHighlightSnapshot)
        .where(DailyHighlightSnapshot.category == category)
        .order_by(DailyHighlightSnapshot.generated_at.desc())
    )
    if row is None:
        return None
    return DailyHighlights.model_validate(json.loads(row.payload))


def load_highlights_for_date(db: Session, category: str, start: datetime, end: datetime) -> DailyHighlights | None:
    """The date-browser's per-day 핵심이슈: snapshots aren't overwritten
    (see DailyHighlightSnapshot's docstring), so this just picks the latest
    one whose generated_at falls within the given day's [start, end)."""
    row = db.scalar(
        select(DailyHighlightSnapshot)
        .where(
            DailyHighlightSnapshot.category == category,
            DailyHighlightSnapshot.generated_at >= start,
            DailyHighlightSnapshot.generated_at < end,
        )
        .order_by(DailyHighlightSnapshot.generated_at.desc())
    )
    if row is None:
        return None
    return DailyHighlights.model_validate(json.loads(row.payload))


def to_api_dict(highlights: DailyHighlights | None, category: str, now: datetime) -> dict:
    """camelCase shape the frontend expects — kept separate from the pydantic
    model (which stays snake_case for the stored JSON payload) rather than
    fighting pydantic's alias machinery for one call site."""
    if highlights is None:
        return {"category": category, "hasSignal": False, "articleCount": 0, "generatedAt": now.isoformat(), "coreIssues": [], "recommended": []}
    return {
        "category": highlights.category,
        "hasSignal": highlights.has_signal,
        "articleCount": highlights.article_count,
        "generatedAt": highlights.generated_at.isoformat(),
        "coreIssues": [{"title": i.title, "summary": i.summary, "articles": i.articles} for i in highlights.core_issues],
        "recommended": [{"title": r.title, "url": r.url, "source": r.source, "reason": r.reason} for r in highlights.recommended],
    }
