"""Editorial ranking rules for period briefs.

Several outlets often cover the same earnings release as separate articles.
Coverage volume should improve confidence, never let one corporate event occupy
multiple top-issue slots.  These rules deliberately use only existing article
metadata and do not add an AI call.
"""
from __future__ import annotations

import json
import re
from collections import Counter

from .models import Article, Issue


_EARNINGS_TERMS = ("실적", "영업이익", "매출", "분기 최대", "분기 실적")
_STRUCTURAL_GAME_TERMS = (
    "ip", "웹툰", "인수", "지분", "투자", "글로벌", "플랫폼", "규제", "퍼블리싱",
    "콘솔", "멀티플랫폼", "판권",
)
_PROMOTIONAL_GAME_TERMS = (
    "배우", "홍보대사", "모델 발탁", "게임 플레이 비하인드", "플레이 비하인드",
    "비하인드 영상", "메이킹 영상", "화보", "셀럽", "인플루언서",
    "굿즈", "아트북", "코믹마켓", "팬 행사", "전시 성료", "완판",
)
_MATERIAL_CHANGE_TERMS = (
    "출시일", "정식 출시", "글로벌 출시", "서비스 시작", "업데이트", "확장팩",
    "신규 클래스", "신규 서버", "투자", "인수", "합병", "지분", "실적",
    "매출", "영업이익", "규제", "정책", "법안", "보안", "취약점", "유출",
    "파트너십", "제휴", "퍼블리싱", "서비스 종료",
)
_GENERIC_ENTITIES = {"게임", "ai", "대한민국", "한국", "분기", "실적"}


def _entities(members: list[Article]) -> list[str]:
    values: list[str] = []
    for article in members:
        try:
            values.extend(str(value).strip() for value in json.loads(article.entities or "[]"))
        except (TypeError, ValueError):
            continue
    return values


def _primary_entity(members: list[Article]) -> str | None:
    candidates = [value for value in _entities(members) if len(value) > 1 and value.casefold() not in _GENERIC_ENTITIES]
    if not candidates:
        return None
    return Counter(candidates).most_common(1)[0][0].casefold()


def issue_event_key(issue: Issue, members: list[Article]) -> str | None:
    """Stable key for multiple issues describing the same corporate event."""
    text = f"{issue.title} {issue.summary or ''}".casefold()
    if any(term in text for term in _EARNINGS_TERMS):
        entity = _primary_entity(members)
        if entity:
            return f"earnings:{issue.category}:{entity}"
        # Korean company names commonly lead an earnings headline.
        lead = re.split(r"[ ,·:…]", issue.title.strip(), maxsplit=1)[0].casefold()
        return f"earnings:{issue.category}:{lead}" if lead else None
    return None


def is_core_summary_candidate(issue: Issue, members: list[Article]) -> bool:
    """Keep marketing amplification out of the executive-level summary.

    Promotional coverage remains searchable and may appear as a signal or
    recommended article. It only loses the two scarce core-summary slots when
    it contains no material launch, business, policy, security, or product
    change.
    """
    if issue.category != "GAME":
        return True
    text = " ".join([
        issue.title,
        issue.summary or "",
        *(article.title for article in members),
    ]).casefold()
    is_promotion = any(term in text for term in _PROMOTIONAL_GAME_TERMS)
    has_material_change = any(term in text for term in _MATERIAL_CHANGE_TERMS)
    return not (is_promotion and not has_material_change)


def editorial_score(issue: Issue, members: list[Article]) -> float:
    """Score distinct events, favouring broad industry effects over one firm's results."""
    score = issue.importance_score or 0.0
    text = f"{issue.title} {issue.summary or ''}".casefold()
    if issue.category != "GAME":
        return score
    if not is_core_summary_candidate(issue, members):
        return min(score, 20.0)

    is_earnings = any(term in text for term in _EARNINGS_TERMS)
    is_structural = any(term in text for term in _STRUCTURAL_GAME_TERMS)
    if is_earnings and not is_structural:
        # Important context, but not the principal three-day industry change.
        return min(score, 48.0)
    if is_structural:
        return min(100.0, score + 18.0)
    if "출시" in text and len(members) <= 1:
        return min(score, 68.0)
    return score
