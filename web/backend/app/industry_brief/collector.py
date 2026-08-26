"""RSS collection (design doc section 25's pipeline, MVP slice: fetch ->
URL dedup -> store). No AI classification/importance scoring yet (that's
Phase 3) and no scheduler (Phase 7) — this is meant to be run by hand via
web/backend/industry_brief_collect.py until then, matching the spec's
"관리자 수동 재생성" MVP allowance."""
import ssl
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

import certifi
import feedparser
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Article
from .sources import SOURCES, Source

# Some feeds (e.g. openai.com, techcrunch.com) chain through a root CA that
# Windows' own certificate store doesn't trust on this machine, so urllib's
# default SSL context rejects them with "certificate has expired" even
# though the certificate is valid. certifi ships an up-to-date bundle that
# does trust it, so fetch feeds with an explicit context built from it
# instead of relying on the OS trust store.
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


@dataclass
class SourceResult:
    source: str
    fetched: int
    new: int
    duplicates: int
    error: str | None = None


@dataclass
class CollectResult:
    sources: list[SourceResult] = field(default_factory=list)

    @property
    def total_new(self) -> int:
        return sum(s.new for s in self.sources)


def _parsed_time_to_dt(struct_time) -> datetime | None:
    if struct_time is None:
        return None
    return datetime.fromtimestamp(time.mktime(struct_time), tz=timezone.utc)


def _collect_one(db: Session, source: Source) -> SourceResult:
    try:
        request_headers = None
        if source.name == "삼성전자 뉴스룸":
            request_headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/127.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "ko-KR,ko;q=0.9",
            }
        handlers = [urllib.request.HTTPSHandler(context=_SSL_CONTEXT)]
        feed = (
            feedparser.parse(source.feed_url, request_headers=request_headers, handlers=handlers)
            if request_headers else feedparser.parse(source.feed_url, handlers=handlers)
        )
    except Exception as e:
        return SourceResult(source.name, 0, 0, 0, error=f"{type(e).__name__}: {e}")

    if getattr(feed, "bozo", False) and not feed.entries:
        return SourceResult(source.name, 0, 0, 0, error=f"피드 파싱 실패: {getattr(feed, 'bozo_exception', '알 수 없는 오류')}")

    new_count = 0
    dup_count = 0
    seen_this_batch: set[str] = set()
    for entry in feed.entries:
        url = entry.get("link")
        title = entry.get("title")
        if not url or not title or url in seen_this_batch:
            continue
        seen_this_batch.add(url)

        already_stored = db.execute(select(Article.id).where(Article.url == url)).first()
        if already_stored:
            dup_count += 1
            continue

        summary = (entry.get("summary") or "").strip()
        db.add(Article(
            source=source.name, source_type=source.source_type, category=source.category,
            title=title.strip(), url=url,
            published_at=_parsed_time_to_dt(entry.get("published_parsed")),
            summary=summary[:2000] or None,
        ))
        new_count += 1

    db.commit()
    return SourceResult(source.name, len(feed.entries), new_count, dup_count)


def collect_all(db: Session, sources: list[Source] | None = None) -> CollectResult:
    result = CollectResult()
    for source in (sources if sources is not None else SOURCES):
        result.sources.append(_collect_one(db, source))
    # Explicit source lists are used by tests/manual RSS-only runs. NAVER is
    # only part of the normal full Industry Brief collection.
    if sources is None:
        from .official_html import collect_all_official_html, collect_all_naver_sections
        result.sources.extend(collect_all_official_html(db))
        result.sources.extend(collect_all_naver_sections(db))
    return result
