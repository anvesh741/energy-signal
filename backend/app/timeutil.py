"""All stored timestamps are timezone-aware UTC. Local days are derived, never stored as datetimes."""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def local_midnight_utc(local_date: date, tz_name: str) -> datetime:
    """Start of a local calendar day, expressed in UTC."""
    return datetime.combine(local_date, time.min, tzinfo=ZoneInfo(tz_name)).astimezone(
        timezone.utc
    )


def add_business_days(ts: datetime, n: int) -> datetime:
    out = ts
    while n > 0:
        out += timedelta(days=1)
        if out.weekday() < 5:
            n -= 1
    return out


def add_months(ts: datetime, n: int) -> datetime:
    month = ts.month - 1 + n
    return ts.replace(year=ts.year + month // 12, month=month % 12 + 1, day=1)
