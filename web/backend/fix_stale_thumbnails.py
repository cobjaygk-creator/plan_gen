"""One-off repair: null out thumbnail references left dangling by the
cache-location move (see app/media_cache.py's docstring) — event_bench
records for events no longer live (ended/removed) never get re-scraped, so
their hero_image_url still points at the old, now-deleted
web/frontend/dist/data/thumbnails/... path forever; game_sites' own
official_sites.json is worse — refresh_portal_sites() skips any URL it has
already seen even once, so EVERY entry's thumbnail_url is frozen at
whatever it was on first discovery, with no self-healing at all.

The original source image URL was already overwritten by the cached path
at write time, so there's nothing left to re-download for these — the best
fix is nulling the field so the frontend's existing "NO IMAGE" placeholder
shows instead of a permanently-broken <img>. Safe to run repeatedly.

Run from web/backend/: python fix_stale_thumbnails.py
"""
from __future__ import annotations

import json
from pathlib import Path

from app.config import BENCHMARK_DATA_DIR
from app.media_cache import is_cached_thumbnail_missing
from app.game_sites.portal_collector import OFFICIAL_PATH


def _clean_field(path: Path, field: str) -> int:
    if not path.is_file():
        print(f"{path}: 파일 없음, 건너뜀")
        return 0
    rows = json.loads(path.read_text(encoding="utf-8"))
    fixed = 0
    for row in rows:
        value = row.get(field)
        if is_cached_thumbnail_missing(value):
            row[field] = None
            fixed += 1
    if fixed:
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{path}: {fixed}/{len(rows)}건 정리")
    return fixed


def main() -> None:
    event_bench_path = BENCHMARK_DATA_DIR / "event_bench" / "nexon_events_sample.json"
    total = 0
    total += _clean_field(event_bench_path, "hero_image_url")
    total += _clean_field(OFFICIAL_PATH, "thumbnail_url")
    print(f"총 {total}건 정리 완료")


if __name__ == "__main__":
    main()
