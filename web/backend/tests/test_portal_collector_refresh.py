import json

from app.game_sites import portal_collector


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_refresh_backfills_missing_thumbnail_for_a_known_site(monkeypatch, tmp_path):
    # official_sites.json은 한 번 본 URL을 다시는 새 항목으로 추가하지
    # 않지만(중복 방지), 그 항목의 thumbnail_url이 여전히 비어있다면 이번
    # 수집 회차가 이미 긁어온 값으로 채워줘야 한다 — refresh_portal_sites의
    # 영구 스킵 로직 때문에 한 번 놓친 썸네일이 절대 복구되지 않던 문제.
    url = "https://example-game.nexon.com"
    monkeypatch.setattr(portal_collector, "OFFICIAL_PATH", tmp_path / "official_sites.json")
    monkeypatch.setattr(portal_collector, "SNAPSHOT_PATH", tmp_path / "portal_snapshot.json")
    monkeypatch.setattr(portal_collector, "LAST_REFRESH_PATH", tmp_path / "last_refresh.json")
    _write(portal_collector.OFFICIAL_PATH, [{
        "id": "portal:NEXON:1", "game_name": "Example Game", "site_name": "Example Game",
        "site_type": "OFFICIAL", "url": url, "thumbnail_url": None, "publisher": "NEXON",
        "platform": [], "discovered_at": "2026-08-01T00:00:00+00:00", "published_on": None,
        "source": "OFFICIAL_PORTAL:NEXON", "evidence_url": portal_collector.PORTALS["NEXON"],
        "status": "ACTIVE", "verified_at": "2026-08-01T00:00:00+00:00",
    }])

    monkeypatch.setattr(
        portal_collector, "discover_portal_sites",
        lambda: ([{"url": url, "game_name": "Example Game", "publisher": "NEXON",
                    "published_on": None, "thumbnail_url": "https://cdn.example.com/hero.jpg",
                    "portal": "NEXON"}], {}),
    )
    monkeypatch.setattr(portal_collector, "cache_thumbnail", lambda url, feature: f"data/thumbnails/{feature}/cached.jpg")

    portal_collector.refresh_portal_sites()

    saved = json.loads(portal_collector.OFFICIAL_PATH.read_text(encoding="utf-8"))
    assert saved[0]["thumbnail_url"] == "data/thumbnails/game_sites/cached.jpg"
    # A known URL is still never re-added as a second/new entry.
    assert len(saved) == 1


def test_refresh_leaves_known_site_alone_when_this_cycle_has_no_image_either(monkeypatch, tmp_path):
    url = "https://example-game.nexon.com"
    monkeypatch.setattr(portal_collector, "OFFICIAL_PATH", tmp_path / "official_sites.json")
    monkeypatch.setattr(portal_collector, "SNAPSHOT_PATH", tmp_path / "portal_snapshot.json")
    monkeypatch.setattr(portal_collector, "LAST_REFRESH_PATH", tmp_path / "last_refresh.json")
    _write(portal_collector.OFFICIAL_PATH, [{
        "id": "portal:NEXON:1", "game_name": "Example Game", "site_name": "Example Game",
        "site_type": "OFFICIAL", "url": url, "thumbnail_url": None, "publisher": "NEXON",
        "platform": [], "discovered_at": "2026-08-01T00:00:00+00:00", "published_on": None,
        "source": "OFFICIAL_PORTAL:NEXON", "evidence_url": portal_collector.PORTALS["NEXON"],
        "status": "ACTIVE", "verified_at": "2026-08-01T00:00:00+00:00",
    }])
    monkeypatch.setattr(
        portal_collector, "discover_portal_sites",
        lambda: ([{"url": url, "game_name": "Example Game", "publisher": "NEXON",
                    "published_on": None, "thumbnail_url": None, "portal": "NEXON"}], {}),
    )

    portal_collector.refresh_portal_sites()

    saved = json.loads(portal_collector.OFFICIAL_PATH.read_text(encoding="utf-8"))
    assert saved[0]["thumbnail_url"] is None
    assert len(saved) == 1
