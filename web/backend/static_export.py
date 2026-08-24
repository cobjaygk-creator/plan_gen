"""Export the isolated benchmark data for the GitHub Pages build.

This deliberately exports only industry/event/site data.  The normal UXTLER
user and generation tables are never copied to the public static site.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
ROOT = BACKEND.parents[1]
FRONTEND_DATA = ROOT / "web" / "frontend" / "public" / "data"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.industry_brief import models as _industry_models  # noqa: F401
from app.industry_brief.models import DailyBrief
from app.industry_brief.periods import PERIOD_LABELS, period_window
from app.industry_brief.routes import _serialize_brief
from app.preregistration import models as _prereg_models  # noqa: F401
from app.preregistration.models import GamePreRegistration
from app.game_sites.routes import _load_event_sites, _load_official_sites, _last_refresh, SITE_TYPES

EVENT_PATH = BACKEND / "data" / "event_bench" / "nexon_events_sample.json"


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _event_payload() -> dict:
    rows = []
    if EVENT_PATH.is_file():
        try:
            rows = json.loads(EVENT_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            rows = []
    last = max((item.get("last_seen_at", "") for item in rows), default="")
    return {
        "mode": "static",
        "source": "공식 게임 이벤트 페이지",
        "description": "GitHub Actions가 수집한 이벤트 모음입니다.",
        "last_refreshed_at": last or None,
        "refreshed_event_count": sum(item.get("first_collected_at") == last for item in rows),
        "candidates": rows,
    }


def _site_payload(db) -> dict:
    by_url: dict[str, dict] = {}
    for item in db.scalars(
        select(GamePreRegistration)
        .where(GamePreRegistration.is_game_preregistration.is_(True))
        .order_by(GamePreRegistration.discovered_at.desc())
    ).all():
        url = item.preregistration_url
        by_url[url] = {
            "id": f"preregistration:{item.id}",
            "game_name": item.game_name,
            "site_name": item.campaign_name,
            "site_type": "PREREGISTRATION",
            "url": url,
            "thumbnail_url": item.main_visual_url or item.thumbnail_url,
            "publisher": item.publisher,
            "platform": (item.platform or "").split(",") if item.platform else [],
            "discovered_at": item.discovered_at,
            "source": "PREREGISTRATION",
            "status": item.status.upper(),
        }
    for item in _load_official_sites():
        if item.get("url"):
            by_url.setdefault(item["url"], item)
    sites = list(by_url.values())
    sites.sort(key=lambda item: str(item.get("discovered_at") or ""), reverse=True)
    last = _last_refresh()
    return {
        "types": list(SITE_TYPES),
        "total": len(sites),
        "last_refreshed_at": last["refreshed_at"],
        "refreshed_site_count": last["new_sites"],
        "sites": sites,
    }


def export() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        base = db.scalars(
            select(DailyBrief)
            .where(~DailyBrief.brief_date.contains(":"))
            .order_by(DailyBrief.generated_at.desc(), DailyBrief.id.desc())
        ).first()
        periods: dict[str, object | None] = {}
        if base is not None:
            for key in ("today", "3d", "week"):
                start, end, _ = period_window(key)
                payload = _serialize_brief(db, base, stats_period_start=start, stats_period_end=end)
                payload["periodLabel"] = PERIOD_LABELS[key]
                periods[key] = payload
        _write(FRONTEND_DATA / "industry-brief.json", {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "periods": periods,
        })
        _write(FRONTEND_DATA / "game-sites.json", _site_payload(db))
    _write(FRONTEND_DATA / "event-bench.json", _event_payload())


if __name__ == "__main__":
    export()
    print(f"static data exported to {FRONTEND_DATA}")
