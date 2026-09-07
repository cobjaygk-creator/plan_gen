"""Phase 7: 매일 오전 7시(KST) 자동 갱신.

그 전까지는 화면에 이전 스냅샷이 그대로 유지된다 — 이 스레드가 하는 일은
"하루에 한 번, 정해진 시각에 수동 새로고침과 똑같은 파이프라인을 대신
눌러주는 것" 뿐이고, 그 시각이 되기 전에는 아무 것도 건드리지 않는다.

collector.py의 오래된 코멘트가 "no scheduler (Phase 7)"라고 적어둔 그 단계.
외부 cron/작업 스케줄러 없이, 이 프로세스 안에서 도는 데몬 스레드 하나로
충분하다 — 단일 인스턴스로 로컬에 떠 있는 배포 형태에 맞춘 선택이다.
"""
import logging
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..database import SessionLocal
from ..game_sites.portal_collector import refresh_portal_sites
from .highlights import refresh_and_save_highlights
from .periods import KST
from .refresh import refresh_industry_brief
from .routes import _brief_cache

logger = logging.getLogger(__name__)

DAILY_REFRESH_HOUR_KST = 7

# 타사 이벤트/타사 사이트 — LLM 호출이 없는 순수 스크레이핑이라 비용
# 걱정 없이 시간마다 돌린다(GitHub Pages 쪽 CI가 uxtler-pages.yml에서
# 쓰는 것과 같은 주기). 이 CI는 매번 "[skip ci]" 커밋만 남기는데, 그
# 접두어가 붙은 push는 GitHub가 다른 워크플로(deploy-oci.yml 포함)까지
# 통째로 건너뛰게 만든다 — 그래서 이 서버에 새 코드를 배포하는 커밋이
# 없으면 타사 이벤트/사이트 데이터가 영영 안 바뀌었다. 서버 스스로
# 갱신하게 해서 그 배포 타이밍 의존성을 없앤다.
BENCH_REFRESH_INTERVAL_SECONDS = 60 * 60
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_EVENT_BENCH_REFRESH_SCRIPT = _BACKEND_DIR / "event_bench_refresh.py"


def _seconds_until_next_run(now_kst: datetime) -> float:
    target = now_kst.replace(hour=DAILY_REFRESH_HOUR_KST, minute=0, second=0, microsecond=0)
    if target <= now_kst:
        target += timedelta(days=1)
    return (target - now_kst).total_seconds()


def _run_once() -> None:
    # "새로고침" 버튼(POST /refresh 뒤 /highlights/refresh)과 완전히 같은
    # 순서 — 자동/수동 경로가 서로 다른 결과를 내는 일이 없게 한다.
    db = SessionLocal()
    try:
        result = refresh_industry_brief(db)
        _brief_cache.clear()  # routes._serialize_brief의 "오늘" 캐시도 같이 비운다
        now = datetime.now(timezone.utc)
        refresh_and_save_highlights(db, "GAME", now)
        refresh_and_save_highlights(db, "AI", now)
        logger.info(
            "industry_brief: 07:00 KST auto-refresh done (collected=%d, classified=%d, brief_id=%d)",
            result.collected, result.classified, result.brief_id,
        )
    except Exception:
        # 실패해도 다음날 7시에 다시 시도한다 — 화면은 실패 전 스냅샷을
        # 계속 보여주면 되므로, 여기서 재시도 루프를 만들 필요는 없다.
        logger.exception("industry_brief: 07:00 KST auto-refresh failed")
    finally:
        db.close()


def _loop() -> None:
    while True:
        wait_seconds = _seconds_until_next_run(datetime.now(KST))
        threading.Event().wait(wait_seconds)
        _run_once()


def _run_bench_refresh_once() -> None:
    """수동 "수집"/"지금 수집" 버튼과 완전히 같은 경로를 그대로 재사용한다
    (event_bench는 별도 프로세스 스크립트, game_sites는 함수 호출) —
    자동/수동이 다른 결과를 내지 않게."""
    try:
        result = subprocess.run(
            [sys.executable, str(_EVENT_BENCH_REFRESH_SCRIPT)],
            cwd=_BACKEND_DIR, capture_output=True, text=True, timeout=600,
        )
        if result.returncode != 0:
            logger.error("event_bench 자동 갱신 실패(exit %d): %s", result.returncode, result.stderr[-2000:])
        else:
            logger.info("event_bench 자동 갱신 완료")
    except Exception:
        logger.exception("event_bench 자동 갱신 중 예외")

    try:
        refresh_portal_sites()
        logger.info("game_sites 자동 갱신 완료")
    except Exception:
        logger.exception("game_sites 자동 갱신 중 예외")


def _bench_loop() -> None:
    while True:
        threading.Event().wait(BENCH_REFRESH_INTERVAL_SECONDS)
        _run_bench_refresh_once()


def start_daily_refresh_scheduler() -> None:
    """앱 시작 시 한 번 호출. 데몬 스레드라 프로세스 종료를 막지 않는다.

    pytest 프로세스 안에서 `app.main`을 import할 때(테스트가 매번 그렇게
    한다)는 절대 스레드를 띄우지 않는다 — 실제 uvicorn 기동이 아니라
    TestClient가 만드는 격리된 테스트 DB 세션에서 도는 게 아니라 이 모듈이
    직접 여는 프로덕션 SessionLocal을 그대로 쓰기 때문에, 테스트 중에 켜지면
    실제 DB를 건드릴 위험이 있다.
    """
    if "pytest" in sys.modules:
        return
    threading.Thread(target=_loop, name="industry-brief-daily-refresh", daemon=True).start()
    logger.info("industry_brief: daily 07:00 KST auto-refresh scheduler started")
    threading.Thread(target=_bench_loop, name="event-bench-game-sites-hourly-refresh", daemon=True).start()
    logger.info("event_bench/game_sites: hourly auto-refresh scheduler started")
