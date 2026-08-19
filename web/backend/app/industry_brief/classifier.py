"""Phase 3: per-article classification (design doc section 36's "Article
Intelligence" — relevance, GAME/AI 분류, 요약, keywords, entities, 중요도).
Uses OpenAI per the spec's recommendation (section 22), now that
OPENAI_API_KEY is configured — reuses tools/ai_client.py's provider-
agnostic classify() helper as-is (now with OpenAI support added there)
rather than writing a second API client. Passes provider explicitly so
this stays independent of the PPT pipeline's AI_PROVIDER=anthropic
default (spec: "Provider 변경을 고려하여 AI Service Layer를 분리한다").

No Issue clustering here (Phase 4) — this only touches one article at a
time."""
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.ai_client import classify, ClassificationError

from .models import Article
from .sources import is_korean_source
from .reference import analyze_live_article
from .ai_editorial_policy import ai_editorial_cap, ai_editorial_score, is_ai_context_only

# Not hardcoded (spec section 22) — override via .env if the account uses
# a different model. Defaults to a known-available cheap OpenAI model
# rather than guessing at the spec's own "GPT-5.4 nano" placeholder name.
BRIEF_AI_PROVIDER = os.environ.get("BRIEF_AI_PROVIDER", "openai")
CLASSIFIER_MODEL = os.environ.get("BRIEF_CLASSIFIER_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """\
너는 게임업계와 AI업계 뉴스를 분류하는 리서치 어시스턴트다. 기사 제목과
요약(또는 본문 일부)을 보고 다음을 판단해라:

1. is_relevant: 이 기사가 게임 산업 또는 AI 산업의 실질적인 동향(제품,
   기업 발표, 산업 트렌드, 기술, 인수합병 등)과 관련 있는지. 단순 잡담,
   광고, 완전히 무관한 주제면 false.
2. category: "GAME"(게임 산업), "AI"(AI 산업), "OTHER"(둘 다 아니거나
   애매함) 중 하나.
3. summary: 기사 핵심 내용을 한국어 1~2문장으로 요약해라. 제목을 그대로
   반복하지 말고 실제 내용을 담아라.
4. keywords: 이 기사가 다루는 핵심 주제/트렌드 키워드 (예: "AI Agent",
   "Live Service", "Web3"), 최대 5개.
5. entities: 기사에 언급된 핵심 기업/제품/인물 이름, 최대 8개.
6. importance: 산업 동향 파악 관점에서 이 기사의 중요도. 신제품 공식
   발표나 산업 전반에 영향을 주는 소식은 high, 일반적인 업데이트나
   소규모 소식은 medium, 사소하거나 반복적인 소식은 low.

기사에 실제로 나온 내용만 근거로 판단해라 — 과장하거나 근거 없이
추측하지 마라."""


class ArticleClassification(BaseModel):
    is_relevant: bool = Field(description="게임 또는 AI 업계 동향과 실질적으로 관련 있는 기사인지")
    category: Literal["GAME", "AI", "OTHER"]
    summary: str = Field(description="기사 핵심 내용의 한국어 1~2문장 요약")
    keywords: list[str] = Field(default_factory=list, description="핵심 주제 키워드, 최대 5개")
    entities: list[str] = Field(default_factory=list, description="언급된 기업/제품/인물 등 핵심 개체명, 최대 8개")
    importance: Literal["high", "medium", "low"]


_IMPORTANCE_SCORE = {"high": 90.0, "medium": 60.0, "low": 30.0}

_HIGH_VALUE_TERMS = (
    "투자", "인수", "합병", "실적", "출시", "공개", "정책", "규제",
    "생성형 AI", "AI Agent", "LLM", "반도체", "데이터센터", "전력",
    "넥슨", "크래프톤", "엔씨소프트", "넷마블", "OpenAI", "Google", "NVIDIA",
)
_LOW_VALUE_TERMS = ("이벤트", "쿠폰", "공략", "할인", "체험기")


def _pending_priority(article: Article) -> float:
    """Cheap pre-AI score: freshness + Korea + industry-value signals."""
    title = article.title.casefold()
    score = 20.0 if is_korean_source(article.source) else 0.0
    score += 15.0 if article.source_type == "official" else 0.0
    score += min(20.0, sum(5.0 for term in _HIGH_VALUE_TERMS if term.casefold() in title))
    score -= sum(15.0 for term in _LOW_VALUE_TERMS if term.casefold() in title)
    published = article.published_at or article.collected_at
    if published is not None:
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        age_hours = max(0.0, (datetime.now(timezone.utc) - published).total_seconds() / 3600)
        score += max(0.0, 30.0 - min(age_hours, 30.0))
    return score


def _select_balanced_pending(articles: list[Article], limit: int) -> list[Article]:
    """Select a diverse batch: max 20% per outlet, max 60% per category/region.

    A final fill pass relaxes category/region caps when a pool is too small,
    while retaining the per-source cap so one large feed cannot dominate.
    """
    if limit <= 0:
        return []
    ranked = sorted(articles, key=lambda article: (_pending_priority(article), article.id), reverse=True)
    source_cap = max(1, (limit + 4) // 5)
    group_cap = max(1, (limit * 3 + 4) // 5)
    source_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    region_counts: Counter[str] = Counter()
    selected: list[Article] = []

    def add(article: Article, enforce_groups: bool, enforce_source: bool) -> bool:
        region = "KR" if is_korean_source(article.source) else "GLOBAL"
        if enforce_source and source_counts[article.source] >= source_cap:
            return False
        if enforce_groups and (
            category_counts[article.category] >= group_cap or region_counts[region] >= group_cap
        ):
            return False
        selected.append(article)
        source_counts[article.source] += 1
        category_counts[article.category] += 1
        region_counts[region] += 1
        return True

    for enforce_groups, enforce_source in ((True, True), (False, True), (False, False)):
        for article in ranked:
            if len(selected) >= limit:
                return selected
            if article not in selected:
                add(article, enforce_groups, enforce_source)
    return selected


def _classify_one(article: Article) -> ArticleClassification | None:
    user_prompt = f"제목: {article.title}\n\n요약/본문: {(article.summary or '')[:1500]}"
    try:
        return classify(
            SYSTEM_PROMPT, user_prompt, ArticleClassification, CLASSIFIER_MODEL,
            provider=BRIEF_AI_PROVIDER,
        )
    except ClassificationError:
        return None


def classify_pending(
    db: Session,
    limit: int = 10,
    source_names: tuple[str, ...] | None = None,
) -> int:
    """Classifies up to `limit` not-yet-classified articles (classified_at
    is null). Returns how many were actually classified — an article the
    model failed on is left pending (classified_at stays null) rather than
    silently marked done, so a later run retries it instead of losing it."""
    query = select(Article).where(Article.classified_at.is_(None))
    if source_names:
        query = query.where(Article.source.in_(source_names))
    candidates = db.execute(query).scalars().all()
    pending = _select_balanced_pending(candidates, limit)

    done = 0
    for article in pending:
        result = _classify_one(article)
        if result is None:
            continue
        if result.category in ("GAME", "AI"):
            article.category = result.category
        article.is_relevant = result.is_relevant
        article.summary = result.summary
        article.keywords = json.dumps(result.keywords, ensure_ascii=False)
        article.entities = json.dumps(result.entities, ensure_ascii=False)
        score = _IMPORTANCE_SCORE[result.importance]
        # The AI lane is a technology briefing, not a broad market-wire feed.
        # Keep context-only pricing, production, and stock stories searchable,
        # but ensure they cannot outrank model, product, safety, or security news.
        if result.category == "AI":
            score += ai_editorial_score(article)
            if is_ai_context_only(article):
                score = min(score, _IMPORTANCE_SCORE["low"])
        cap = ai_editorial_cap(article)
        if cap is not None:
            score = min(score, cap)
        article.importance_score = max(0.0, min(100.0, score))
        article.classified_at = datetime.now(timezone.utc)
        analyze_live_article(db, article)
        done += 1

    db.commit()
    return done



