"""One-off repair: backfill hero_image_url for 리니지/리니지M/블레이드앤소울
event_bench records left null by a one-time extraction glitch on the
2026-09-07 collection run.

Confirmed via direct inspection of NC's eventon API: every affected record's
raw image has always been present in marketingItemAdditionSet — the very
first collection run for that batch simply failed to extract it. Records
whose event stayed in NC's RUNNING list long enough to be re-collected on a
later, successful run self-healed automatically (event_bench_refresh.py
re-extracts hero_image_url from scratch every cycle). Records whose event
had already ended before that next successful run never got the chance —
once an event drops off the RUNNING list, event_bench_refresh.py stops
touching it, so its hero_image_url stays frozen at whatever it was.

This queries NC's eventon API *without* the RUNNING filter (so already-ended
events are included too) for all three domains, builds an
event_url -> raw image URL map, and fills in any matching event_bench
record that's still null. Safe to run repeatedly — only ever touches a
record whose hero_image_url is currently empty.

Run from web/backend/: python backfill_nc_eventon_thumbnails.py
"""
from __future__ import annotations

import json
from urllib.parse import quote

from app.config import BENCHMARK_DATA_DIR
from app.event_bench.nexon_sample import NC_EVENTON_API_URL, _eventon_hero_image, _fetch_html
from app.media_cache import cache_thumbnail

EVENT_PATH = BENCHMARK_DATA_DIR / "event_bench" / "nexon_events_sample.json"
LAST_GOOD_PATH = EVENT_PATH.with_name("nexon_events_last_good.json")

DOMAIN_TAGS = {
    "리니지": "DOMAIN_LINEAGE",
    "리니지M": "DOMAIN_LINEAGEM",
    "블레이드앤소울": "DOMAIN_BNS",
}


def _fetch_all_images(domain_tag: str) -> dict[str, str]:
    """event_url -> 원본 이미지 URL. RUNNING 필터 없이 전체 페이지를 순회해
    이미 종료된 이벤트의 항목도 포함한다."""
    images: dict[str, str] = {}
    page = 1
    while True:
        tag = quote(f"MKT_PROMOTION,{domain_tag},,", safe="")
        url = f"{NC_EVENTON_API_URL}?tag={tag}&pageSize=50&page={page}"
        payload = json.loads(_fetch_html(url))
        for item in payload.get("content", []):
            image = _eventon_hero_image(item)
            if not image:
                continue
            for entry in item.get("marketingEntrySet") or []:
                if entry.get("entryType") == "promo" and entry.get("entryUrl"):
                    images.setdefault(entry["entryUrl"].strip(), image)
        if payload.get("last", True):
            break
        page += 1
    return images


def main() -> None:
    if not EVENT_PATH.is_file():
        print(f"{EVENT_PATH}: 파일 없음, 건너뜀")
        return
    rows = json.loads(EVENT_PATH.read_text(encoding="utf-8"))

    images_by_url: dict[str, str] = {}
    for domain_tag in DOMAIN_TAGS.values():
        images_by_url.update(_fetch_all_images(domain_tag))

    fixed = 0
    for row in rows:
        if row.get("game") not in DOMAIN_TAGS or row.get("hero_image_url"):
            continue
        raw = images_by_url.get(row.get("event_url") or "")
        if not raw:
            continue
        row["hero_image_url"] = cache_thumbnail(raw, "event_bench") or raw
        fixed += 1

    if fixed:
        rendered = json.dumps(rows, ensure_ascii=False, indent=2)
        EVENT_PATH.write_text(rendered, encoding="utf-8")
        LAST_GOOD_PATH.write_text(rendered, encoding="utf-8")
    print(f"{fixed}건 썸네일 복구 완료")


if __name__ == "__main__":
    main()
