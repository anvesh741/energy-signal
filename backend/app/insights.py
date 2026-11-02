"""Ranked "what changed" rules.

- Fire only when the underlying series got a new observation (as_of advances).
- Cooldown after each firing; hysteresis on state (enter/exit thresholds differ).
- as_of is the data date, shown as "as of Oct 28" — never the fetch time.
- Inputs are stored so the UI can show exactly what the rule looked at.
"""

import json
import math
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlmodel import Session, col, select

from app.forecast import PRICE_SERIES
from app.ingest import complete_daily, history
from app.models import Insight, Series
from app.rollup import prior_complete_week_change
from app.storage_band import five_year_band
from app.timeutil import local_midnight_utc, utc_now

COOLDOWN = timedelta(hours=18)
RETENTION = timedelta(days=180)
# price move: enter "extreme" at the 95th/5th percentile, leave it only inside 90th/10th
ENTER_PCT, EXIT_PCT = 95.0, 90.0
# storage: leave "below"/"above" only once back inside the band by this share of its width
BAND_EXIT_MARGIN = 0.05


def ordinal(n: float) -> str:
    k = int(round(n))
    suffix = "th" if 10 <= k % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(k % 10, "th")
    return f"{k}{suffix}"


def percentile_rank(values: list[float], x: float) -> float:
    if not values:
        return 50.0
    return 100.0 * sum(1 for v in values if v <= x) / len(values)


def log_returns(values: list[float]) -> list[float]:
    return [math.log(b / a) for a, b in zip(values, values[1:]) if a > 0 and b > 0]


def _last(session: Session, rule_id: str, series_id: str) -> Insight | None:
    return session.exec(
        select(Insight)
        .where(Insight.rule_id == rule_id, Insight.series_id == series_id)
        .order_by(col(Insight.issued_at).desc())
    ).first()


def should_emit(
    session: Session,
    rule_id: str,
    series_id: str,
    as_of: datetime,
    now: datetime | None = None,
) -> bool:
    now = now or utc_now()
    last = _last(session, rule_id, series_id)
    if last is None:
        return True
    if last.as_of_ts >= as_of:
        return False  # no new observation
    if last.cooldown_until and last.cooldown_until > now:
        return False
    return True


def price_state(pct: float, previous: str) -> str:
    """Hysteresis: 'high'/'low' are entered at 95/5 and kept until back inside 90/10."""
    if pct >= ENTER_PCT or (previous == "high" and pct >= EXIT_PCT):
        return "high"
    if pct <= 100 - ENTER_PCT or (previous == "low" and pct <= 100 - EXIT_PCT):
        return "low"
    return "normal"


def band_state(current: float, lo: float, hi: float, previous: str) -> str:
    margin = (hi - lo) * BAND_EXIT_MARGIN
    if current < lo or (previous == "below" and current < lo + margin):
        return "below"
    if current > hi or (previous == "above" and current > hi - margin):
        return "above"
    return "inside"


def _emit(session: Session, **fields) -> Insight:
    now = utc_now()
    inputs = fields.pop("inputs")
    row = Insight(issued_at=now, cooldown_until=now + COOLDOWN, inputs_json=json.dumps(inputs), **fields)
    session.add(row)
    return row


def demand_week_insight(session: Session, series_id: str = "eia-us48-demand") -> Insight | None:
    series = session.get(Series, series_id)
    change = prior_complete_week_change(complete_daily(session, series_id))
    if not change or not series or not series.local_tz:
        return None
    end = datetime.fromisoformat(change["recent_end"]).date()
    as_of = local_midnight_utc(end, series.local_tz)
    if not should_emit(session, "demand_week", series_id, as_of):
        return None
    pct = change["pct_change"]
    return _emit(
        session,
        rule_id="demand_week",
        series_id=series_id,
        rank=2 if abs(pct) >= 3 else 4,
        as_of_ts=as_of,
        state="up" if pct >= 0 else "down",
        headline=(
            f"US48 demand {'up' if pct >= 0 else 'down'} {abs(pct):.1f}% over the last 7 complete "
            f"local days vs the 7 before"
        ),
        inputs={**change, "window": "7 complete local days vs prior 7 (America/New_York)"},
    )


def price_move_insight(session: Session, series_id: str) -> Insight | None:
    series = session.get(Series, series_id)
    pts = history(session, series_id)
    window = 156 if series and series.frequency == "weekly" else 252
    if not series or len(pts) < 40:
        return None
    rets = log_returns([v for _, v in pts])
    hist, last_ret = rets[-(window + 1) : -1], rets[-1]
    as_of = pts[-1][0]
    if not should_emit(session, "price_move", series_id, as_of):
        return None
    pct = percentile_rank(hist, last_ret)
    previous = _last(session, "price_move", series_id)
    state = price_state(pct, previous.state if previous else "normal")
    entered = state != "normal" and (previous is None or previous.state != state)
    step = "week" if series.frequency == "weekly" else "observation"
    move = (pts[-1][1] / pts[-2][1] - 1) * 100
    return _emit(
        session,
        rule_id="price_move",
        series_id=series_id,
        rank=1 if entered else (3 if state != "normal" else 5),
        as_of_ts=as_of,
        state=state,
        headline=(
            f"{series.title} {'rose' if move >= 0 else 'fell'} {abs(move):.1f}% in the latest {step}: "
            f"{ordinal(pct)} percentile of the last {len(hist)} moves"
        ),
        inputs={
            "last_value": pts[-1][1],
            "prior_value": pts[-2][1],
            "last_log_return": last_ret,
            "percentile": pct,
            "window": f"last {len(hist)} {step} log returns",
            "unit": series.unit,
        },
    )


def storage_band_insight(session: Session, series_id: str = "eia-storage-r48") -> Insight | None:
    series = session.get(Series, series_id)
    pts = history(session, series_id)
    if not series or len(pts) < 52 * 5:
        return None
    weekly = [(t.date(), v) for t, v in pts]
    b = five_year_band(weekly, weekly[-1][0])
    if not b or b["current"] is None:
        return None
    as_of = pts[-1][0]
    if not should_emit(session, "storage_band", series_id, as_of):
        return None
    previous = _last(session, "storage_band", series_id)
    state = band_state(b["current"], b["min"], b["max"], previous.state if previous else "inside")
    changed = previous is None or previous.state != state
    vs_mean = (b["current"] / b["mean"] - 1) * 100
    return _emit(
        session,
        rule_id="storage_band",
        series_id=series_id,
        rank=(1 if changed else 2) if state != "inside" else 4,
        as_of_ts=as_of,
        state=state,
        headline=(
            f"{series.region} gas storage {b['current']:,.0f} Bcf is {state} its 5-year week-{b['week']} "
            f"range ({vs_mean:+.1f}% vs 5-yr mean)"
        ),
        inputs={**b, "window": f"same ISO week, prior {b['n_years']} years"},
    )


def generate_insights(session: Session) -> list[Insight]:
    created = [demand_week_insight(session), storage_band_insight(session)]
    created += [price_move_insight(session, sid) for sid in PRICE_SERIES]
    session.exec(delete(Insight).where(col(Insight.issued_at) < utc_now() - RETENTION))
    session.flush()
    return [c for c in created if c]


def current_insights(session: Session) -> list[Insight]:
    """Latest insight per (rule, series), ranked: lowest rank first, then newest data."""
    latest: dict[tuple[str, str], Insight] = {}
    for row in session.exec(select(Insight).order_by(col(Insight.issued_at).desc())):
        latest.setdefault((row.rule_id, row.series_id), row)
    return sorted(latest.values(), key=lambda r: (r.rank, -r.as_of_ts.timestamp()))
