"""GitHub Actions 전용 — 오라클 클라우드 IP를 차단하는 소스를 대신 수집한다.

tales.nexon.com(테일즈위버)/tr.rhaon.co.kr(테일즈런너)/gersang.co.kr(거상)/
thefinals.nexon.com(더 파이널스) 넷 다 운영 서버(Oracle Cloud IP)에서
실행하면 403/타임아웃으로 막히는 게 직접 확인됐다(같은 코드가 GitHub
Actions·집/사무실 IP에서는 정상 동작). wp.nexon.com(프라시아전기)은
개발 환경에서도 이미 정적 요청과 브라우저 렌더링 결과가 달라 이벤트
목록 자체가 안 잡히는 걸 확인해서, 검증 삼아 여기에 같이 포함한다.
IP 대역 차단이라 코드로 우회할 수 없어서, 이 스크립트가 GitHub Actions의
망을 빌려 대신 수집해 결과를 커밋해두면, 운영 서버는 이 파일을
raw.githubusercontent.com에서 매시간 직접 fetch해 병합한다
(event_bench_refresh.py의 _collect_via_github_fallback) — git/rsync를
거치지 않는 순수 HTTP 요청이라, data/ci를 배포가 덮어쓰던 것과 같은
종류의 충돌이 생기지 않는다.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from app.event_bench.nexon_sample import (
    collect_gersang_events,
    collect_talesrunner_events,
    collect_talesweaver_events,
    collect_thefinals_events,
    collect_wp_events,
)

OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "github-collected" / "fallback_events.json"

COLLECTORS = {
    "테일즈위버": collect_talesweaver_events,
    "테일즈런너": collect_talesrunner_events,
    "거상": collect_gersang_events,
    "더 파이널스": collect_thefinals_events,
    "프라시아전기": collect_wp_events,
}


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    previous: dict[str, list[dict]] = {}
    if OUTPUT_PATH.is_file():
        try:
            previous = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = {}

    result: dict[str, list[dict]] = {}
    for game, collector in COLLECTORS.items():
        try:
            candidates = [asdict(item) for item in collector()]
            if not candidates:
                raise RuntimeError("collector returned no candidates")
            result[game] = candidates
            print(f"{game}: {len(candidates)}건 수집")
        except Exception as error:
            # 실패한 소스는 직전 성공분을 그대로 유지한다 — event_bench_refresh.py
            # 본연의 "실패 시 이전 상태 유지" 원칙과 같다.
            result[game] = previous.get(game, [])
            print(f"{game}: 수집 실패, 이전 값({len(result[game])}건) 유지 - {error}")

    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
