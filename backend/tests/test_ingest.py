from datetime import date, datetime, timedelta, timezone

from sqlmodel import select

from app.ingest import rebuild_rollups, upsert_observations
from app.models import DailyRollup, Observation
from app.rollup import utc_bounds_of_local_date


def test_upsert_overwrites_revised_values(session):
    t = datetime(2024, 1, 15, 5, tzinfo=timezone.utc)
    upsert_observations(session, "eia-us48-demand", [{"ts_utc": t, "value": 1.0}])
    upsert_observations(session, "eia-us48-demand", [{"ts_utc": t, "value": 2.0}])
    rows = session.exec(select(Observation)).all()
    assert len(rows) == 1 and rows[0].value == 2.0
    assert rows[0].ts_utc.tzinfo is not None


def test_rebuild_only_touched_local_dates(session):
    start, _ = utc_bounds_of_local_date(date(2024, 1, 15), "America/New_York")
    pts = [{"ts_utc": start + timedelta(hours=i), "value": 10.0} for i in range(48)]
    upsert_observations(session, "eia-us48-demand", pts)
    rebuild_rollups(session, "eia-us48-demand")
    # revise one hour on the 16th; only that day is recomputed
    revised = start + timedelta(hours=30)
    upsert_observations(session, "eia-us48-demand", [{"ts_utc": revised, "value": 34.0}])
    rebuild_rollups(session, "eia-us48-demand", [revised])
    by_day = {r.local_date: r for r in session.exec(select(DailyRollup))}
    assert by_day[date(2024, 1, 15)].total == 240.0
    assert by_day[date(2024, 1, 16)].total == 264.0
    assert by_day[date(2024, 1, 16)].peak == 34.0
