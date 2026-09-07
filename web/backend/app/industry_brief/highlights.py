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
_MAX_RECOMMENDED = 9
_MAX_CORE_ISSUES = 5

SYSTEM_PROMPT = """\
너는 게임업계·AI업계 뉴스를 매일 정리하는 시니어 에디터다. 아래 기사 목록(지난
24시간 동안 네이버 뉴스 게임/AI 섹션에서 수집됨)을 전체적으로 훑어보고 두 가지를
선정해라.

[언어 규칙 — 반드시 지킬 것] summary, title, one_line_reason을 포함한 모든 텍스트
출력은 예외 없이 한국어 문장으로 작성한다. 원문 기사나 인용문이 영어여도 그대로
옮기거나 영어 문장으로 요약하지 말고 반드시 한국어로 번역해서 서술하라. 인명·
회사명·모델명 등 고유명사의 로마자 표기만 예외로 허용한다.

1. core_issues (핵심 이슈, 반드시 3~5개 — has_signal이 true라면 예외 없이
   최소 3개를 채워야 한다. 화면이 3칸 고정 레이아웃이라 2개 이하로 나오면
   레이아웃이 깨진다): 오늘 업계에서 가장 중요한 사건/발표/흐름.
   여러 기사가 같은 사건을 다뤄도 되고, 단 하나의 기사가 다루는 중요한 발표나
   데이터여도 된다 — 다른 매체가 같은 내용을 보도했는지는 선정 기준이 아니다.
   "이게 3개짜리 이슈로 부를 만큼 중요한가"보다 "이 기사들 중 오늘 언급할
   가치가 있는 걸 3개 고른다면 무엇인가"로 접근해라 — 애매하면 후순위
   후보라도 포함해 3개를 채우고, 정말로 기사 자체가 5건 미만일 때만
   has_signal을 false로 두거나 3개 미만을 허용해라.
   각 이슈마다:
   - title: 짧은 내부 라벨 한 줄 (화면에는 노출되지 않음 — 근거 정리·식별용)
   - summary: 화면 카드에 최대 2줄까지만 보이므로 반드시 1~2문장, 60자
     내외로 짧고 간결하게 써라. "제목: 요약" 식으로 딱딱하게 나열하지 말고,
     날씨 캐스터가 브리핑하듯 사건의 핵심 사실과 왜 중요한지를 한 호흡에
     압축해서 서술해라. title에 해당하는 핵심 사실이 summary 첫 문장에
     자연스럽게 녹아 있어야 한다 (예: "지스타 2026이 크림과 손잡으며 글로벌
     흥행 시험대에 올랐습니다."). 반드시 한국어로 작성하고, 해외 모델·기업
     이름 등 고유명사를 제외한 모든 서술은 한글로 써라 — 원문이 영어 기사여도
     summary 자체를 영어로 쓰지 마라.
   - detail: summary를 클릭해서 열어보는 상세 팝업에만 노출되는 긴 설명.
     3~5문장으로, 배경(왜 이 일이 일어났는지)·핵심 내용(무슨 일이 있었는지
     구체적으로)·의미(업계에 어떤 영향을 주는지)를 순서대로 풀어 써라.
     summary를 그대로 늘여쓰지 말고, summary에 없던 구체적 사실(수치, 배경
     맥락, 다음에 지켜볼 지점 등)을 근거 기사에서 찾아 보태라. summary와
     마찬가지로 반드시 한국어로만 작성한다.
   - article_indices: 근거가 된 기사의 index 목록, 1개 이상

2. recommended (추천 기사, 정확히 9개 — 후보가 부족한 경우가 아니면 9개를
   채워라): 핵심 이슈로 묶이진
   않지만 오늘 업계 동향을 파악하는 데 도움이 되는 개별 기사. 예: 산업
   실적/통계 기사, 업계 전망·칼럼, 행사 프리뷰, 트렌드 분석 기사. 각각
   index, one_line_reason(왜 추천하는지 한 줄)을 작성해라.

선정 기준:
- 제외: 광고성 기사, 단순 상품/아이템 소개, 이벤트 홍보 목적의 보도자료성 기사
- 우선: 신작 게임 발표, AI 신규 모델/기술, 산업 데이터·분석·전망, 의미 있는
  정책/규제 변화
- 개별 기업 하나가 자사 내부 업무에 AI/신기술을 도입·활용한 사례(예: "OO
  제약이 AI로 품질관리 시스템을 구축했다", "OO사가 AI 챗봇을 고객센터에
  도입했다")는 그 자체만으로는 핵심 이슈감이 아니다 — 업계 전체에 영향을
  주는 사건이 아니라 한 회사의 활용 사례일 뿐이기 때문이다. 이런 기사는
  recommended(추천 기사)로 내려보내고, core_issues는 신기술 발표·시장
  판도 변화·대규모 투자/M&A·정책 변화처럼 산업 전반을 흔드는 사건 위주로
  채워라.
- 기사 목록에 실제로 없는 내용은 만들어내지 마라. article_indices와 index는
  반드시 제공된 목록의 index 값이어야 한다.
- 오늘 자료가 너무 적거나(예: 10건 미만) 의미 있는 이슈를 뽑기 어려우면
  has_signal을 false로 설정하고 core_issues/recommended는 빈 배열로 둬라.
{category_priority}

[최종 확인] summary/title/one_line_reason은 전부 한국어로 작성했는가? 영어
문장이 하나라도 섞여 있으면 안 된다 — 다시 확인하고 한국어로만 출력하라."""

# 실제 8개월치 공유 이력(461건)을 훑어 확인한 카테고리별 우선순위 — 단신 발표보다
# "왜 중요한가" 프레이밍이 있는 기사가 실제로 선택되어 온 패턴, AI 쪽은 게임과
# 무관한 순수 LLM/인프라 뉴스도 꾸준히 선택되어 온 패턴을 반영한다.
_CATEGORY_PRIORITY = {
    "GAME": (
        "GAME 카테고리 추가 기준: 이벤트 참가·신작 출시 발표 자체보다, 그 사건이 "
        "산업적으로 왜 중요한지를 짚은 기사를 우선한다 (예: 단순 '게임스컴 참가' "
        "보다 '게임스컴이 특별한 이유'나 실적·글로벌 진출·정책 변화 관점을 담은 "
        "기사). 반복 축: 글로벌·중국 시장 진출, 정책/규제 변화, 게임사 실적. "
        "한 게임사의 단순 신작/업데이트 소식 하나만으로는 부족하다 — 그 소식이 "
        "산업 전체의 흐름(장르 트렌드, 플랫폼 경쟁 구도, 시장 규모 변화 등)을"
        " 대표하거나 보여줄 때 핵심 이슈로 뽑아라."
    ),
    "AI": (
        "AI 카테고리 추가 기준: 오늘의 판단은 기술 위주로 잡는다 — 최우선 "
        "순위는 AI 모델·연구 성과 출시, 성능/벤치마크, 신기술·아키텍처 발표, "
        "GPU/데이터센터/인프라 같은 세계적인 AI 기술 이슈다. 국내 정치·정책·"
        "인사 소식(정부 위원회 인선, 규제 발언, 노동·일자리 정책, 예산·사업 "
        "공모, 컨소시엄 선정 등)은 그 자체로 기술적 진전을 다루지 않는 한 "
        "핵심이슈 후순위로 두고, 정말 다른 기술 이슈가 부족할 때만 채택해라 "
        "— 예를 들어 '정부가 AI 일자리 지표를 만든다'류 소식보다 '오픈AI가 "
        "새 추론 모델을 공개했다'류 소식을 우선한다. 게임과 무관한 순수 "
        "LLM/AI 뉴스도 게임 산업과의 접점이 없다는 이유만으로 배제하지 마라. "
        "해외 모델/기업 소식이 많은 카테고리이므로 summary는 절대 영어 "
        "문장으로 쓰지 말고 처음부터 끝까지 한국어로 서술해라 (모델명·회사명 "
        "등 고유명사만 원어 표기 허용)."
    ),
}


def _system_prompt_for(category: str) -> str:
    return SYSTEM_PROMPT.format(category_priority=_CATEGORY_PRIORITY.get(category, ""))


class _CoreIssue(BaseModel):
    title: str
    summary: str
    # 기본값 "" — 모델이 혹시 이 필드를 빼먹어도 응답 전체가 검증 실패로
    # 튕기지 않게 한다. summary는 그대로 쓰고 detail 팝업만 짧게 나온다.
    detail: str = ""
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


def list_all_window_articles(db: Session, category: str, now: datetime) -> list[Article]:
    """Same window/filter as _fetch_window_articles, but uncapped — for the
    "더보기" panel that shows every article this category's judgment was
    actually drawn from (not just the ones that made core_issues/recommended)."""
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
    # 기본값 "" — 이 필드가 생기기 전에 저장된 DailyHighlightSnapshot을
    # model_validate로 다시 읽을 때도 깨지지 않아야 한다(과거 스냅샷은
    # 다음 자동/수동 새로고침 전까지 detail 없이 summary만 보인다).
    detail: str = ""
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
            detail=issue.detail,
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
        "coreIssues": [{"title": i.title, "summary": i.summary, "detail": i.detail, "articles": i.articles} for i in highlights.core_issues],
        "recommended": [{"title": r.title, "url": r.url, "source": r.source, "reason": r.reason} for r in highlights.recommended],
    }
