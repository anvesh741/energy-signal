"""Refresh jobs. Each returns the set of series ids that received a new latest observation."""

from datetime import datetime, timedelta

import httpx
from sqlmodel import Session, col, select

from app.catalog import ids_where
from app.config import settings
from app.eval import run_evaluations
from app.forecast import DEMAND_SERIES, PRICE_SERIES, issue_forecasts
from app.ingest import (
    earliest_observation,
    finish_refresh,
    latest_observation,
    rebuild_rollups,
    seed_series,
    start_refresh,
    upsert_observations,
)
from app.insights import generate_insights
from app.models import RefreshRun, Series
from app.sources import eia, ember, pink_sheet
from app.timeutil import as_utc, utc_now
from app.weekly_window import RELEASES, window_start

REPULL_HOURS = 72
HOURLY_CHUNK = timedelta(days=30)
MAX_BACKFILL_CHUNKS_PER_RUN = 14
# demand + DF need a year for daily backtests; the rest only feed recent charts
HOURLY_BACKFILL_DAYS = {"eia-us48-demand": 400, "eia-us48-df": 400}
HOURLY_BACKFILL_DEFAULT = 45
DAILY_PRICE_BACKFILL = timedelta(days=5 * 365)
WEEKLY_BACKFILL = {"retail": timedelta(days=5 * 365), "storage": timedelta(days=6 * 365 + 30)}
WEEKLY_SERIES = {"retail": ids_where(category="retail"), "storage": ids_where(category="storage")}


def refresh_source_for(series: Series) -> str:
    """Which RefreshRun.source feeds a series (for the Sources page)."""
    if series.source == "eia":
        if series.frequency == "hourly":
            return "eia-hourly"
        if series.category in WEEKLY_SERIES:
            return f"eia-weekly-{series.category}"
        return "eia-prices"
    return {"worldbank": "pink-sheet"}.get(series.source, series.source)


def _hour(ts: datetime) -> str:
    return as_utc(ts).strftime("%Y-%m-%dT%H")


def _advanced(before, after) -> bool:
    return after is not None and (before is None or after.ts_utc > before.ts_utc)


def _fetch(client: httpx.Client, series: Series, freq: str, start: str, end: str | None = None) -> list[dict]:
    return eia.fetch_series(
        client, settings.eia_api_key, series.route, series.source_code, freq, start=start, end=end
    )


def refresh_eia_hourly(session: Session, client: httpx.Client) -> set[str]:
    """Trailing 72h re-pull (BAs revise), then resumable backfill in 30-day chunks."""
    run = start_refresh(session, "eia-hourly")
    changed, problems, total = set(), [], 0
    now = utc_now()
    for sid in ids_where(source="eia", frequency="hourly"):
        series = session.get(Series, sid)
        try:
            before = latest_observation(session, sid)
            start = before.ts_utc - timedelta(hours=REPULL_HOURS) if before else now - HOURLY_CHUNK
            rows = _fetch(client, series, "hourly", _hour(start))
            touched = [r["ts_utc"] for r in rows]
            total += upsert_observations(session, sid, rows)

            target = now - timedelta(days=HOURLY_BACKFILL_DAYS.get(sid, HOURLY_BACKFILL_DEFAULT))
            for _ in range(MAX_BACKFILL_CHUNKS_PER_RUN):
                earliest = earliest_observation(session, sid)
                if earliest is None or earliest.ts_utc <= target + timedelta(hours=1):
                    break
                end = earliest.ts_utc - timedelta(hours=1)
                rows = _fetch(client, series, "hourly", _hour(max(target, end - HOURLY_CHUNK)), _hour(end))
                if not rows:
                    break
                touched += [r["ts_utc"] for r in rows]
                total += upsert_observations(session, sid, rows)
                session.commit()  # resumable: a crash keeps finished chunks

            rebuild_rollups(session, sid, touched)
            session.commit()
            if _advanced(before, latest_observation(session, sid)):
                changed.add(sid)
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            problems.append(f"{sid}: {exc}")
    finish_refresh(session, run, success=not problems, rows=total, error="; ".join(problems) or None)
    return changed


def refresh_eia_prices(session: Session, client: httpx.Client) -> set[str]:
    """Daily spot prices. Values are daily but usually land in weekly batches, so most runs no-op."""
    run = start_refresh(session, "eia-prices")
    changed, problems, total = set(), [], 0
    for sid in ids_where(source="eia", frequency="daily"):
        series = session.get(Series, sid)
        try:
            before = latest_observation(session, sid)
            start = before.ts_utc - timedelta(days=30) if before else utc_now() - DAILY_PRICE_BACKFILL
            total += upsert_observations(session, sid, _fetch(client, series, "daily", start.strftime("%Y-%m-%d")))
            session.commit()
            if _advanced(before, latest_observation(session, sid)):
                changed.add(sid)
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            problems.append(f"{sid}: {exc}")
    finish_refresh(session, run, success=not problems, rows=total, error="; ".join(problems) or None)
    return changed


def refresh_eia_weekly(session: Session, client: httpx.Client, release: str, force: bool = False) -> set[str]:
    """Poll inside the release window until a new period appears, then stop until next week."""
    source = f"eia-weekly-{release}"
    opened = window_start(utc_now(), RELEASES[release])
    if not force:
        if opened is None:
            return set()
        done = session.exec(
            select(RefreshRun.id).where(
                RefreshRun.source == source,
                RefreshRun.new_period == True,  # noqa: E712
                RefreshRun.started_at >= opened,
            )
        ).first()
        if done:
            return set()
    run = start_refresh(session, source)
    changed, problems, total = set(), [], 0
    for sid in WEEKLY_SERIES[release]:
        series = session.get(Series, sid)
        try:
            before = latest_observation(session, sid)
            start = before.ts_utc - timedelta(weeks=8) if before else utc_now() - WEEKLY_BACKFILL[release]
            rows = _fetch(client, series, "weekly", start.strftime("%Y-%m-%d"))
            if before is None and not rows:
                raise eia.EiaError(f"no rows for {series.source_code}; check the series id in the EIA browser")
            total += upsert_observations(session, sid, rows)
            session.commit()
            if _advanced(before, latest_observation(session, sid)):
                changed.add(sid)
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            problems.append(f"{sid}: {exc}")
    finish_refresh(
        session, run, success=not problems, rows=total,
        error="; ".join(problems) or None, new_period=bool(changed),
    )
    return changed


def refresh_ember(session: Session, client: httpx.Client) -> set[str]:
    run = start_refresh(session, "ember")
    changed, problems, total = set(), [], 0
    for sid in ids_where(source="ember"):
        series = session.get(Series, sid)
        try:
            before = latest_observation(session, sid)
            iso3 = series.source_code.split("|", 1)[0]
            total += upsert_observations(session, sid, ember.fetch_monthly_demand(client, settings.ember_api_key, iso3))
            session.commit()
            if _advanced(before, latest_observation(session, sid)):
                changed.add(sid)
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            problems.append(f"{sid}: {exc}")
    finish_refresh(session, run, success=not problems, rows=total, error="; ".join(problems) or None)
    return changed


def refresh_pink_sheet(session: Session, client: httpx.Client) -> set[str]:
    """ETag / Last-Modified when present, content hash always. Parse failure = failed run, no writes."""
    run = start_refresh(session, "pink-sheet")
    last = session.exec(
        select(RefreshRun)
        .where(RefreshRun.source == "pink-sheet", RefreshRun.success == True)  # noqa: E712
        .order_by(col(RefreshRun.finished_at).desc())
    ).first()
    try:
        content, etag, last_mod = pink_sheet.fetch_workbook(
            client,
            settings.pink_sheet_url,
            etag=last.etag if last else None,
            last_modified=last.last_modified if last else None,
        )
        if content is None:  # 304
            finish_refresh(session, run, success=True, etag=etag, last_modified=last_mod,
                           content_hash=last.content_hash if last else None)
            return set()
        digest = pink_sheet.content_hash(content)
        if last and last.content_hash == digest:
            finish_refresh(session, run, success=True, etag=etag, last_modified=last_mod, content_hash=digest)
            return set()
        columns = {sid: session.get(Series, sid).source_code for sid in ids_where(source="worldbank")}
        parsed = pink_sheet.parse_workbook(content, columns)  # raises before any write
        changed, total = set(), 0
        for sid, points in parsed.items():
            before = latest_observation(session, sid)
            total += upsert_observations(session, sid, points)
            if _advanced(before, latest_observation(session, sid)):
                changed.add(sid)
        missing = sorted(set(columns) - set(parsed))
        finish_refresh(
            session, run, success=not missing, rows=total,
            error=f"columns missing: {', '.join(columns[m] for m in missing)}" if missing else None,
            etag=etag, last_modified=last_mod, content_hash=digest,
        )
        return changed
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        finish_refresh(session, run, success=False, error=str(exc))
        return set()


def post_refresh_derived(session: Session, changed: set[str]) -> None:
    """Forecasts (gated: once per new complete day / new observation), their evals, insights."""
    for sid in [*DEMAND_SERIES, *PRICE_SERIES]:
        if sid in changed and issue_forecasts(session, sid):
            run_evaluations(session, [sid])
    generate_insights(session)
    session.commit()


def run_all(session: Session, *, weekly_force: bool = False) -> set[str]:
    seed_series(session)
    session.commit()
    changed: set[str] = set()
    with httpx.Client() as client:
        if settings.eia_api_key:
            changed |= refresh_eia_hourly(session, client)
            changed |= refresh_eia_prices(session, client)
            for release in RELEASES:
                changed |= refresh_eia_weekly(session, client, release, force=weekly_force)
        if settings.ember_api_key:
            changed |= refresh_ember(session, client)
        changed |= refresh_pink_sheet(session, client)
    post_refresh_derived(session, changed)
    return changed
