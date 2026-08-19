"""Editorial priorities for the AI lane of Industry Brief.

This module is deliberately local to Industry Brief.  It prevents broad
business news that merely mentions AI from displacing genuinely useful AI
technology, model, security, and product-development coverage.
"""

from __future__ import annotations

from .models import Article


# Topics the team wants to discover first in the AI lane.
AI_PRIORITY_TERMS = (
    "오픈웨이트", "open weight", "오픈소스", "open source", "모델 출시",
    "모델 공개", "llm", "추론", "reasoning", "멀티모달", "multimodal",
    "에이전트", "agent", "ai 안전", "ai 보안", "취약점", "보안", "red team",
    "데이터 유출", "프롬프트 인젝션", "저작권", "규제", "ai act",
    "api", "파인튜닝", "fine-tuning", "코딩 에이전트", "로보틱스",
    "benchmark", "벤치마크", "gpt", "claude", "gemini", "llama", "mistral",
    "deepseek", "qwen", "sora", "veo",
)

# These can still be collected as context, but should not headline an AI brief
# without a direct technical release, safety event, or material platform change.
AI_CONTEXT_ONLY_TERMS = (
    "요금제", "구독료", "가격 인상", "무료 요금제", "프로모션", "결제",
    "메모리 생산", "hbm 생산", "d램 생산", "공급 계약", "공장 증설",
    "실적", "주가", "매출", "투자 유치", "증자",
)


def ai_editorial_score(article: Article) -> float:
    """Return a deterministic score adjustment for AI editorial importance."""
    if article.category != "AI":
        return 0.0
    text = f"{article.title} {article.summary or ''}".casefold()
    priority_hits = sum(term.casefold() in text for term in AI_PRIORITY_TERMS)
    context_hits = sum(term.casefold() in text for term in AI_CONTEXT_ONLY_TERMS)
    # A story that has both types can remain important, e.g. a model release
    # with a pricing change.  Context-only stories are intentionally demoted.
    return min(30.0, priority_hits * 12.0) - min(45.0, context_hits * 18.0)


def is_ai_context_only(article: Article) -> bool:
    """Whether the article lacks a preferred technical/safety signal."""
    if article.category != "AI":
        return False
    text = f"{article.title} {article.summary or ''}".casefold()
    has_priority = any(term.casefold() in text for term in AI_PRIORITY_TERMS)
    has_context = any(term.casefold() in text for term in AI_CONTEXT_ONLY_TERMS)
    return has_context and not has_priority

# Strong caps for commercial/market-wire coverage.  Generic words such as
# "generative AI" or "agent" do not override these caps by themselves.
def ai_editorial_cap(article: Article) -> float | None:
    if article.category != "AI":
        return None
    text = f"{article.title} {article.summary or ''}".casefold()
    if any(term in text for term in ("요금제", "구독료", "가격 인상", "프로모션", "메모리 생산", "hbm 생산", "d램 생산", "실적", "주가")):
        return 25.0
    if "edr" in text and not any(term in text for term in ("취약점", "침해", "공격", "유출", "랜섬웨어", "제로데이")):
        return 30.0
    if any(term in text for term in ("투자", "투자 유치", "증자", "투자 기금", "자금 조달", "메가딜")):
        return 35.0
    if any(term in text for term in ("데이터센터", "iaas", "ai 인프라")) and not any(term in text for term in ("모델 출시", "모델 공개", "오픈웨이트", "취약점", "규제")):
        return 45.0
    return None

# Do not use these commercial or supply-chain stories as a top AI briefing
# issue even when clustering also finds a named model in the same article.
AI_BRIEF_DEMOTION_TERMS = (
    "요금제", "구독료", "edr", "메모리 생산", "hbm 생산", "d램 생산",
    "실적", "주가", "투자", "투자 유치", "증자", "자금 조달", "메가딜",
)


def is_ai_brief_context_issue(title: str) -> bool:
    return any(term in (title or "").casefold() for term in AI_BRIEF_DEMOTION_TERMS)

