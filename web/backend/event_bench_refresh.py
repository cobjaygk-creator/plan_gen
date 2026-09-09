"""Scheduled refresh for the isolated Event Benchmark data.

The JSON file is an append-only event archive keyed by official event URL.
Only candidates listed as ongoing by each official source are collected. When
an event disappears from a successfully refreshed source, it remains stored
with ``is_active=False``; failed sources keep their previous state unchanged.
"""
from __future__ import annotations

import json
import logging
import urllib.request
from dataclasses import asdict
from datetime import date, datetime, timezone

from app.config import BENCHMARK_DATA_DIR
from app.media_cache import cache_thumbnail
from app.event_bench.nexon_sample import (
    EventCandidate,
    collect_fc_online_events,
    collect_mabinogi_events,
    collect_maplestory_events,
    collect_elsword_events,
    collect_baram_events,
    collect_lostark_events,
    collect_lineage_events,
    collect_lineagem_events,
    collect_blade_and_soul_events,
    collect_black_desert_events,
    collect_dnf_events,
    collect_cso_events,
    collect_heroes_events,
    collect_ragnarok_events,
    collect_audition_events,
    collect_cyphers_events,
    collect_thefinals_events,
)

OUTPUT_PATH = BENCHMARK_DATA_DIR / "event_bench" / "nexon_events_sample.json"
LAST_GOOD_PATH = OUTPUT_PATH.with_name("nexon_events_last_good.json")
LOG_PATH = OUTPUT_PATH.with_name("refresh.log")

# tales.nexon.com(\ud14c\uc77c\uc988\uc704\ubc84)/tr.rhaon.co.kr(\ud14c\uc77c\uc988\ub7f0\ub108)/gersang.co.kr(\uac70\uc0c1)\ub294
# \uc624\ub77c\ud074 \ud074\ub77c\uc6b0\ub4dc IP\ub97c \ucc28\ub2e8\ud574\uc11c(403/\ud0c0\uc784\uc544\uc6c3, \uc9c1\uc811 \ud655\uc778) \uc6b4\uc601 \uc11c\ubc84\uac00 \ubabb
# \ub6ab\ub294\ub2e4 \u2014 GitHub Actions(fallback-collect.yml)\uac00 \ub300\uc2e0 \uc218\uc9d1\ud574 \ucee4\ubc0b\ud574\ub454
# \uacb0\uacfc\ub97c raw.githubusercontent.com\uc5d0\uc11c \uc9c1\uc811 fetch\ud55c\ub2e4. git/rsync\ub97c \uac70\uce58\uc9c0
# \uc54a\ub294 \uc21c\uc218 HTTP \uc77d\uae30\ub77c, \uc608\uc804\uc5d0 data/ci\ub97c \ubc30\ud3ec\uac00 \ub36e\uc5b4\uc4f0\ub358 \uac83\uacfc \uac19\uc740 \ucda9\ub3cc\uc774
# \uc0dd\uae30\uc9c0 \uc54a\ub294\ub2e4.
_GITHUB_FALLBACK_URL = (
    "https://raw.githubusercontent.com/cobjaygk-creator/plan_gen/master/"
    "web/backend/data/github-collected/fallback_events.json"
)


def collect_via_github_fallback(game: str) -> list[EventCandidate]:
    with urllib.request.urlopen(_GITHUB_FALLBACK_URL, timeout=20) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    return [EventCandidate(**item) for item in payload.get(game, [])]


COLLECTORS = {
    "FC ONLINE": collect_fc_online_events,
    "\uba54\uc774\ud50c\uc2a4\ud1a0\ub9ac": collect_maplestory_events,
    "\ub9c8\ube44\ub178\uae30": collect_mabinogi_events,
    "\ud14c\uc77c\uc988\uc704\ubc84": lambda: collect_via_github_fallback("\ud14c\uc77c\uc988\uc704\ubc84"),
    "\uc5d8\uc18c\ub4dc": collect_elsword_events,
    "\ubc14\ub78c\uc758\ub098\ub77c": collect_baram_events,
    "\ub85c\uc2a4\ud2b8\uc544\ud06c": collect_lostark_events,
    "\ub9ac\ub2c8\uc9c0": collect_lineage_events,
    "\ub9ac\ub2c8\uc9c0M": collect_lineagem_events,
    "\ube14\ub808\uc774\ub4dc\uc564\uc18c\uc6b8": collect_blade_and_soul_events,
    "\uac80\uc740\uc0ac\ub9c9": collect_black_desert_events,
    "\uac70\uc0c1": lambda: collect_via_github_fallback("\uac70\uc0c1"),
    "\ub358\uc804\uc564\ud30c\uc774\ud130": collect_dnf_events,
    "\ud14c\uc77c\uc988\ub7f0\ub108": lambda: collect_via_github_fallback("\ud14c\uc77c\uc988\ub7f0\ub108"),
    "\uce74\uc6b4\ud130\uc2a4\ud2b8\ub77c\uc774\ud06c \uc628\ub77c\uc778": collect_cso_events,
    "\ub9c8\ube44\ub178\uae30 \uc601\uc6c5\uc804": collect_heroes_events,
    "\ub77c\uadf8\ub098\ub85c\ud06c": collect_ragnarok_events,
    "\uc624\ub514\uc158": collect_audition_events,
    "\uc0ac\uc774\ud37c\uc988": collect_cyphers_events,
    "\ub354 \ud30c\uc774\ub110\uc2a4": collect_thefinals_events,
}


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def display_status(ends_on: str | None) -> str:
    """Calculate display state exclusively from the collected event end date."""
    if not ends_on:
        return "\uc9c4\ud589 \uc911"
    try:
        return "\uc9c4\ud589 \uc911" if date.fromisoformat(ends_on) >= date.today() else "\uc885\ub8cc"
    except ValueError:
        return "\uc9c4\ud589 \uc911"


def canonical_game_for_url(event_url: str | None, current_game: str | None) -> str | None:
    """Repair legacy console-encoding damage using the official event URL."""
    host = (event_url or "").lower()
    if "fconline.nexon.com" in host:
        return "FC ONLINE"
    if "maplestory.nexon.com" in host:
        return "\uba54\uc774\ud50c\uc2a4\ud1a0\ub9ac"
    if "mabinogi.nexon.com" in host:
        return "\ub9c8\ube44\ub178\uae30"
    if "tales.nexon.com" in host:
        return "\ud14c\uc77c\uc988\uc704\ubc84"
    if "elsword.nexon.com" in host:
        return "\uc5d8\uc18c\ub4dc"
    if "baram.nexon.com" in host:
        return "\ubc14\ub78c\uc758\ub098\ub77c"
    if "lostark.game.onstove.com" in host:
        return "\ub85c\uc2a4\ud2b8\uc544\ud06c"
    if "lineagem.plaync.com" in host:
        return "\ub9ac\ub2c8\uc9c0M"
    if "bns.plaync.com" in host:
        return "\ube14\ub808\uc774\ub4dc\uc564\uc18c\uc6b8"
    if "lineage.plaync.com" in host:
        return "\ub9ac\ub2c8\uc9c0"
    if "df.nexon.com" in host:
        return "\ub358\uc804\uc564\ud30c\uc774\ud130"
    if "tr.rhaon.co.kr" in host:
        return "\ud14c\uc77c\uc988\ub7f0\ub108"
    if "csonline.nexon.com" in host:
        return "\uce74\uc6b4\ud130\uc2a4\ud2b8\ub77c\uc774\ud06c \uc628\ub77c\uc778"
    if "heroes.nexon.com" in host:
        return "\ub9c8\ube44\ub178\uae30 \uc601\uc6c5\uc804"
    if "ro.gnjoy.com" in host:
        return "\ub77c\uadf8\ub098\ub85c\ud06c"
    if "audition.hangame.com" in host:
        return "\uc624\ub514\uc158"
    if "cyphers.nexon.com" in host:
        return "\uc0ac\uc774\ud37c\uc988"
    if "thefinals.nexon.com" in host:
        return "\ub354 \ud30c\uc774\ub110\uc2a4"
    return current_game


def normalize_existing(row: dict) -> dict:
    row = dict(row)
    row["game"] = canonical_game_for_url(row.get("event_url"), row.get("game"))
    collected_at = row.get("collected_at") or datetime.now(timezone.utc).isoformat()
    row.setdefault("first_collected_at", collected_at)
    row.setdefault("last_seen_at", collected_at)
    row.setdefault("is_active", True)
    return row


def main() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=LOG_PATH, level=logging.INFO, encoding="utf-8", format="%(asctime)s %(levelname)s %(message)s")

    # The last complete snapshot recovers candidates if a prior partial run lost them.
    records_by_url: dict[str, dict] = {}
    for row in [*load_rows(LAST_GOOD_PATH), *load_rows(OUTPUT_PATH)]:
        url = row.get("event_url")
        if url:
            records_by_url[url] = normalize_existing(row)

    refreshed_games: list[str] = []
    now = datetime.now(timezone.utc).isoformat()
    for game, collector in COLLECTORS.items():
        try:
            # Each collector reads its official source's ongoing-event list only.
            candidates = [asdict(item) for item in collector()]
            if not candidates:
                raise RuntimeError("collector returned no candidates")

            # A successful source establishes the current active set for that game.
            for record in records_by_url.values():
                if record.get("game") == game:
                    record["is_active"] = False
            for candidate in candidates:
                previous = records_by_url.get(candidate["event_url"], {})
                candidate["first_collected_at"] = previous.get("first_collected_at", now)
                # Detail-page registration dates are expensive to resolve; preserve a
                # verified prior value when a list collector does not provide one.
                candidate["published_on"] = candidate.get("published_on") or previous.get("published_on")
                candidate["last_seen_at"] = now
                candidate["status"] = display_status(candidate.get("ends_on"))
                candidate["is_active"] = True
                # Cached so the thumbnail survives the event page itself
                # going down once the event ends (a routine occurrence).
                candidate["hero_image_url"] = (
                    cache_thumbnail(candidate.get("hero_image_url"), "event_bench")
                    or candidate.get("hero_image_url")
                )
                records_by_url[candidate["event_url"]] = candidate
            refreshed_games.append(game)
            logging.info("%s: refreshed %s ongoing candidates", game, len(candidates))
        except Exception as error:
            logging.exception("%s: refresh failed; kept previous archive state: %s", game, error)

    if not refreshed_games:
        raise RuntimeError("No source refreshed; existing archive was not replaced.")

    for record in records_by_url.values():
        record["status"] = display_status(record.get("ends_on"))

    records = sorted(
        records_by_url.values(),
        key=lambda item: (
            bool(item.get("is_active", False)),
            item.get("published_on") or item.get("starts_on") or item.get("first_collected_at", ""),
        ),
        reverse=True,
    )
    temporary = OUTPUT_PATH.with_suffix(".tmp")
    rendered = json.dumps(records, ensure_ascii=False, indent=2)
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(OUTPUT_PATH)
    LAST_GOOD_PATH.write_text(rendered, encoding="utf-8")
    logging.info("Refresh complete: %s total archived / %s active candidates", len(records), sum(row["is_active"] for row in records))


if __name__ == "__main__":
    main()
