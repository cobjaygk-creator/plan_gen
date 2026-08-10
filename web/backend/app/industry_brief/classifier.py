"""Phase 3: per-article classification (design doc section 36's "Article
Intelligence" — relevance, GAME/AI 분류, 요약, keywords, entities, 중요도).
The spec recommends OpenAI GPT-5.4 nano for this tier; the user approved
substituting Anthropic (already configured, no new API key needed) for
the same cheap/fast role — reuses tools/ai_client.py's provider-agnostic
classify() helper as-is rather than writing a second API client.

No Issue clustering here (Phase 4) — this only touches one article at a
time."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.ai_client import classify, ClassificationError, HAIKU_MODEL

from .models import Article

CLASSIFIER_MODEL = HAIKU_MODEL

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


def _classify_one(article: Article) -> ArticleClassification | None:
    user_prompt = f"제목: {article.title}\n\n요약/본문: {(article.summary or '')[:1500]}"
    try:
        return classify(SYSTEM_PROMPT, user_prompt, ArticleClassification, CLASSIFIER_MODEL)
    except ClassificationError:
        return None


def classify_pending(db: Session, limit: int = 10) -> int:
    """Classifies up to `limit` not-yet-classified articles (classified_at
    is null). Returns how many were actually classified — an article the
    model failed on is left pending (classified_at stays null) rather than
    silently marked done, so a later run retries it instead of losing it."""
    pending = db.execute(
        select(Article).where(Article.classified_at.is_(None)).limit(limit)
    ).scalars().all()

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
        article.importance_score = _IMPORTANCE_SCORE[result.importance]
        article.classified_at = datetime.now(timezone.utc)
        done += 1

    db.commit()
    return done
