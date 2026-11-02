"""Weekly releases are polled inside a window, not on a fixed cron, because holidays shift them.

retail  (gasoline/diesel): usually Monday afternoon ET; holiday weeks slip to Tuesday.
storage (weekly gas storage): usually Thursday 10:30 ET; holiday weeks move to Wednesday or Friday.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ET = "America/New_York"


@dataclass(frozen=True)
class ReleaseWindow:
    start_weekday: int
    start_hour: int
    end_weekday: int
    end_hour: int
    tz_name: str = ET


RELEASES = {
    "retail": ReleaseWindow(0, 12, 2, 12),  # Mon 12:00 – Wed 12:00 ET
    "storage": ReleaseWindow(2, 10, 4, 18),  # Wed 10:00 – Fri 18:00 ET
}


def _minutes_into_week(local: datetime) -> int:
    return local.weekday() * 24 * 60 + local.hour * 60 + local.minute


def window_start(now: datetime, window: ReleaseWindow) -> datetime | None:
    """Start of the window containing `now`, or None when outside it."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=ZoneInfo("UTC"))
    local = now.astimezone(ZoneInfo(window.tz_name))
    minutes = _minutes_into_week(local)
    start = window.start_weekday * 24 * 60 + window.start_hour * 60
    end = window.end_weekday * 24 * 60 + window.end_hour * 60
    if not start <= minutes < end:
        return None
    monday = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    naive = monday.replace(tzinfo=None) + timedelta(days=window.start_weekday, hours=window.start_hour)
    return naive.replace(tzinfo=ZoneInfo(window.tz_name))


def in_weekly_release_window(now: datetime, window: ReleaseWindow = RELEASES["retail"]) -> bool:
    return window_start(now, window) is not None
