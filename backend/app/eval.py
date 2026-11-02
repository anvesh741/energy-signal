"""Rolling-origin backtests -> ModelEval (MASE, MAE, 80% coverage, n_origins).

At each origin the model sees only data up to that origin, and its 80% band is built
only from errors that had already been realized by then — so coverage is out-of-sample.
An origin counts toward a bucket only once a band exists, so n_origins applies to
every metric on the row. Coverage from ~10 origins is noise; the UI shows n_origins.
"""

from __future__ import annotations

import math
from datetime import datetime

from sqlmodel import Session, select

from app.forecast import (
    DEMAND_SERIES,
    MODEL_VERSION,
    PRICE_SERIES,
    ForecastSpec,
    Point,
    band,
    specs_for,
)
from app.ingest import complete_daily
from app.models import ModelEval, Series
from app.timeutil import local_midnight_utc, utc_now

ERROR_MEMORY = 200


def origin_indices(
    n: int,
    min_train: int,
    horizon: int,
    stride: int = 1,
    max_origins: int | None = None,
) -> list[int]:
    """Chronological training-end indices (inclusive) that still leave `horizon` points."""
    origins = list(range(min_train - 1, n - horizon, stride))
    return origins[-max_origins:] if max_origins else origins


def mase_scale(values: list[float], season: int | None) -> float | None:
    """In-sample mean absolute seasonal difference (plain lag-1 when season is None)."""
    lag = season or 1
    diffs = [abs(values[i] - values[i - lag]) for i in range(lag, len(values))]
    if not diffs:
        return None
    scale = sum(diffs) / len(diffs)
    return scale or None


def backtest(spec: ForecastSpec, hist: list[Point], model: str) -> dict[str, dict]:
    fn = spec.models[model]
    n = len(hist)
    step_bucket = {s: label for label, steps in spec.buckets.items() for s in steps}
    realized: dict[int, list[tuple[int, float]]] = {s: [] for s in spec.steps}
    acc = {
        label: {"abs": [], "hits": 0, "origins": set(), "first": None, "last": None}
        for label in spec.buckets
    }
    for o in origin_indices(
        n, spec.min_train, min(spec.steps), spec.eval_stride, spec.eval_max_origins or spec.max_origins
    ):
        usable = [s for s in spec.steps if o + s < n]
        preds = fn(hist[: o + 1], [hist[o + s][0] for s in usable], usable)
        for s, p in zip(usable, preds):
            actual = hist[o + s][1]
            prior = [e for idx, e in realized[s] if idx <= o][-ERROR_MEMORY:]
            lo, hi = band(p, prior)
            if lo is not None:
                a = acc[step_bucket[s]]
                a["abs"].append(abs(actual - p))
                a["hits"] += int(lo <= actual <= hi)
                a["origins"].add(o)
                a["first"] = a["first"] or hist[o][0]
                a["last"] = hist[o][0]
            if p > 0 and actual > 0:
                realized[s].append((o + s, math.log(actual / p)))
    return acc


def _upsert_eval(session: Session, **payload) -> ModelEval:
    row = session.exec(
        select(ModelEval).where(
            ModelEval.series_id == payload["series_id"],
            ModelEval.model_version == payload["model_version"],
            ModelEval.target_kind == payload["target_kind"],
            ModelEval.horizon_bucket == payload["horizon_bucket"],
        )
    ).first()
    row = row or ModelEval(**payload)
    for key, value in payload.items():
        setattr(row, key, value)
    session.add(row)
    return row


def evaluate_spec(session: Session, spec: ForecastSpec, now: datetime) -> list[ModelEval]:
    hist = spec.load(session)
    if len(hist) < spec.min_train + max(spec.steps):
        return []
    values = [v for _, v in hist]
    scale = mase_scale(values, spec.mase_season)
    scale2 = mase_scale(values, spec.secondary_season) if spec.secondary_season else None
    out = []
    for model in spec.models:
        for label, a in backtest(spec, hist, model).items():
            if not a["abs"]:
                continue
            mae = sum(a["abs"]) / len(a["abs"])
            out.append(
                _upsert_eval(
                    session,
                    series_id=spec.series_id,
                    model_version=f"{MODEL_VERSION}:{model}",
                    target_kind=spec.target_kind,
                    horizon_bucket=label,
                    mase=mae / scale if scale else None,
                    mase_lag24=mae / scale2 if scale2 else None,
                    mae=mae,
                    coverage=a["hits"] / len(a["abs"]),
                    interval_level=0.8,
                    n_origins=len(a["origins"]),
                    backtest_start=spec.to_utc(a["first"]),
                    backtest_end=spec.to_utc(a["last"]),
                    evaluated_at=now,
                )
            )
    return out


def evaluate_eia_df(
    session: Session, actual_id: str = "eia-us48-demand", df_id: str = "eia-us48-df", days: int = 365
) -> ModelEval | None:
    """Operator day-ahead (EIA DF) daily totals vs actual complete local days. 1-day horizon only."""
    actual = {r.local_date: r.total for r in complete_daily(session, actual_id)}
    df = {r.local_date: r.total for r in complete_daily(session, df_id)}
    common = sorted(set(actual) & set(df))[-days:]
    if len(common) < 7:
        return None
    errors = [abs(actual[d] - df[d]) for d in common]
    scale = mase_scale([actual[d] for d in sorted(actual)], 7)
    mae = sum(errors) / len(errors)
    series = session.get(Series, actual_id)
    tz = series.local_tz if series and series.local_tz else "America/New_York"
    return _upsert_eval(
        session,
        series_id=actual_id,
        model_version="eia_df",
        target_kind="daily_total",
        horizon_bucket="1d",
        mase=mae / scale if scale else None,
        mase_lag24=None,
        mae=mae,
        coverage=None,
        interval_level=0.8,
        n_origins=len(common),
        backtest_start=local_midnight_utc(common[0], tz),
        backtest_end=local_midnight_utc(common[-1], tz),
        evaluated_at=utc_now(),
    )


def run_evaluations(session: Session, series_ids: list[str] | None = None) -> list[ModelEval]:
    now = utc_now()
    out: list[ModelEval] = []
    for series_id in series_ids or [*DEMAND_SERIES, *PRICE_SERIES]:
        for spec in specs_for(session, series_id):
            out.extend(evaluate_spec(session, spec, now))
        if series_id in DEMAND_SERIES:
            df_row = evaluate_eia_df(session, series_id)
            if df_row:
                out.append(df_row)
    session.flush()
    return out
