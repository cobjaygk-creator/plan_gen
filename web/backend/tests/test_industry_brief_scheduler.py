from datetime import datetime

from app.industry_brief.periods import KST
from app.industry_brief.scheduler import _seconds_until_next_run, start_daily_refresh_scheduler
import threading


def test_seconds_until_next_run_same_day_before_seven():
    now = datetime(2026, 9, 7, 3, 0, 0, tzinfo=KST)
    seconds = _seconds_until_next_run(now)
    assert seconds == 4 * 3600


def test_seconds_until_next_run_rolls_over_after_seven():
    now = datetime(2026, 9, 7, 7, 0, 1, tzinfo=KST)
    seconds = _seconds_until_next_run(now)
    # Just past 07:00 -> waits almost a full day for tomorrow's 07:00.
    assert 23 * 3600 < seconds < 24 * 3600


def test_seconds_until_next_run_exactly_at_seven_rolls_to_tomorrow():
    now = datetime(2026, 9, 7, 7, 0, 0, tzinfo=KST)
    seconds = _seconds_until_next_run(now)
    assert seconds == 24 * 3600


def test_scheduler_does_not_start_a_thread_under_pytest():
    before = threading.active_count()
    start_daily_refresh_scheduler()
    assert threading.active_count() == before
