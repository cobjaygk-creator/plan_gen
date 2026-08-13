"""Read-only API for the isolated event-design benchmark sample."""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import get_current_user
from ..models import User


router = APIRouter(prefix="/event-bench", tags=["event-bench"])
_SAMPLE_PATH = Path(__file__).resolve().parents[2] / "data" / "event_bench" / "nexon_events_sample.json"


@router.get("/candidates")
def list_candidates(user: User = Depends(get_current_user)):
    """Return the locally collected, verified FC ONLINE event candidates."""
    if not _SAMPLE_PATH.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "아직 수집된 이벤트 벤치마크 샘플이 없습니다.")
    try:
        candidates = json.loads(_SAMPLE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "이벤트 벤치마크 샘플을 읽지 못했습니다.") from exc
    return {
        "mode": "test",
        "source": "NEXON Korea · FC ONLINE / 메이플스토리 / 마비노기 / 테일즈위버 공식 이벤트 목록",
        "description": "자동 수집 검증용 목록입니다. 디자인 분석·평가는 아직 적용하지 않았습니다.",
        "candidates": candidates,
    }

