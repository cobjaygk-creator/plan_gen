"""Aggregate verified game landing pages from isolated collection features."""
from __future__ import annotations

import json
from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import BENCHMARK_DATA_DIR
from ..database import get_db
from ..deps import get_current_user
from ..media_cache import as_absolute_path
from ..models import User
from ..preregistration.models import GamePreRegistration
from .portal_collector import LAST_REFRESH_PATH, OFFICIAL_PATH, refresh_portal_sites

router = APIRouter(prefix="/game-sites", tags=["game-sites"])
_EVENT_PATH = BENCHMARK_DATA_DIR / "event_bench" / "nexon_events_sample.json"
_OFFICIAL_PATH = OFFICIAL_PATH
SITE_TYPES = ("OFFICIAL", "PREREGISTRATION", "TEASER", "MICROSITE", "PROMOTION")


def _event_site_type(url: str, title: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.lower()
    value = f"{title} {path}".lower()
    if any(token in value for token in ("teaser", "티저", "countdown")):
        return "TEASER"
    if any(token in path for token in ("/promotion/", "/eventfull/", "/pg/", "/event/", "/page/event/")):
        return "MICROSITE"
    return "PROMOTION"


def _load_event_sites() -> list[dict]:
    if not _EVENT_PATH.is_file():
        return []
    try:
        rows = json.loads(_EVENT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    sites = []
    for item in rows:
        if item.get("event_format") != "full_page" or not item.get("event_url"):
            continue
        sites.append({
            "id": f"event:{item['event_url']}",
            "game_name": item.get("game") or "Unknown",
            "site_name": item.get("title") or item.get("game") or "Game site",
            "site_type": _event_site_type(item["event_url"], item.get("title") or ""),
            "url": item["event_url"],
            "thumbnail_url": as_absolute_path(item.get("hero_image_url")),
            "publisher": item.get("publisher"),
            "platform": [],
            "discovered_at": item.get("first_collected_at") or item.get("collected_at"),
            "source": "EVENT_BENCH",
            "status": "ACTIVE" if item.get("is_active", True) else "ARCHIVED",
        })
    return sites


def _load_official_sites() -> list[dict]:
    if not _OFFICIAL_PATH.is_file():
        return []
    try:
        rows = json.loads(_OFFICIAL_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [item for item in rows if item.get("url") and item.get("status") == "ACTIVE"]


def _last_refresh() -> dict:
    if not LAST_REFRESH_PATH.is_file():
        return {"refreshed_at": None, "new_sites": 0}
    try:
        result = json.loads(LAST_REFRESH_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"refreshed_at": None, "new_sites": 0}
    return {"refreshed_at": result.get("refreshed_at"), "new_sites": result.get("new_sites", 0)}


@router.post("/refresh")
def refresh_game_sites(user: User = Depends(get_current_user)):
    return refresh_portal_sites()


@router.get("/data")
def list_game_sites(
    site_type: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    preregistrations = db.scalars(
        select(GamePreRegistration)
        .where(GamePreRegistration.is_game_preregistration.is_(True))
        .order_by(GamePreRegistration.discovered_at.desc())
    ).all()
    by_url: dict[str, dict] = {}
    for item in preregistrations:
        url = item.preregistration_url
        by_url[url] = {
            "id": f"preregistration:{item.id}",
            "game_name": item.game_name,
            "site_name": item.campaign_name,
            "site_type": "PREREGISTRATION",
            "url": url,
            "thumbnail_url": as_absolute_path(item.main_visual_url or item.thumbnail_url),
            "publisher": item.publisher,
            "platform": item.platform.split(",") if item.platform else [],
            "discovered_at": item.discovered_at,
            "source": "PREREGISTRATION",
            "status": item.status.upper(),
        }
    for item in _load_official_sites():
        by_url.setdefault(item["url"], {**item, "thumbnail_url": as_absolute_path(item.get("thumbnail_url"))})
    # Event Benchmark full pages are campaign/event landing pages for games
    # already in service. They are intentionally excluded from this feature,
    # whose scope is the game itself: official, teaser, and preregistration sites.
    sites = list(by_url.values())
    if site_type in SITE_TYPES:
        sites = [item for item in sites if item["site_type"] == site_type]
    sites.sort(key=lambda item: str(item.get("discovered_at") or ""), reverse=True)
    last_refresh = _last_refresh()
    return {
        "types": list(SITE_TYPES),
        "total": len(sites),
        "last_refreshed_at": last_refresh["refreshed_at"],
        "refreshed_site_count": last_refresh["new_sites"],
        "sites": sites,
    }
