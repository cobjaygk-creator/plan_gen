"""One-off repair: backfill thumbnail_url for game_sites/official_sites.json
records left null by refresh_portal_sites()'s permanent per-URL skip (see
its docstring/comments) — once a site is known, it's never revisited, so a
record whose first-discovery thumbnail resolution failed (or was later
nulled by fix_stale_thumbnails.py) had no path back to a real image.

portal_collector.py now self-heals a missing thumbnail on every future
refresh cycle *if* that cycle's own portal collector happens to have scraped
one, at no extra request cost — but several portals (WEMADE, and others
when a listing carries no thumbnail of its own) never provide one that way,
since the only real source is the game's own og:image, which only
_page_metadata()'s live fetch reads. Since these are official, ongoing game
sites (unlike an ended event's dedicated splash page), the source page is
still up and its og:image is worth fetching directly.

Run from web/backend/: python backfill_game_sites_thumbnails.py
"""
from __future__ import annotations

import json

from app.game_sites.portal_collector import OFFICIAL_PATH, _page_metadata
from app.media_cache import cache_thumbnail


def main() -> None:
    if not OFFICIAL_PATH.is_file():
        print(f"{OFFICIAL_PATH}: 파일 없음, 건너뜀")
        return
    rows = json.loads(OFFICIAL_PATH.read_text(encoding="utf-8"))

    fixed = 0
    checked = 0
    for row in rows:
        if row.get("thumbnail_url") or not row.get("url"):
            continue
        checked += 1
        try:
            _title, image = _page_metadata(row["url"])
        except Exception as error:
            print(f"  {row['url']}: 조회 실패 - {error}")
            continue
        if not image:
            continue
        row["thumbnail_url"] = cache_thumbnail(image, "game_sites") or image
        fixed += 1

    if fixed:
        OFFICIAL_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{checked}건 확인, {fixed}건 썸네일 복구 완료")


if __name__ == "__main__":
    main()
