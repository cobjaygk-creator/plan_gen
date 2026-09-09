import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import event_bench_refresh
from app.event_bench.nexon_sample import EventCandidate


def test_collect_via_github_fallback_reconstructs_event_candidates(monkeypatch):
    # tales.nexon.com/tr.rhaon.co.kr/gersang.co.kr/thefinals.nexon.com이 오라클 클라우드 IP를
    # 차단해서, 운영 서버는 GitHub Actions가 대신 수집해 커밋해둔 JSON을
    # raw.githubusercontent.com에서 읽어온다 — 그 파싱·재구성 로직을 고정.
    payload = {
        "테일즈위버": [{
            "publisher": "NEXON Korea", "game": "테일즈위버", "title": "테스트 이벤트",
            "event_url": "https://tales.nexon.com/News/Event/1", "hero_image_url": None,
            "starts_on": "2026-09-01", "ends_on": "2026-09-30", "published_on": None,
            "status": "ongoing", "event_format": "board", "collected_at": "2026-09-09T00:00:00+00:00",
        }],
        "거상": [],
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr(event_bench_refresh.urllib.request, "urlopen", lambda url, timeout=20: FakeResponse())

    result = event_bench_refresh.collect_via_github_fallback("테일즈위버")
    assert result == [EventCandidate(**payload["테일즈위버"][0])]
    assert event_bench_refresh.collect_via_github_fallback("거상") == []


def test_collect_via_github_fallback_returns_empty_for_unknown_game(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"{}"

    monkeypatch.setattr(event_bench_refresh.urllib.request, "urlopen", lambda url, timeout=20: FakeResponse())
    assert event_bench_refresh.collect_via_github_fallback("존재하지않는게임") == []


def test_collectors_route_blocked_ip_games_through_fallback():
    # COLLECTORS 딕셔너리가 이 게임들만 GitHub fallback을 쓰도록 배선돼
    # 있는지 확인 — 실수로 원래 collect_* 함수로 되돌리는 회귀를 막는다.
    for game in ("테일즈위버", "테일즈런너", "거상", "더 파이널스", "프라시아전기", "사이퍼즈"):
        collector = event_bench_refresh.COLLECTORS[game]
        assert collector.__name__ == "<lambda>", f"{game}는 GitHub fallback 람다여야 한다"


def test_main_keeps_previously_cached_thumbnail_when_this_cycle_extracts_none(monkeypatch, tmp_path):
    # 리니지/리니지M/블레이드앤소울에서 실제로 겪은 회귀: 이전 회차에 캐싱을
    # 성공한 hero_image_url이, 이번 회차의 원본 사이트 추출이 일시적으로
    # None을 반환했다는 이유만으로 null로 덮어써졌었다. published_on과
    # 똑같이 이전 값을 fallback으로 남겨야 한다.
    event_url = "https://lineage.plaync.com/promo/example"
    monkeypatch.setattr(event_bench_refresh, "OUTPUT_PATH", tmp_path / "nexon_events_sample.json")
    monkeypatch.setattr(event_bench_refresh, "LAST_GOOD_PATH", tmp_path / "nexon_events_last_good.json")
    monkeypatch.setattr(event_bench_refresh, "LOG_PATH", tmp_path / "refresh.log")
    event_bench_refresh.OUTPUT_PATH.write_text(json.dumps([{
        "publisher": "NCSOFT", "game": "리니지", "title": "기존 이벤트", "event_url": event_url,
        "hero_image_url": "data/thumbnails/event_bench/already-cached.jpg",
        "starts_on": "2026-09-01", "ends_on": "2026-09-30", "published_on": "2026-09-01",
        "status": "진행 중", "event_format": "full_page", "collected_at": "2026-09-01T00:00:00+00:00",
        "first_collected_at": "2026-09-01T00:00:00+00:00", "last_seen_at": "2026-09-01T00:00:00+00:00",
        "is_active": True,
    }]), encoding="utf-8")

    def fake_collector():
        return [SimpleNamespace(**{
            "publisher": "NCSOFT", "game": "리니지", "title": "기존 이벤트", "event_url": event_url,
            "hero_image_url": None, "starts_on": "2026-09-01", "ends_on": "2026-09-30",
            "published_on": None, "status": "ongoing", "event_format": "full_page",
            "collected_at": "2026-09-09T00:00:00+00:00",
        })]

    monkeypatch.setattr(event_bench_refresh, "COLLECTORS", {"리니지": fake_collector})
    monkeypatch.setattr(event_bench_refresh, "asdict", lambda item: vars(item))
    monkeypatch.setattr(event_bench_refresh, "cache_thumbnail", lambda url, feature: None)

    event_bench_refresh.main()

    saved = json.loads(event_bench_refresh.OUTPUT_PATH.read_text(encoding="utf-8"))
    assert saved[0]["hero_image_url"] == "data/thumbnails/event_bench/already-cached.jpg"
