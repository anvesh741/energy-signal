import re
from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import Session, col, select

from app.catalog import CATALOG
from app.models import DailyRollup, Observation, RefreshRun, Series
from app.rollup import local_date_of, rollup_hourly, utc_bounds_of_local_date
from app.timeutil import as_utc, utc_now

UPSERT_CHUNK = 500
# httpx error messages include the request URL, which carries the api key
SECRET_PARAM = re.compile(r"(api_key=)[^&\s'\"]+")


def seed_series(session: Session) -> None:
    """Insert or refresh catalog rows. The catalog is the source of truth for metadata."""
    for series in CATALOG:
        current = session.get(Series, series.id)
        if current is None:
            session.add(Series.model_validate(series.model_dump()))
            continue
        for field, value in series.model_dump().items():
            setattr(current, field, value)
        session.add(current)
    session.flush()


def upsert_observations(
    session: Session,
    series_id: str,
    points: list[dict],
    fetched_at: datetime | None = None,
) -> int:
    """Upsert on (series_id, ts_utc). v1 overwrites revised values (no vintages)."""
    if not points:
        return 0
    fetched_at = as_utc(fetched_at or utc_now())
    table = Observation.__table__
    rows = [
        {
            "series_id": series_id,
            "ts_utc": as_utc(p["ts_utc"]),
            "value": float(p["value"]),
            "fetched_at": fetched_at,
        }
        for p in points
    ]
    for i in range(0, len(rows), UPSERT_CHUNK):
        stmt = sqlite_insert(table).values(rows[i : i + UPSERT_CHUNK])
        stmt = stmt.on_conflict_do_update(
            index_elements=["series_id", "ts_utc"],
            set_={"value": stmt.excluded.value, "fetched_at": stmt.excluded.fetched_at},
        )
        session.exec(stmt)
    session.flush()
    return len(rows)


def rebuild_rollups(
    session: Session,
    series_id: str,
    touched: list[datetime] | None = None,
) -> int:
    """Recompute DailyRollup for the local dates touched by `touched` (all dates if None)."""
    series = session.get(Series, series_id)
    if not series or series.frequency != "hourly" or not series.local_tz:
        return 0
    tz = series.local_tz

    if touched is None:
        obs = list(session.exec(select(Observation).where(Observation.series_id == series_id)))
        session.exec(delete(DailyRollup).where(col(DailyRollup.series_id) == series_id))
    else:
        dates = sorted({local_date_of(t, tz) for t in touched})
        if not dates:
            return 0
        start, _ = utc_bounds_of_local_date(dates[0], tz)
        _, end = utc_bounds_of_local_date(dates[-1], tz)
        obs = [
            o
            for o in session.exec(
                select(Observation).where(
                    Observation.series_id == series_id,
                    Observation.ts_utc >= start,
                    Observation.ts_utc < end,
                )
            )
            if local_date_of(o.ts_utc, tz) in set(dates)
        ]
        session.exec(
            delete(DailyRollup).where(
                col(DailyRollup.series_id) == series_id,
                col(DailyRollup.local_date).in_(dates),
            )
        )
    session.flush()
    rows = rollup_hourly(series_id, tz, obs)
    session.add_all(rows)
    session.flush()
    return len(rows)


def start_refresh(session: Session, source: str) -> RefreshRun:
    """Committed immediately, so a later rollback of the job's data never loses the run row."""
    run = RefreshRun(source=source, started_at=utc_now(), success=False)
    session.add(run)
    session.commit()
    return run


def finish_refresh(
    session: Session,
    run: RefreshRun,
    *,
    success: bool,
    rows: int = 0,
    error: str | None = None,
    **fields,
) -> None:
    run.finished_at = utc_now()
    run.success = success
    run.rows_upserted = rows
    run.error = SECRET_PARAM.sub(r"\1***", error)[:800] if error else None
    for key, value in fields.items():
        setattr(run, key, value)
    session.add(run)
    session.flush()


def latest_observation(session: Session, series_id: str) -> Observation | None:
    return session.exec(
        select(Observation)
        .where(Observation.series_id == series_id)
        .order_by(col(Observation.ts_utc).desc())
    ).first()


def earliest_observation(session: Session, series_id: str) -> Observation | None:
    return session.exec(
        select(Observation)
        .where(Observation.series_id == series_id)
        .order_by(col(Observation.ts_utc))
    ).first()


def history(session: Session, series_id: str, since: datetime | None = None) -> list[tuple[datetime, float]]:
    q = select(Observation.ts_utc, Observation.value).where(Observation.series_id == series_id)
    if since is not None:
        q = q.where(Observation.ts_utc >= since)
    return [(as_utc(t), v) for t, v in session.exec(q.order_by(Observation.ts_utc))]


def complete_daily(session: Session, series_id: str) -> list[DailyRollup]:
    return list(
        session.exec(
            select(DailyRollup)
            .where(DailyRollup.series_id == series_id, DailyRollup.quality == "complete")
            .order_by(DailyRollup.local_date)
        )
    )
