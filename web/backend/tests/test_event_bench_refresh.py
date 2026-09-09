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
