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


def day_window(date_str: str, now: datetime | None = None) -> tuple[datetime, datetime]:
    """KST midnight-to-midnight bounds for a single calendar date (the
    single-date browser that replaced the 오늘/3일/이번주 tabs). `end` is
    capped at `now` when `date_str` is today so a same-day view still only
    ever counts articles collected so far, not the whole 24h of a day
    that hasn't finished yet."""
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=KST)
    except ValueError as e:
        raise ValueError(f"invalid date: {date_str!r}") from e
    now = now or datetime.now(timezone.utc)
    start_local = target.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
    start = start_local.astimezone(timezone.utc)
    end = min(end_local.astimezone(timezone.utc), now)
    return start, end
