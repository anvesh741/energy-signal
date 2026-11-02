from datetime import date, datetime, timedelta, timezone

from app.models import Observation
from app.rollup import (
    expected_hours_for_local_date,
    is_complete,
    local_date_of,
    prior_complete_week_change,
    rollup_hourly,
    utc_bounds_of_local_date,
)

NY = "America/New_York"


def _obs(ts, value=100.0):
    return Observation(series_id="eia-us48-demand", ts_utc=ts, value=value, fetched_at=ts)


def _day(local_date, n_hours=None, value=100.0):
    start, end = utc_bounds_of_local_date(local_date, NY)
    hours = int((end - start).total_seconds() // 3600)
    return [_obs(start + timedelta(hours=i), value) for i in range(n_hours if n_hours is not None else hours)]


def test_us48_local_date_uses_new_york():
    # 04:00 UTC is 23:00 the previous day in EST
    assert local_date_of(datetime(2024, 1, 15, 4, tzinfo=timezone.utc), NY) == date(2024, 1, 14)


def test_dst_expected_hours():
    assert expected_hours_for_local_date(date(2024, 3, 10), NY) == 23
    assert expected_hours_for_local_date(date(2024, 11, 3), NY) == 25
    assert expected_hours_for_local_date(date(2024, 6, 1), NY) == 24


def test_fall_back_day_counts_repeated_hour():
    (row,) = rollup_hourly("x", NY, _day(date(2024, 11, 3)))
    assert row.hour_count == 25 and row.expected_hours == 25
    assert row.quality == "complete" and row.dst_flag


def test_spring_forward_complete_with_23_and_22_hours():
    (row,) = rollup_hourly("x", NY, _day(date(2024, 3, 10)))
    assert row.expected_hours == 23 and row.quality == "complete"
    (row,) = rollup_hourly("x", NY, _day(date(2024, 3, 10), 22))
    assert row.quality == "complete"  # one missing hour allowed
    (row,) = rollup_hourly("x", NY, _day(date(2024, 3, 10), 21))
    assert row.quality == "partial"


def test_partial_day_and_one_missing_hour():
    (row,) = rollup_hourly("x", NY, _day(date(2024, 1, 15), 10))
    assert row.quality == "partial" and not is_complete(row.hour_count, row.expected_hours)
    obs = [_obs(o.ts_utc, 200 + i) for i, o in enumerate(_day(date(2024, 1, 16), 23))]
    (row,) = rollup_hourly("x", NY, obs)
    assert row.quality == "complete" and row.peak == 222


def test_partial_today_never_looks_like_a_crash():
    obs = []
    for i in range(14):
        obs += _day(date(2024, 1, 1) + timedelta(days=i))
    obs += _day(date(2024, 1, 15), 6)  # "today", 6 hours in
    change = prior_complete_week_change(rollup_hourly("x", NY, obs))
    assert change["recent_end"] == "2024-01-14"
    assert abs(change["pct_change"]) < 1e-9
