"""NAVER Search News API adapter for Korea-focused Industry Brief discovery.

Search results are candidate links only.  We retain the original publisher URL
and use the same Article table/deduplication rules as the RSS collector.
"""
import html
import json
import os
import re
from dataclasses import dataclass
from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Iterable
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.orm import Session

from .collector import SourceResult
from .models import Article

API_URL = "https://naverapihub.apigw.ntruss.com/search/v1/news"
QUERIES: tuple[tuple[str, str], ...] = (
    ("게임 신작", "GAME"), ("게임 실적", "GAME"), ("게임 규제", "GAME"),
    ("게임 중국", "GAME"), ("게임 AI", "GAME"),
    ("생성형 AI", "AI"), ("AI 에이전트", "AI"), ("AI 반도체", "AI"),
    ("AI 투자", "AI"), ("AI 규제", "AI"), ("AI 게임 개발", "GAME"),
    ("AI NPC", "GAME"),
)
_TAGS = re.compile(r"<[^>]+>")
# Naver is a discovery source. Its default AI search terms deliberately favour
# technical developments over pricing plans, chip production, or earnings news.
TECH_FOCUSED_AI_QUERIES: tuple[tuple[str, str], ...] = (
    ("AI 모델 출시", "AI"), ("오픈웨이트 AI 모델", "AI"),
    ("생성형 AI 업데이트", "AI"), ("AI 에이전트", "AI"),
    ("AI 보안 취약점", "AI"), ("AI 안전", "AI"),
    ("AI 저작권 규제", "AI"), ("멀티모달 AI", "AI"),
    ("AI 개발 도구", "AI"),
)
# Policy is a separate discovery lane.  These queries deliberately cover
# law, regulator decisions, privacy and market-access changes that can alter
# game planning or AI product operation, not general political news.
POLICY_FOCUSED_QUERIES: tuple[tuple[str, str], ...] = (
    ("게임산업진흥법", "GAME"), ("확률형 아이템 규제", "GAME"),
    ("게임물관리위원회 등급분류", "GAME"), ("중국 게임 판호", "GAME"),
    ("인공지능 기본법", "AI"), ("AI 기본법 시행", "AI"),
    ("생성형 AI 저작권", "AI"), ("AI 개인정보보호", "AI"),
    ("AI 안전성 규제", "AI"),
)


def _clean(value: str) -> str:
    return html.unescape(_TAGS.sub("", value or "")).strip()


def _published_at(value: str):
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _fetch(query: str, client_id: str, client_secret: str) -> list[dict]:
    url = f"{API_URL}?{urlencode({'query': query, 'display': 20, 'sort': 'date'})}"
    request = Request(url, headers={
        "X-NCP-APIGW-API-KEY-ID": client_id,
        "X-NCP-APIGW-API-KEY": client_secret,
    })
    with urlopen(request, timeout=15) as response:  # noqa: S310 - fixed HTTPS endpoint
        return json.loads(response.read().decode("utf-8")).get("items", [])


def collect_naver_news(db: Session, queries: Iterable[tuple[str, str]] | None = None) -> SourceResult:
    client_id = os.environ.get("NAVER_CLIENT_ID", "").strip()
    client_secret = os.environ.get("NAVER_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return SourceResult("NAVER News", 0, 0, 0, error="NAVER_CLIENT_ID/SECRET not configured")

    fetched = new_count = duplicates = 0
    seen: set[str] = set()
    try:
        active_queries = queries if queries is not None else (*QUERIES[:5], *TECH_FOCUSED_AI_QUERIES, *POLICY_FOCUSED_QUERIES)
        for query, category in active_queries:
            for item in _fetch(query, client_id, client_secret):
                fetched += 1
                url = (item.get("originallink") or item.get("link") or "").strip()
                title = _clean(item.get("title", ""))
                if not url or not title or url in seen:
                    continue
                seen.add(url)
                if db.execute(select(Article.id).where(Article.url == url)).first():
                    duplicates += 1
                    continue
                domain = urlparse(url).netloc.removeprefix("www.") or "NAVER News"
                db.add(Article(
                    source=f"NAVER · {domain}", source_type="media", category=category,
                    title=title, url=url, published_at=_published_at(item.get("pubDate", "")),
                    summary=_clean(item.get("description", ""))[:2000] or None,
                ))
                new_count += 1
        db.commit()
    except Exception as exc:
        db.rollback()
        return SourceResult("NAVER News", fetched, 0, duplicates, error=f"{type(exc).__name__}: {exc}")
    return SourceResult("NAVER News", fetched, new_count, duplicates)



