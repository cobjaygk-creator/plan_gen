"""Phase 7: 매일 오전 7시(KST) 자동 갱신.

그 전까지는 화면에 이전 스냅샷이 그대로 유지된다 — 이 스레드가 하는 일은
"하루에 한 번, 정해진 시각에 수동 새로고침과 똑같은 파이프라인을 대신
눌러주는 것" 뿐이고, 그 시각이 되기 전에는 아무 것도 건드리지 않는다.

collector.py의 오래된 코멘트가 "no scheduler (Phase 7)"라고 적어둔 그 단계.
외부 cron/작업 스케줄러 없이, 이 프로세스 안에서 도는 데몬 스레드 하나로
충분하다 — 단일 인스턴스로 로컬에 떠 있는 배포 형태에 맞춘 선택이다.
"""
import logging
import sys
import threading
from datetime import datetime, timedelta, timezone

from ..database import SessionLocal
from .highlights import refresh_and_save_highlights
from .periods import KST
from .refresh import refresh_industry_brief

logger = logging.getLogger(__name__)

DAILY_REFRESH_HOUR_KST = 7


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
    thread = threading.Thread(target=_loop, name="industry-brief-daily-refresh", daemon=True)
    thread.start()
    logger.info("industry_brief: daily 07:00 KST auto-refresh scheduler started")
