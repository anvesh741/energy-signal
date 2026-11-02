"""Local-calendar-day aggregation of hourly electricity.

A "day" is a local calendar day in Series.local_tz (US48 = America/New_York).
Complete only if hour_count >= expected_hours - 1 (23/24/25 from the tz calendar).
Partial days are excluded from forecasts, backtests, insights and KPIs, so an
incomplete "today" never looks like a demand crash.
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models import DailyRollup, Observation
from app.timeutil import as_utc


def expected_hours_for_local_date(local_date: date, tz_name: str) -> int:
    tz = ZoneInfo(tz_name)
    start = datetime.combine(local_date, time.min, tzinfo=tz)
    end = datetime.combine(local_date + timedelta(days=1), time.min, tzinfo=tz)
    seconds = (end.astimezone(timezone.utc) - start.astimezone(timezone.utc)).total_seconds()
    return int(round(seconds / 3600))


def local_date_of(ts_utc: datetime, tz_name: str) -> date:
    return as_utc(ts_utc).astimezone(ZoneInfo(tz_name)).date()


def utc_bounds_of_local_date(local_date: date, tz_name: str) -> tuple[datetime, datetime]:
    tz = ZoneInfo(tz_name)
    start = datetime.combine(local_date, time.min, tzinfo=tz).astimezone(timezone.utc)
    end = datetime.combine(local_date + timedelta(days=1), time.min, tzinfo=tz).astimezone(
        timezone.utc
    )
    return start, end


def is_complete(hour_count: int, expected_hours: int) -> bool:
    return hour_count >= expected_hours - 1


def rollup_hourly(
    series_id: str,
    tz_name: str,
    observations: list[Observation],
) -> list[DailyRollup]:
    # key by UTC instant: the repeated 01:00 local hour on fall-back days stays distinct
    by_day: dict[date, dict[datetime, float]] = defaultdict(dict)
    for obs in observations:
        ts = as_utc(obs.ts_utc)
        by_day[local_date_of(ts, tz_name)][ts] = obs.value

    rows: list[DailyRollup] = []
    for local_date, hours in sorted(by_day.items()):
        expected = expected_hours_for_local_date(local_date, tz_name)
        values = list(hours.values())
        hour_count = len(hours)
        rows.append(
            DailyRollup(
                series_id=series_id,
                local_date=local_date,
                local_tz=tz_name,
                total=float(sum(values)),
                peak=float(max(values)),
                hour_count=hour_count,
                expected_hours=expected,
                quality="complete" if is_complete(hour_count, expected) else "partial",
                dst_flag=expected != 24,
            )
        )
    return rows


def prior_complete_week_change(rollups: list[DailyRollup]) -> dict | None:
    """Last 7 complete local days vs the 7 complete local days before them."""
    days = sorted(
        ((r.local_date, r.total) for r in rollups if r.quality == "complete"),
        key=lambda p: p[0],
    )
    if len(days) < 14:
        return None
    recent, prior = days[-7:], days[-14:-7]
    recent_sum = sum(v for _, v in recent)
    prior_sum = sum(v for _, v in prior)
    if prior_sum == 0:
        return None
    return {
        "recent_start": recent[0][0].isoformat(),
        "recent_end": recent[-1][0].isoformat(),
        "prior_start": prior[0][0].isoformat(),
        "prior_end": prior[-1][0].isoformat(),
        "recent_total": recent_sum,
        "prior_total": prior_sum,
        "pct_change": (recent_sum - prior_sum) / prior_sum * 100,
        "local_tz": rollups[0].local_tz,
    }
