"""Small deterministic taxonomy for presenting keyword signals at the right level."""
import json
import re
from collections import Counter
from math import ceil

from .models import Article

_PROJECT = re.compile(r"(?:project|프로젝트|\b[a-z]+\s?\d+\b)", re.IGNORECASE)
_PRODUCTS = {"붉은사막", "로스트아크", "라그나로크", "검은사막", "프로젝트 d1"}

_GENERIC = {
    "ai", "생성형 ai", "ai agent", "ai 에이전트", "llm", "mmorpg", "신작",
    "게임 개발", "게임 정보", "라이브 서비스", "퍼블리싱", "글로벌 마케팅",
    "디지털 창작", "중간배당", "steam", "free-to-play", "web3",
}


def classify_signal_keyword(topic: str, articles: list[Article]) -> tuple[str, str]:
    value = topic.casefold().strip()
    if _PROJECT.search(topic):
        return "PROJECT", "프로젝트"
    if value in _PRODUCTS:
        return "PRODUCT", "제품"
    if value in _GENERIC:
        return "INDUSTRY", "산업 주제"
    entity_hits = sum(
        1 for article in articles
        if any(entity.casefold() == value for entity in (json.loads(article.entities) if article.entities else []))
    )
    if articles and entity_hits >= max(2, ceil(len(articles) * 0.6)):
        return "COMPANY", "기업"
    return "INDUSTRY", "산업 주제"