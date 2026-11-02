"""Cadence-aware statistical forecasts.

Every model is a pure function  fn(train, targets, steps) -> points  where `train` is
[(t, v), ...] up to the origin, `targets` are the target timestamps and `steps` the
horizon in observation steps. The same functions drive issuance (here) and the
rolling-origin backtest (eval.py), so what we evaluate is what we publish.

Intervals: for every model, the 80% band is  point * exp(q10, q90)  of that model's own
historical log errors log(actual / point) at the same step, taken from rolling origins.
For the naive price model that is exactly the empirical quantiles of historical h-step
log returns. No parametric (SARIMAX) standard errors.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable
from zoneinfo import ZoneInfo

import numpy as np
from sqlalchemy import delete
from sqlmodel import Session, col, select

from app.config import settings
from app.ingest import complete_daily, history
from app.models import Forecast, Series
from app.rollup import utc_bounds_of_local_date
from app.timeutil import add_business_days, local_midnight_utc, utc_now

MODEL_VERSION = "v1.1"
LEVEL = 0.8
MIN_BAND_SAMPLES = 20

Point = tuple[datetime, float]
Forecaster = Callable[[list[Point], list[datetime], list[int]], list[float]]


# ---------------------------------------------------------------- models


def naive(train: list[Point], targets: list[datetime], steps: list[int]) -> list[float]:
    return [train[-1][1]] * len(targets)


def seasonal_naive(season: timedelta) -> Forecaster:
    """Value one (or more) whole seasons before each target, never from the future."""

    def fn(train, targets, steps):
        lookup = dict(train)
        last_t, last_v = train[-1]
        out = []
        for t in targets:
            k = max(1, math.ceil((t - last_t) / season))
            value = None
            for kk in range(k, k + 4):  # skip gaps (e.g. an excluded partial day)
                value = lookup.get(t - kk * season)
                if value is not None:
                    break
            out.append(last_v if value is None else value)
        return out

    return fn


def seasonal_mean(season: timedelta, n: int = 4) -> Forecaster:
    """Mean of the n most recent same-season values (e.g. last 4 same weekdays)."""

    def fn(train, targets, steps):
        lookup = dict(train)
        last_t, last_v = train[-1]
        out = []
        for t in targets:
            k = max(1, math.ceil((t - last_t) / season))
            vals = [lookup.get(t - kk * season) for kk in range(k, k + n + 2)]
            vals = [v for v in vals if v is not None][:n]
            out.append(sum(vals) / len(vals) if vals else last_v)
        return out

    return fn


def logret_ar(window: int = 500) -> Forecaster:
    """AR(1) on 1-step log returns over a trailing window, iterated `step` times."""

    def fn(train, targets, steps):
        values = [v for _, v in train[-(window + 1) :]]
        rets = [
            math.log(b / a) for a, b in zip(values, values[1:]) if a > 0 and b > 0
        ]
        last = values[-1]
        if len(rets) < 20 or last <= 0:
            return [last] * len(steps)
        x, y = np.array(rets[:-1]), np.array(rets[1:])
        var = float(np.var(x)) or 1e-12
        phi = float(np.clip(np.mean((x - x.mean()) * (y - y.mean())) / var, -0.99, 0.99))
        intercept = float(y.mean() - phi * x.mean())
        out = []
        for step in steps:
            r, total = rets[-1], 0.0
            for _ in range(step):
                r = intercept + phi * r
                total += r
            out.append(last * math.exp(total))
        return out

    return fn


def _local_hours(ts: list[datetime], tz: ZoneInfo) -> np.ndarray:
    """Hours since epoch on the local wall clock, so daily/weekly cycles follow local time."""
    return np.array(
        [(t.timestamp() + t.astimezone(tz).utcoffset().total_seconds()) / 3600 for t in ts]
    )


def _fourier_design(h: np.ndarray, h0: float) -> np.ndarray:
    cols = [np.ones_like(h), (h - h0) / 168.0]
    for period, k_max in ((24.0, 4), (168.0, 3)):
        for k in range(1, k_max + 1):
            angle = 2 * math.pi * k * h / period
            cols += [np.sin(angle), np.cos(angle)]
    return np.column_stack(cols)


def fourier_ar(tz_name: str, window_days: int = 28) -> Forecaster:
    """Daily + weekly Fourier terms and a linear trend (OLS), with AR(1) residual decay."""
    tz = ZoneInfo(tz_name)

    def fn(train, targets, steps):
        recent = train[-window_days * 24 :]
        if len(recent) < 24 * 7:
            return seasonal_naive(timedelta(hours=168))(train, targets, steps)
        h = _local_hours([t for t, _ in recent], tz)
        y = np.array([v for _, v in recent])
        X = _fourier_design(h, h[0])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ beta
        denom = float(np.dot(resid[:-1], resid[:-1])) or 1e-12
        phi = float(np.clip(np.dot(resid[:-1], resid[1:]) / denom, -0.99, 0.99))
        Xf = _fourier_design(_local_hours(targets, tz), h[0])
        last_t = train[-1][0]
        hours_ahead = np.array([(t - last_t).total_seconds() / 3600 for t in targets])
        return list(Xf @ beta + resid[-1] * phi ** np.maximum(hours_ahead, 1))

    return fn


# ---------------------------------------------------------------- bands


def rolling_log_errors(
    hist: list[Point],
    fn: Forecaster,
    steps: list[int],
    *,
    min_train: int,
    stride: int,
    max_origins: int,
) -> dict[int, list[float]]:
    """log(actual/point) per step from the most recent `max_origins` origins."""
    errors: dict[int, list[float]] = {s: [] for s in steps}
    last_origin = len(hist) - 1 - min(steps)
    origins = list(range(last_origin, min_train - 2, -stride))[:max_origins]
    for o in origins:
        usable = [s for s in steps if o + s < len(hist)]
        if not usable:
            continue
        targets = [hist[o + s][0] for s in usable]
        preds = fn(hist[: o + 1], targets, usable)
        for s, p in zip(usable, preds):
            actual = hist[o + s][1]
            if p > 0 and actual > 0:
                errors[s].append(math.log(actual / p))
    return errors


def band(point: float, log_errors: list[float], level: float = LEVEL) -> tuple[float | None, float | None]:
    if len(log_errors) < MIN_BAND_SAMPLES or point <= 0:
        return None, None
    tail = (1 - level) / 2
    lo, hi = np.quantile(log_errors, [tail, 1 - tail])
    return point * math.exp(float(lo)), point * math.exp(float(hi))


# ---------------------------------------------------------------- specs


@dataclass
class ForecastSpec:
    series_id: str
    target_kind: str
    models: dict[str, Forecaster]
    steps: list[int]
    # horizon bucket label -> steps (used by eval)
    buckets: dict[str, list[int]]
    # loads [(t, v)]; daily kinds use date-at-00:00-UTC as model time
    load: Callable[[Session], list[Point]]
    # (last model time, step) -> model-time target
    next_target: Callable[[datetime, int], datetime]
    # model time -> stored target_ts_utc
    to_utc: Callable[[datetime], datetime] = lambda t: t
    min_train: int = 30
    stride: int = 1
    max_origins: int = 365
    eval_stride: int = 1
    eval_max_origins: int | None = None  # defaults to max_origins
    mase_season: int | None = None
    secondary_season: int | None = None
    meta: dict = field(default_factory=dict)


def _daily_loader(series_id: str, attr: str) -> Callable[[Session], list[Point]]:
    def load(session: Session) -> list[Point]:
        return [
            (datetime(r.local_date.year, r.local_date.month, r.local_date.day, tzinfo=timezone.utc), getattr(r, attr))
            for r in complete_daily(session, series_id)
        ]

    return load


def _hourly_loader(series_id: str, tz: str, days: int = 120) -> Callable[[Session], list[Point]]:
    """Hours through the end of the last complete local day, so hourly issues are gated
    once per day like the daily ones and never train on a partial day."""

    def load(session: Session) -> list[Point]:
        days_done = complete_daily(session, series_id)
        if not days_done:
            return []
        _, end = utc_bounds_of_local_date(days_done[-1].local_date, tz)
        since = end - timedelta(days=days)
        return [p for p in history(session, series_id, since=since) if p[0] < end]

    return load


def demand_specs(series_id: str, tz: str) -> list[ForecastSpec]:
    day = timedelta(days=1)
    week = timedelta(days=7)
    daily_models = {
        "naive": naive,
        "seasonal_naive": seasonal_naive(week),
        "seasonal_mean4": seasonal_mean(week, 4),
    }
    daily_buckets = {
        "1d": [1],
        "2-7d": list(range(2, 8)),
        "8-14d": list(range(8, 15)),
        "15-30d": list(range(15, 31)),
    }
    to_utc = lambda t: local_midnight_utc(t.date(), tz)  # noqa: E731
    specs = [
        ForecastSpec(
            series_id=series_id,
            target_kind=kind,
            models=daily_models,
            steps=list(range(1, 31)),
            buckets=daily_buckets,
            load=_daily_loader(series_id, attr),
            next_target=lambda t, s: t + s * day,
            to_utc=to_utc,
            min_train=35,
            mase_season=7,
        )
        for kind, attr in (("daily_total", "total"), ("daily_peak", "peak"))
    ]
    specs.append(
        ForecastSpec(
            series_id=series_id,
            target_kind="hourly",
            models={
                "seasonal_naive": seasonal_naive(timedelta(hours=168)),
                "fourier_ar": fourier_ar(tz),
            },
            steps=list(range(1, 169)),
            buckets={
                "1-24h": list(range(1, 25)),
                "25-72h": list(range(25, 73)),
                "73-168h": list(range(73, 169)),
            },
            load=_hourly_loader(series_id, tz),
            next_target=lambda t, s: t + timedelta(hours=s),
            min_train=24 * 21,
            stride=24,
            max_origins=45,
            eval_stride=24,
            eval_max_origins=120,
            mase_season=168,
            secondary_season=24,
        )
    )
    return specs


def price_spec(series: Series) -> ForecastSpec:
    load = lambda session: history(session, series.id)  # noqa: E731
    models = {"naive": naive, "logret_ar": logret_ar()}
    if series.frequency == "weekly":
        return ForecastSpec(
            series_id=series.id,
            target_kind="weekly",
            models=models,
            steps=[1, 2, 4],
            buckets={"1w": [1], "2w": [2], "4w": [4]},
            load=load,
            next_target=lambda t, s: t + timedelta(days=7 * s),
            min_train=52,
            max_origins=260,
            mase_season=None,  # prices: MASE vs plain naive
        )
    return ForecastSpec(
        series_id=series.id,
        target_kind="daily",
        models=models,
        steps=[1, 5, 10, 20],
        buckets={"1d": [1], "1w": [5], "2w": [10], "1m": [20]},
        load=load,
        next_target=add_business_days,
        min_train=60,
        max_origins=750,
        mase_season=None,
    )


DEMAND_SERIES = {"eia-us48-demand": "America/New_York"}
PRICE_SERIES = ["eia-wti", "eia-brent", "eia-henry-hub", "eia-gasoline", "eia-diesel"]


def specs_for(session: Session, series_id: str) -> list[ForecastSpec]:
    if series_id in DEMAND_SERIES:
        return demand_specs(series_id, DEMAND_SERIES[series_id])
    series = session.get(Series, series_id)
    if series and series_id in PRICE_SERIES:
        return [price_spec(series)]
    return []


# ---------------------------------------------------------------- issuance


def build_issue(spec: ForecastSpec, hist: list[Point], issued_at: datetime) -> list[Forecast]:
    last_t = hist[-1][0]
    targets = [spec.next_target(last_t, s) for s in spec.steps]
    rows: list[Forecast] = []
    for name, fn in spec.models.items():
        points = fn(hist, targets, spec.steps)
        errors = rolling_log_errors(
            hist, fn, spec.steps,
            min_train=spec.min_train, stride=spec.stride, max_origins=spec.max_origins,
        )
        for step, target, point in zip(spec.steps, targets, points):
            lo, hi = band(point, errors[step])
            rows.append(
                Forecast(
                    series_id=spec.series_id,
                    model=name,
                    model_version=MODEL_VERSION,
                    issued_at=issued_at,
                    target_ts_utc=spec.to_utc(target),
                    horizon=step,
                    target_kind=spec.target_kind,
                    point=float(point),
                    interval_lo=lo,
                    interval_hi=hi,
                    interval_level=LEVEL,
                    training_window_start=spec.to_utc(hist[0][0]),
                    training_window_end=spec.to_utc(last_t),
                )
            )
    return rows


def _already_issued(session: Session, spec: ForecastSpec, window_end: datetime) -> bool:
    return (
        session.exec(
            select(Forecast.id).where(
                Forecast.series_id == spec.series_id,
                Forecast.target_kind == spec.target_kind,
                Forecast.training_window_end == window_end,
            )
        ).first()
        is not None
    )


def issue_forecasts(session: Session, series_id: str, issued_at: datetime | None = None) -> int:
    """Issue once per new training-window end (demand: once per new complete local day;
    prices: once per new observation). Re-running without new data is a no-op."""
    issued_at = issued_at or utc_now()
    total = 0
    for spec in specs_for(session, series_id):
        hist = spec.load(session)
        if len(hist) < spec.min_train + max(spec.steps[:1]):
            continue
        if _already_issued(session, spec, spec.to_utc(hist[-1][0])):
            continue
        rows = build_issue(spec, hist, issued_at)
        session.add_all(rows)
        total += len(rows)
    session.flush()
    prune_forecasts(session)
    return total


def prune_forecasts(session: Session, keep_days: int | None = None) -> None:
    cutoff = utc_now() - timedelta(days=keep_days or settings.forecast_retention_days)
    session.exec(delete(Forecast).where(col(Forecast.issued_at) < cutoff))


def latest_issue(session: Session, series_id: str, target_kind: str) -> datetime | None:
    return session.exec(
        select(Forecast.issued_at)
        .where(Forecast.series_id == series_id, Forecast.target_kind == target_kind)
        .order_by(col(Forecast.issued_at).desc())
    ).first()
