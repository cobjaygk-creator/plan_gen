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

# 한 회사가 자사 내부 업무에 AI를 도입·적용한 사례("OO제약이 AI로 품질관리
# 시스템을 구축") — 그 자체로는 업계 전체를 흔드는 사건이 아니라 개별
# 활용 사례일 뿐이라, GAME의 프로모션 필터와 같은 방식으로 핵심 요약
# 자리에서 뺀다. 모델 출시·인프라·정책처럼 진짜 기술/산업 변화를 다루면
# (구조적 용어가 같이 있으면) 그대로 둔다.
#
# "하다"류 동사는 과거형에서 "하였다→했다"로 축약되면서 어간의 "하"
# 글자 자체가 사라진다 — "도입했다"/"도입했습니다"는 "도입하"를 부분
# 문자열로 포함하지 않는다. 그래서 활용형(하/했)별로 따로 등록해야
# "도입했습니다"·"도입하여"·"도입하고" 어디서든 걸린다.
_AI_ADOPTION_TERMS = (
    "도입하", "도입했", "도입을",
    "적용하", "적용했",
    "구축하", "구축했",
    "자동화하", "자동화했",
    "업무에 적용", "업무에 도입",
)
_AI_STRUCTURAL_TERMS = (
    "모델", "gpu", "인프라", "데이터센터", "반도체", "오픈소스", "벤치마크",
    "성능", "아키텍처", "추론", "투자", "인수", "합병", "지분", "정책", "규제",
    "법안", "유출", "보안", "취약점", "출시", "공개", "연구", "논문", "협약",
    "동맹", "파트너십",
)
# 회사가 자사 제품/브랜드를 전시회·행사에 내보인 것 자체를 알리는 보도자료
# ("삼성전자가 OO 전시에서 AI와 예술의 융합을 소개했다") — 공식 출처라서
# synthesis_eligible은 통과하지만, 실제 기술/산업 변화가 없는 홍보성 소식일
# 뿐이라 GAME의 프로모션 필터와 같은 방식으로 다룬다. 구조적 용어가 같이
# 있으면(신제품·신기술을 그 자리에서 "공개"/"출시"했다면) 그대로 둔다.
_AI_PROMOTIONAL_TERMS = (
    "전시", "전시회", "박람회", "쇼케이스", "부스", "체험존", "홍보관",
    "하이라이트", "비전을 소개",
)


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
    """Keep marketing amplification (GAME) / single-company internal AI
    adoption (AI) out of the executive-level summary.

    That coverage remains searchable and may appear as a signal or
    recommended article. It only loses the two scarce core-summary slots when
    it contains no material launch, business, policy, security, or product
    change.
    """
    if issue.category not in ("GAME", "AI"):
        return True
    text = " ".join([
        issue.title,
        issue.summary or "",
        *(article.title for article in members),
    ]).casefold()
    if issue.category == "GAME":
        is_promotion = any(term in text for term in _PROMOTIONAL_GAME_TERMS)
        has_material_change = any(term in text for term in _MATERIAL_CHANGE_TERMS)
        return not (is_promotion and not has_material_change)
    is_adoption = any(term in text for term in _AI_ADOPTION_TERMS)
    is_promotional = any(term in text for term in _AI_PROMOTIONAL_TERMS)
    has_structural_change = any(term in text for term in _AI_STRUCTURAL_TERMS)
    return not ((is_adoption or is_promotional) and not has_structural_change)


def has_strong_ai_technical_signal(issue: Issue, members: list[Article], established_media_count: int) -> bool:
    """A same-day AI story reported by only one outlet still deserves a shot
    at "오늘의 판단" when that outlet is a reputable specialist press (AI타임스,
    연합뉴스 계열 등) and the story is a real model/infra/security event —
    otherwise `synthesis_eligible`(교차 확인 or 공식 출처) alone lets a same-day
    company PR/전시회 소식 win the headline slot just because it carries an
    "공식 출처" tag, while the outlet that actually broke the day's real AI news
    waits for a second publication to even become a candidate. Requiring
    established-media coverage (not just any single source) keeps fringe/blog
    noise from qualifying through this bypass.
    """
    if issue.category != "AI" or established_media_count < 1:
        return False
    text = " ".join([
        issue.title, issue.summary or "", *(article.title for article in members),
    ]).casefold()
    return any(term in text for term in _AI_STRUCTURAL_TERMS)


def editorial_score(issue: Issue, members: list[Article]) -> float:
    """Score distinct events, favouring broad industry effects over one firm's results."""
    score = issue.importance_score or 0.0
    text = f"{issue.title} {issue.summary or ''}".casefold()
    if issue.category not in ("GAME", "AI"):
        return score
    if not is_core_summary_candidate(issue, members):
        return min(score, 20.0)
    if issue.category == "AI":
        return score

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
