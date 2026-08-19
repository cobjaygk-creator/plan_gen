"""Selection policy for the compact 'must read' article lanes.

This is intentionally stricter than collection and looser than the main
brief: it picks diverse, substantiated reading rather than every article that
mentions the industry.
"""
from __future__ import annotations

import json
import re

from .models import Article


_PROMOTIONAL_TERMS = (
    "광고", "협찬", "체험단", "쿠폰", "할인", "이벤트", "기획전", "리뷰", "칼럼",
    "사전예약", "경품", "무료 체험",
)
_HIGH_SIGNAL_TERMS = (
    "모델", "오픈웨이트", "오픈소스", "출시", "공개", "보안", "취약점", "규제",
    "인수", "지분", "ip", "웹툰", "플랫폼", "정책", "개방형", "멀티모달",
)
_EVENT_MARKERS = (
    ("보안", ("취약점", "침해", "공격", "유출", "보안")),
    ("규제", ("규제", "정책", "저작권")),
    ("모델", ("모델", "오픈웨이트", "오픈소스", "llm")),
    ("출시", ("출시", "공개", "발표", "업데이트")),
    ("ip", ("ip", "웹툰", "판권")),
    ("거래", ("인수", "지분", "투자")),
)
_GENERIC_ENTITIES = {"ai", "게임", "한국", "대한민국", "산업"}


def _text(article: Article) -> str:
    return f"{article.title} {article.summary or ''}".casefold()


def is_promotional(article: Article) -> bool:
    return any(term in _text(article) for term in _PROMOTIONAL_TERMS)


def _entity(article: Article) -> str | None:
    try:
        entities = json.loads(article.entities or "[]")
    except (TypeError, ValueError):
        return None
    for value in entities:
        candidate = str(value).strip().casefold()
        if len(candidate) > 1 and candidate not in _GENERIC_ENTITIES:
            return candidate
    return None


def event_key(article: Article) -> str:
    """A conservative same-event key, used only to diversify recommendations."""
    text = _text(article)
    marker = next((label for label, terms in _EVENT_MARKERS if any(term in text for term in terms)), "news")
    entity = _entity(article)
    if entity:
        return f"{article.category}:{entity}:{marker}"
    normalized = re.sub(r"[^\w가-힣\s]", " ", article.title.casefold())
    words = [word for word in normalized.split() if len(word) > 1][:4]
    return f"{article.category}:{marker}:{'-'.join(words)}"


def recommendation_score(article: Article, *, current_period: bool) -> float:
    score = article.importance_score or 0.0
    text = _text(article)
    score += 15.0 if current_period else 0.0
    score += 10.0 if article.source_type == "official" else 0.0
    score += min(20.0, 4.0 * sum(term in text for term in _HIGH_SIGNAL_TERMS))
    # Headlines that only report company financial performance remain useful
    # context, but rarely deserve a slot over a material industry event.
    if any(term in text for term in ("실적", "영업이익", "매출", "주가")):
        score -= 18.0
    return score
