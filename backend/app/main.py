"""Read-only API. Ingestion runs only in the scheduler process (python -m app.scheduler)."""

from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta

from fastapi import FastAPI, HTTPException, Query
from sqlmodel import Session, col, select

from app.catalog import ids_where
from app.db import init_db, session_scope
from app.downsample import min_max_buckets
from app.forecast import DEMAND_SERIES, PRICE_SERIES, specs_for
from app.ingest import complete_daily, history, latest_observation, seed_series
from app.insights import current_insights
from app.jobs import refresh_source_for
from app.models import DailyRollup, Forecast, Insight, ModelEval, RefreshRun, Series
from app.rollup import local_date_of, prior_complete_week_change
from app.storage_band import band_history, five_year_band
from app.timeutil import local_midnight_utc, utc_now

US48_TZ = "America/New_York"
DISCLAIMER = (
    "Statistical extrapolations for context, not trading or operational advice. "
    "Nothing here claims to beat markets."
)
PRICE_NOTE = (
    "Oil and gas prices behave close to a random walk, so the naive model (last value) "
    "is the default and often wins; the challenger is shown so you can see when it doesn't. "
    "Naive 80% bands are empirical quantiles of historical h-step log returns."
)
DEMAND_NOTE = (
    "No weather inputs yet: beyond a few days, demand forecasts are mostly climatology "
    "(same weekday, recent level). Only complete local days are used."
)
DF_NOTE = (
    "EIA DF is the grid operators' own day-ahead forecast. It is compared only at a "
    "1-day horizon, labeled operator day-ahead — never beside a multi-day path."
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with session_scope() as session:
        seed_series(session)
    yield


app = FastAPI(title="EnergySignal", version="0.2.0", lifespan=lifespan)


def _iso(dt: datetime | date | None) -> str | None:
    return dt.isoformat() if dt else None


def _lag_hours(ts: datetime | None) -> float | None:
    return round((utc_now() - ts).total_seconds() / 3600, 1) if ts else None


def _meta(s: Series) -> dict:
    return {
        "id": s.id,
        "title": s.title,
        "unit": s.unit,
        "frequency": s.frequency,
        "region": s.region,
        "source": s.source,
        "source_code": s.source_code,
        "license": s.license,
        "attribution": s.attribution,
        "expected_lag": s.expected_lag,
        "local_tz": s.local_tz,
        "category": s.category,
    }


def _series(session: Session, series_id: str) -> Series:
    s = session.get(Series, series_id)
    if not s:
        raise HTTPException(404, f"unknown series {series_id}")
    return s


def _latest(session: Session, series_id: str) -> dict | None:
    s = _series(session, series_id)
    row = latest_observation(session, series_id)
    if not row:
        return {**_meta(s), "value": None, "as_of": None}
    prev = history(session, series_id, since=row.ts_utc - timedelta(days=45))
    prior = prev[-2][1] if len(prev) >= 2 else None
    return {
        **_meta(s),
        "value": row.value,
        "prior_value": prior,
        "as_of": _iso(row.ts_utc),
        "data_lag_hours": _lag_hours(row.ts_utc),
        "fetched_at": _iso(row.fetched_at),
    }


def _is_demo(session: Session) -> bool:
    real = session.exec(
        select(RefreshRun.id).where(RefreshRun.source != "demo", RefreshRun.rows_upserted > 0)
    ).first()
    demo = session.exec(select(RefreshRun.id).where(RefreshRun.source == "demo")).first()
    return bool(demo and not real)


def _insight_json(r: Insight) -> dict:
    return {
        "rule_id": r.rule_id,
        "series_id": r.series_id,
        "headline": r.headline,
        "rank": r.rank,
        "state": r.state,
        "as_of": _iso(r.as_of_ts),
        "issued_at": _iso(r.issued_at),
        "inputs": r.inputs_json,
    }


def _rollup_json(r: DailyRollup) -> dict:
    return {
        "date": r.local_date.isoformat(),
        "total": r.total,
        "peak": r.peak,
        "hour_count": r.hour_count,
        "expected_hours": r.expected_hours,
        "quality": r.quality,
        "dst_flag": r.dst_flag,
    }


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/overview")
def overview() -> dict:
    with session_scope() as session:
        rollups = list(
            session.exec(select(DailyRollup).where(DailyRollup.series_id == "eia-us48-demand"))
        )
        ranked = current_insights(session)
        return {
            "demo": _is_demo(session),
            "prices": [_latest(session, sid) for sid in ("eia-wti", "eia-brent", "eia-henry-hub")],
            "retail": [_latest(session, sid) for sid in ("eia-gasoline", "eia-diesel")],
            "demand_week": prior_complete_week_change(rollups),
            "demand_latest_day": next(
                (_rollup_json(r) for r in sorted(rollups, key=lambda r: r.local_date, reverse=True)
                 if r.quality == "complete"),
                None,
            ),
            "us48_day_convention": US48_TZ,
            "headline": _insight_json(ranked[0]) if ranked else None,
            "insights": [_insight_json(r) for r in ranked[1:6]],
        }


@app.get("/api/series")
def list_series() -> list[dict]:
    with session_scope() as session:
        return [_meta(s) for s in session.exec(select(Series))]


@app.get("/api/series/{series_id}/observations")
def series_observations(series_id: str, days: int = 365, max_points: int = 800) -> dict:
    with session_scope() as session:
        s = _series(session, series_id)
        pts = history(session, series_id, since=utc_now() - timedelta(days=days))
        if s.frequency == "hourly":
            points = min_max_buckets(pts, max_points)
            downsample = "min_max"
        else:
            points = [{"t": _iso(t), "value": v} for t, v in pts]
            downsample = None
        return {"series": _meta(s), "downsample": downsample, "points": points}


@app.get("/api/electricity/us48")
def electricity_us48(days: int = Query(14, ge=2, le=400)) -> dict:
    with session_scope() as session:
        since = utc_now() - timedelta(days=days)
        demand = history(session, "eia-us48-demand", since=since)
        df = history(session, "eia-us48-df", since=since)
        rollups = list(
            session.exec(
                select(DailyRollup)
                .where(DailyRollup.series_id == "eia-us48-demand")
                .order_by(col(DailyRollup.local_date).desc())
                .limit(max(days, 14))
            )
        )[::-1]
        fuels = []
        for sid in ids_where(category="fuel_mix"):
            s = session.get(Series, sid)
            days_done = complete_daily(session, sid)[-days:]
            fuels.append(
                {
                    "id": sid,
                    "fuel": s.title.split(": ", 1)[-1],
                    "days": [{"date": r.local_date.isoformat(), "total": r.total} for r in days_done],
                }
            )
        return {
            "local_tz": US48_TZ,
            "note": "US48 local day = America/New_York. Partial local days are shown hatched and excluded from totals, KPIs, insights and forecasts.",
            "downsample": "min_max",
            "demand": min_max_buckets(demand, 900),
            "day_ahead": min_max_buckets(df, 900),
            "daily": [_rollup_json(r) for r in rollups],
            "fuel_mix": fuels,
            "latest": _latest(session, "eia-us48-demand"),
            "attribution": "U.S. Energy Information Administration",
        }


@app.get("/api/electricity/global")
def electricity_global() -> dict:
    with session_scope() as session:
        out = []
        for sid in ids_where(category="global_demand"):
            s = session.get(Series, sid)
            out.append(
                {**_meta(s), "points": [{"t": _iso(t), "value": v} for t, v in history(session, sid)]}
            )
        return {"series": out, "attribution": "Ember, CC BY 4.0"}


@app.get("/api/fuels")
def fuels(days: int = Query(730, ge=30, le=3650)) -> dict:
    with session_scope() as session:
        since = utc_now() - timedelta(days=days)

        def pack(sid: str) -> dict:
            return {
                **_latest(session, sid),
                "points": [{"t": _iso(t), "value": v} for t, v in history(session, sid, since=since)],
            }

        return {
            "spot": [pack(sid) for sid in ("eia-wti", "eia-brent", "eia-henry-hub")],
            "retail": [pack(sid) for sid in ("eia-gasoline", "eia-diesel")],
            "global": [pack(sid) for sid in ids_where(category="global_price")],
            "insights": [
                _insight_json(r) for r in current_insights(session) if r.rule_id != "demand_week"
            ],
        }


@app.get("/api/fuels/storage")
def storage(region: str = "eia-storage-r48") -> dict:
    with session_scope() as session:
        s = _series(session, region)
        weekly = [(t.date(), v) for t, v in history(session, region)]
        regions = [
            {"id": r.id, "region": r.region}
            for r in session.exec(select(Series).where(Series.category == "storage"))
        ]
        if not weekly:
            return {"series": _meta(s), "regions": regions, "band": None, "history": []}
        return {
            "series": _meta(s),
            "regions": regions,
            "band": five_year_band(weekly, weekly[-1][0]),
            "history": band_history(weekly, 104),
            "method": "Range and mean of the same ISO week over the prior 5 years; week 53 uses week 52 in years without one.",
        }


@app.get("/api/insights")
def insights() -> list[dict]:
    with session_scope() as session:
        return [_insight_json(r) for r in current_insights(session)]


@app.get("/api/forecasts/options")
def forecast_options() -> list[dict]:
    with session_scope() as session:
        out = []
        for sid in [*DEMAND_SERIES, *PRICE_SERIES]:
            s = session.get(Series, sid)
            for spec in specs_for(session, sid):
                out.append(
                    {
                        "series_id": sid,
                        "title": s.title,
                        "unit": s.unit,
                        "target_kind": spec.target_kind,
                        "models": list(spec.models),
                        "steps": spec.steps,
                        "buckets": spec.buckets,
                    }
                )
        return out


def _actuals(session: Session, series_id: str, target_kind: str, since: datetime | None = None) -> list[tuple[datetime, float]]:
    s = _series(session, series_id)
    if target_kind in ("daily_total", "daily_peak"):
        attr = "total" if target_kind == "daily_total" else "peak"
        return [
            (local_midnight_utc(r.local_date, s.local_tz), getattr(r, attr))
            for r in complete_daily(session, series_id)
            if since is None or local_midnight_utc(r.local_date, s.local_tz) >= since
        ]
    return history(session, series_id, since=since)


def _eval_json(e: ModelEval) -> dict:
    return {
        "model": e.model_version.split(":", 1)[-1],
        "model_version": e.model_version,
        "horizon_bucket": e.horizon_bucket,
        "mase": e.mase,
        "mase_lag24": e.mase_lag24,
        "mae": e.mae,
        "coverage": e.coverage,
        "interval_level": e.interval_level,
        "n_origins": e.n_origins,
        "backtest_start": _iso(e.backtest_start),
        "backtest_end": _iso(e.backtest_end),
        "evaluated_at": _iso(e.evaluated_at),
    }


@app.get("/api/forecasts")
def forecasts(series_id: str = "eia-us48-demand", target_kind: str = "daily_total") -> dict:
    with session_scope() as session:
        s = _series(session, series_id)
        issued_at = session.exec(
            select(Forecast.issued_at)
            .where(Forecast.series_id == series_id, Forecast.target_kind == target_kind)
            .order_by(col(Forecast.issued_at).desc())
        ).first()
        models: dict[str, list[dict]] = {}
        window_end = None
        if issued_at:
            for r in session.exec(
                select(Forecast)
                .where(
                    Forecast.series_id == series_id,
                    Forecast.target_kind == target_kind,
                    Forecast.issued_at == issued_at,
                )
                .order_by(Forecast.model, Forecast.horizon)
            ):
                window_end = r.training_window_end
                models.setdefault(r.model, []).append(
                    {
                        "horizon": r.horizon,
                        "target": _iso(r.target_ts_utc),
                        "point": r.point,
                        "lo": r.interval_lo,
                        "hi": r.interval_hi,
                        "level": r.interval_level,
                    }
                )
        lookback = {"hourly": 7, "daily_total": 60, "daily_peak": 60, "daily": 180, "weekly": 730}[target_kind]
        actual_since = (window_end or utc_now()) - timedelta(days=lookback)
        actuals = [{"t": _iso(t), "value": v} for t, v in _actuals(session, series_id, target_kind, actual_since)]
        evals = [
            _eval_json(e)
            for e in session.exec(
                select(ModelEval).where(
                    ModelEval.series_id == series_id, ModelEval.target_kind == target_kind
                )
            )
        ]
        df = None
        if series_id == "eia-us48-demand" and target_kind == "daily_total":
            nxt = models.get("seasonal_naive", [{}])[0].get("target") if models else None
            df_day = None
            if nxt:
                local = local_date_of(datetime.fromisoformat(nxt), US48_TZ)
                row = session.exec(
                    select(DailyRollup).where(
                        DailyRollup.series_id == "eia-us48-df", DailyRollup.local_date == local
                    )
                ).first()
                df_day = _rollup_json(row) if row else None
            df = {
                "label": "Operator day-ahead (EIA DF), 1-day horizon only",
                "note": DF_NOTE,
                "next_day": df_day,
                "eval": next((e for e in evals if e["model_version"] == "eia_df"), None),
            }
            evals = [e for e in evals if e["model_version"] != "eia_df"]
        return {
            "series": _meta(s),
            "target_kind": target_kind,
            "issued_at": _iso(issued_at),
            "training_window_end": _iso(window_end),
            "models": models,
            "actuals": actuals,
            "evals": evals,
            "df_benchmark": df,
            "disclaimer": DISCLAIMER,
            "note": DEMAND_NOTE if series_id in DEMAND_SERIES else PRICE_NOTE,
        }


@app.get("/api/forecasts/history")
def forecast_history(series_id: str, target_kind: str, horizon: int = 1) -> dict:
    """Past issues at one horizon vs what actually happened (within the 90-day retention)."""
    with session_scope() as session:
        actual = dict(_actuals(session, series_id, target_kind, utc_now() - timedelta(days=120)))
        rows = session.exec(
            select(Forecast)
            .where(
                Forecast.series_id == series_id,
                Forecast.target_kind == target_kind,
                Forecast.horizon == horizon,
            )
            .order_by(Forecast.target_ts_utc)
        )
        out: dict[str, list[dict]] = {}
        for r in rows:
            out.setdefault(r.model, []).append(
                {
                    "issued_at": _iso(r.issued_at),
                    "target": _iso(r.target_ts_utc),
                    "point": r.point,
                    "lo": r.interval_lo,
                    "hi": r.interval_hi,
                    "actual": actual.get(r.target_ts_utc),
                }
            )
        return {"series_id": series_id, "target_kind": target_kind, "horizon": horizon, "models": out}


@app.get("/api/sources")
def sources() -> dict:
    with session_scope() as session:
        runs = list(session.exec(select(RefreshRun).order_by(col(RefreshRun.started_at).desc()).limit(500)))
        items = []
        for s in session.exec(select(Series)):
            last = latest_observation(session, s.id)
            feed = refresh_source_for(s)
            feed_runs = [r for r in runs if r.source == feed and r.finished_at]
            ok = next((r for r in feed_runs if r.success), None)
            fail = next((r for r in feed_runs if not r.success), None)
            items.append(
                {
                    **_meta(s),
                    "route": s.route,
                    "feed": feed,
                    "latest_period": _iso(last.ts_utc) if last else None,
                    "data_lag_hours": _lag_hours(last.ts_utc) if last else None,
                    "last_success": _iso(ok.finished_at) if ok else None,
                    "fetch_staleness_hours": _lag_hours(ok.finished_at) if ok else None,
                    "last_failure": (
                        {"at": _iso(fail.finished_at), "error": fail.error}
                        if fail and (not ok or fail.finished_at > ok.finished_at)
                        else None
                    ),
                }
            )
        return {
            "demo": _is_demo(session),
            "items": items,
            "runs": [
                {
                    "source": r.source,
                    "started_at": _iso(r.started_at),
                    "finished_at": _iso(r.finished_at),
                    "success": r.success,
                    "rows_upserted": r.rows_upserted,
                    "new_period": r.new_period,
                    "error": r.error,
                }
                for r in runs[:40]
            ],
        }
