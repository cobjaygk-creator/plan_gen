"""기술 레이더 — AI 카테고리 안의 세부 태그 뷰 (기획안 Phase 3, "02 메뉴 구조"
결정: 새 최상위 카테고리가 아니라 AI 카테고리 내부 확장).

MVP는 규칙 기반 키워드 매칭이다 — LLM 호출을 하나 더 추가하면 카테고리마다
매일 분류 비용이 들고, 실패 시 조용히 빈 칸이 되는 리스크가 있다 (기획 검토
때 지적한 "TECH RADAR 12칸 빈 그리드" 문제와 같은 종류). 대신 이미 저장된
title/summary 텍스트만으로 태그를 세고, 활동이 있는 태그만 노출한다 —
classify_pending()의 classified_at 여부와 무관하게 동작해서, 방금 수집된
NAVER 기사에도 즉시 적용된다."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Article

# "시범 분류" 5개만 — 8개월 공유 이력·이번 세션에서 실제로 반복 등장한 유형만
# 골랐다. 활동이 없으면 화면에서 그냥 빠지므로, 굳이 12개를 채워둘 이유가 없다.
TECH_TAGS: list[dict] = [
    {"key": "agent", "label": "AI 에이전트", "keywords": ["에이전트", "agent"]},
    {"key": "coding", "label": "코딩 AI", "keywords": ["코딩", "바이브 코딩", "코파일럿", "copilot", "cursor"]},
    {"key": "model", "label": "신규 모델", "keywords": ["클로드", "제미나이", "챗gpt", "gpt-", "glm", "라마", "딥시크", "오픈소스 모델"]},
    {"key": "gpu", "label": "GPU · 반도체", "keywords": ["gpu", "반도체", "엔비디아", "nvidia", "amd", "칩플레이션"]},
    {"key": "media_gen", "label": "이미지 · 영상 생성", "keywords": ["이미지 생성", "영상 생성", "미드저니", "런웨이", "runway", "sora"]},
]


def _matches(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def build_tech_radar(db: Session, start: datetime, end: datetime) -> list[dict]:
    """활동이 있는 태그만, 최근 기사 많은 순으로. 빈 태그는 아예 목록에서
    빠진다 — 화면은 "몇 칸 채워진 그리드"가 아니라 "지금 실제로 도는 태그
    목록"이어야 한다."""
    articles = db.execute(
        select(Article)
        .where(Article.category == "AI", Article.collected_at >= start, Article.collected_at <= end)
        .order_by(Article.collected_at.desc())
    ).scalars().all()

    radar = []
    for tag in TECH_TAGS:
        matched = [
            a for a in articles
            if _matches(f"{a.title} {a.summary or ''}".casefold(), tag["keywords"])
        ]
        if not matched:
            continue
        radar.append({
            "key": tag["key"],
            "label": tag["label"],
            "articleCount": len(matched),
            "articles": [
                {"title": a.title, "url": a.url, "source": a.source}
                for a in matched[:5]
            ],
        })
    radar.sort(key=lambda item: item["articleCount"], reverse=True)
    return radar
