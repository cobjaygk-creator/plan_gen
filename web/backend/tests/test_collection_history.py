import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import app.deps as deps_module
import app.event_bench.routes as event_routes
from app.event_bench.collection_history import build_collection_history

NOW = datetime(2026, 10, 23, 3, 0, tzinfo=timezone.utc)  # KST 2026-10-23 12:00


def _row(game, title, first_ago, *, seen_ago=1, active=True, first=None):
    first_at = first if first is not None else (NOW - first_ago).isoformat()
    return {
        "game": game, "publisher": "P", "title": title, "event_url": f"https://x/{title}",
        "ends_on": "2026-12-31", "is_active": active,
        "first_collected_at": first_at, "last_seen_at": (NOW - timedelta(hours=seen_ago)).isoformat(),
    }


def test_counts_by_rolling_window_and_year():
    rows = [
        _row("A", "new", timedelta(hours=2)),
        _row("A", "week", timedelta(days=3)),
        _row("A", "month", timedelta(days=20)),
        _row("A", "year", timedelta(days=100)),
        _row("A", "last-year", None, first="2025-12-31T00:00:00+00:00"),
    ]
    game = build_collection_history(rows, NOW)["games"][0]
    assert (game["d1"], game["d7"], game["d30"], game["ytd"]) == (1, 2, 3, 4)
    assert game["total"] == 5
    # 작년 수집분은 총계에는 있지만 올해/날짜별 이력에는 없다
    assert sum(day["count"] for day in game["daily"]) == 4


def test_daily_groups_use_kst_dates():
    # UTC 10-22 16:00 = KST 10-23 01:00, UTC 10-22 14:59 = KST 10-22 23:59
    rows = [
        _row("A", "after-midnight", None, first="2026-10-22T16:00:00+00:00"),
        _row("A", "before-midnight", None, first="2026-10-22T14:59:00+00:00"),
    ]
    daily = build_collection_history(rows, NOW)["games"][0]["daily"]
    assert [(d["date"], d["count"]) for d in daily] == [("2026-10-23", 1), ("2026-10-22", 1)]
    assert daily[0]["events"][0]["title"] == "after-midnight"


def test_last_success_is_newest_last_seen_and_active_counted():
    rows = [
        _row("A", "old", timedelta(days=5), seen_ago=100, active=False),
        _row("A", "live", timedelta(days=5), seen_ago=3),
    ]
    game = build_collection_history(rows, NOW)["games"][0]
    assert game["lastSuccessAt"] == (NOW - timedelta(hours=3)).isoformat()
    assert (game["total"], game["active"]) == (2, 1)


def test_missing_first_collected_at_is_counted_but_not_dated():
    rows = [_row("A", "no-date", None, first=""), _row("A", "ok", timedelta(hours=1))]
    game = build_collection_history(rows, NOW)["games"][0]
    assert game["total"] == 2 and game["d1"] == 1 and game["ytd"] == 1


def test_totals_sum_across_games_and_games_are_sorted():
    rows = [_row("나", "x", timedelta(hours=1)), _row("가", "y", timedelta(hours=1)), _row("가", "z", timedelta(days=2))]
    result = build_collection_history(rows, NOW)
    assert [g["game"] for g in result["games"]] == ["가", "나"]
    assert result["totals"]["d1"] == 2 and result["totals"]["d7"] == 3 and result["totals"]["total"] == 3
    assert result["today"] == "2026-10-23" and result["yearStart"] == "2026-01-01"


def test_empty_rows():
    result = build_collection_history([], NOW)
    assert result["games"] == [] and result["totals"]["total"] == 0


@pytest.fixture()
def sample_file(tmp_path, monkeypatch):
    path = tmp_path / "events.json"
    path.write_text(json.dumps([_row("A", "e", timedelta(hours=1))]), encoding="utf-8")
    monkeypatch.setattr(event_routes, "_SAMPLE_PATH", path)
    return path


def test_endpoint_requires_login(client, sample_file):
    assert client.get("/event-bench/collection-history").status_code == 401


def test_endpoint_rejects_non_admin(client, make_user, sample_file, monkeypatch):
    monkeypatch.setattr(deps_module, "ADMIN_EMAIL", "admin@team.com")
    make_user(email="other@team.com", password="hunter2", name="다른사람")
    client.post("/auth/login", json={"email": "other@team.com", "password": "hunter2"})
    assert client.get("/event-bench/collection-history").status_code == 403


def test_endpoint_returns_history_for_admin(client, make_user, sample_file, monkeypatch):
    monkeypatch.setattr(deps_module, "ADMIN_EMAIL", "admin@team.com")
    make_user(email="admin@team.com", password="correcthorse", name="관리자")
    client.post("/auth/login", json={"email": "admin@team.com", "password": "correcthorse"})
    body = client.get("/event-bench/collection-history").json()
    assert body["games"][0]["game"] == "A"
    assert body["totals"]["total"] == 1


def test_endpoint_404_when_no_data_yet(client, make_user, tmp_path, monkeypatch):
    monkeypatch.setattr(event_routes, "_SAMPLE_PATH", tmp_path / "missing.json")
    monkeypatch.setattr(deps_module, "ADMIN_EMAIL", "admin@team.com")
    make_user(email="admin@team.com", password="correcthorse", name="관리자")
    client.post("/auth/login", json={"email": "admin@team.com", "password": "correcthorse"})
    assert client.get("/event-bench/collection-history").status_code == 404
