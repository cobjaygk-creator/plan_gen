from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def build_collection_history(rows: list[dict], now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(KST).date()
    year_start = date(today.year, 1, 1)
    windows = {"d1": now - timedelta(days=1), "d7": now - timedelta(days=7), "d30": now - timedelta(days=30)}

    games: dict[str, dict] = {}
    for row in rows:
        name = row.get("game")
        if not name:
            continue
        game = games.setdefault(
            name,
            {
                "game": name, "publisher": row.get("publisher"), "total": 0, "active": 0,
                "lastSuccessAt": None, "firstCollectedAt": None,
                "d1": 0, "d7": 0, "d30": 0, "ytd": 0, "_daily": {},
            },
        )
        game["total"] += 1
        game["active"] += bool(row.get("is_active"))

        seen = _parse(row.get("last_seen_at"))
        if seen and (game["lastSuccessAt"] is None or seen > _parse(game["lastSuccessAt"])):
            game["lastSuccessAt"] = seen.isoformat()

        first = _parse(row.get("first_collected_at"))
        if first is None:
            continue
        if game["firstCollectedAt"] is None or first < _parse(game["firstCollectedAt"]):
            game["firstCollectedAt"] = first.isoformat()
        for key, cutoff in windows.items():
            game[key] += first >= cutoff
        collected_on = first.astimezone(KST).date()
        if collected_on >= year_start:
            game["ytd"] += 1
            game["_daily"].setdefault(collected_on, []).append(
                {
                    "title": row.get("title"), "url": row.get("event_url"),
                    "endsOn": row.get("ends_on"), "active": bool(row.get("is_active")),
                    "collectedAt": first.isoformat(),
                }
            )

    result = []
    for game in games.values():
        daily = game.pop("_daily")
        game["daily"] = [
            {"date": day.isoformat(), "count": len(events), "events": sorted(events, key=lambda e: e["collectedAt"])}
            for day, events in sorted(daily.items(), reverse=True)
        ]
        result.append(game)
    result.sort(key=lambda g: g["game"])

    return {
        "generatedAt": now.isoformat(),
        "today": today.isoformat(),
        "yearStart": year_start.isoformat(),
        "totals": {key: sum(g[key] for g in result) for key in ("d1", "d7", "d30", "ytd", "total", "active")},
        "games": result,
    }
