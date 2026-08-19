"""Calendar windows and daily cache keys for Industry Brief range tabs."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

KST = timezone(timedelta(hours=9), name="KST")
PERIOD_LABELS = {
    "today": "오늘", "3d": "최근 3일", "week": "이번 주",
}


def period_window(period: str, now: datetime | None = None) -> tuple[datetime, datetime, str]:
    if period not in PERIOD_LABELS:
        raise ValueError(period)
    end = now or datetime.now(timezone.utc)
    local_end = end.astimezone(KST)
    if period == "today":
        start_local = local_end.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "3d":
        start_local = local_end - timedelta(days=3)
    elif period == "week":
        start_local = (local_end - timedelta(days=local_end.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        raise ValueError(period)
    return start_local.astimezone(timezone.utc), end, f"{local_end.date().isoformat()}:{period}"
