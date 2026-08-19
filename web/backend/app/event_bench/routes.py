"""Read-only API for the isolated event-design benchmark sample."""
import json
from pathlib import Path
import subprocess
import sys
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import get_current_user
from ..models import User


router = APIRouter(prefix="/event-bench", tags=["event-bench"])
_BACKEND_PATH = Path(__file__).resolve().parents[2]
_SAMPLE_PATH = _BACKEND_PATH / "data" / "event_bench" / "nexon_events_sample.json"
_REFRESH_SCRIPT = _BACKEND_PATH / "event_bench_refresh.py"
_REFRESH_LOCK = Lock()


@router.get("/candidates")
def list_candidates(user: User = Depends(get_current_user)):
    """Return the locally collected, verified FC ONLINE event candidates."""
    if not _SAMPLE_PATH.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "아직 수집된 이벤트 벤치마크 샘플이 없습니다.")
    try:
        candidates = json.loads(_SAMPLE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "이벤트 벤치마크 샘플을 읽지 못했습니다.") from exc
    last_refreshed_at = max(
        (item.get("last_seen_at", "") for item in candidates),
        default="",
    )
    refreshed_event_count = sum(
        item.get("first_collected_at") == last_refreshed_at
        for item in candidates
    )
    return {
        "mode": "test",
        "source": "NEXON Korea · FC ONLINE / 메이플스토리 / 마비노기 / 테일즈위버 공식 이벤트 목록",
        "description": "자동 수집 검증용 목록입니다. 디자인 분석·평가는 아직 적용하지 않았습니다.",
        "last_refreshed_at": last_refreshed_at or None,
        "refreshed_event_count": refreshed_event_count,
        "candidates": candidates,
    }



@router.post("/refresh")
def refresh_candidates(user: User = Depends(get_current_user)):
    """Run the isolated event collector once and return the refreshed list."""
    if not _REFRESH_LOCK.acquire(blocking=False):
        raise HTTPException(status.HTTP_409_CONFLICT, "\uc774\ubca4\ud2b8 \uc218\uc9d1\uc774 \uc774\ubbf8 \uc9c4\ud589 \uc911\uc785\ub2c8\ub2e4.")
    try:
        result = subprocess.run(
            [sys.executable, str(_REFRESH_SCRIPT)],
            cwd=_BACKEND_PATH,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=240,
            check=False,
        )
        if result.returncode != 0:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "\uc774\ubca4\ud2b8 \uc218\uc9d1\uc744 \uc644\ub8cc\ud558\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4.",
            )
        return list_candidates(user)
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status.HTTP_504_GATEWAY_TIMEOUT,
            "\uc774\ubca4\ud2b8 \uc218\uc9d1 \uc2dc\uac04\uc744 \ucd08\uacfc\ud588\uc2b5\ub2c8\ub2e4.",
        ) from exc
    finally:
        _REFRESH_LOCK.release()
