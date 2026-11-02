"""Synthetic history so the dashboard runs without API keys:  python -m app.demo_seed

Everything is written under RefreshRun source="demo"; the UI shows a DEMO DATA banner
until a real refresh lands. Values are plausible in scale, not real.
"""

import math
import random
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.catalog import FUELS, STORAGE_REGIONS, ids_where
from app.db import init_db, session_scope
from app.eval import run_evaluations
from app.forecast import DEMAND_SERIES, PRICE_SERIES, issue_forecasts
from app.ingest import finish_refresh, rebuild_rollups, seed_series, start_refresh, upsert_observations
from app.insights import generate_insights
from app.timeutil import utc_now

NY = ZoneInfo("America/New_York")
FUEL_SHARE = {"NG": 0.40, "COL": 0.16, "NUC": 0.18, "WND": 0.10, "SUN": 0.05, "WAT": 0.06, "OIL": 0.01, "OTH": 0.04}
STORAGE_SHARE = {"R48": 1.0, "R31": 0.21, "R32": 0.25, "R33": 0.37, "R34": 0.07, "R35": 0.10}


def _hourly_demand(rng: random.Random, days: int) -> list[tuple[datetime, float]]:
    end = utc_now().replace(minute=0, second=0, microsecond=0)
    t = end - timedelta(days=days)
    out, noise = [], 0.0
    while t <= end:
        local = t.astimezone(NY)
        doy = local.timetuple().tm_yday
        # summer and winter peaks, shoulder-season troughs
        annual = 0.10 * math.cos((doy - 205) / 365 * 2 * math.pi) ** 2 + 0.04 * math.cos((doy - 20) / 365 * 2 * math.pi)
        hour = local.hour + local.minute / 60
        diurnal = 0.13 * math.sin((hour - 9) / 24 * 2 * math.pi) + 0.04 * math.sin((hour - 15) / 12 * 2 * math.pi)
        weekend = -0.06 if local.weekday() >= 5 else 0.0
        noise = 0.9 * noise + rng.gauss(0, 0.008)
        out.append((t, 440_000 * (1 + annual + diurnal + weekend + noise)))
        t += timedelta(hours=1)
    return out


def _walk(rng, start, n, step, vol, drift=0.0, business_days=False, revert=None):
    t = utc_now().replace(hour=0, minute=0, second=0, microsecond=0) - step * int(n * (1.4 if business_days else 1))
    out, v = [], start
    while len(out) < n:
        t += step
        if business_days and t.weekday() >= 5:
            continue
        pull = revert * math.log(start / v) if revert else 0.0
        v *= math.exp(drift + pull + rng.gauss(0, vol))
        out.append((t, v))
    return out


def _pts(pairs):
    return [{"ts_utc": t, "value": v} for t, v in pairs]


def run() -> None:
    rng = random.Random(42)
    init_db()
    with session_scope() as session:
        seed_series(session)
        run = start_refresh(session, "demo")
        rows = 0

        demand = _hourly_demand(rng, 400)
        # leave today partial on purpose: drop the last few hours of the current local day
        demand = demand[:-3]
        rows += upsert_observations(session, "eia-us48-demand", _pts(demand))
        df = [(t, v * (1 + rng.gauss(0, 0.018))) for t, v in demand]
        tomorrow = [(t + timedelta(hours=24), v * (1 + rng.gauss(0, 0.02))) for t, v in demand[-24:]]
        rows += upsert_observations(session, "eia-us48-df", _pts(df + tomorrow))

        recent = demand[-45 * 24 :]
        rows += upsert_observations(session, "eia-us48-ng", _pts([(t, v * 1.02) for t, v in recent]))
        rows += upsert_observations(session, "eia-us48-ti", _pts([(t, -v * 0.02) for t, v in recent]))
        for code in FUELS:
            pts = []
            for t, v in recent:
                share = FUEL_SHARE[code]
                if code == "SUN":
                    hour = t.astimezone(NY).hour
                    share *= max(0.0, math.sin((hour - 6) / 12 * math.pi)) * 2.6
                pts.append((t, max(0.0, v * share * (1 + rng.gauss(0, 0.05)))))
            rows += upsert_observations(session, f"eia-us48-gen-{code.lower()}", _pts(pts))
        for sid in ids_where(source="eia", frequency="hourly"):
            rebuild_rollups(session, sid)

        day = timedelta(days=1)
        n = 5 * 252
        wti = _walk(rng, 74, n, day, 0.021, business_days=True, revert=0.004)
        rows += upsert_observations(session, "eia-wti", _pts(wti))
        rows += upsert_observations(
            session, "eia-brent", _pts([(t, v * 1.05 * (1 + rng.gauss(0, 0.006))) for t, v in wti])
        )
        rows += upsert_observations(
            session, "eia-henry-hub", _pts(_walk(rng, 3.0, n, day, 0.038, business_days=True, revert=0.006))
        )
        week = timedelta(days=7)
        rows += upsert_observations(session, "eia-gasoline", _pts(_walk(rng, 3.30, 260, week, 0.018, revert=0.02)))
        rows += upsert_observations(session, "eia-diesel", _pts(_walk(rng, 3.75, 260, week, 0.017, revert=0.02)))

        start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0) - week * (6 * 52 + 4)
        start -= timedelta(days=(start.weekday() - 4) % 7)  # storage periods end on Fridays
        for code, share in STORAGE_SHARE.items():
            pts, t, drift = [], start, 0.0
            while t <= utc_now():
                woy = t.isocalendar().week
                seasonal = 2600 - 1050 * math.cos((woy - 13) / 52 * 2 * math.pi)
                drift = 0.97 * drift + rng.gauss(0, 18)
                pts.append((t, max(50.0, (seasonal + drift) * share)))
                t += week
            rows += upsert_observations(session, f"eia-storage-{code.lower()}", _pts(pts))
        assert set(STORAGE_SHARE) == set(STORAGE_REGIONS)

        month = timedelta(days=30.44)
        for sid, base, vol in (("wb-coal-australia", 135, 0.06), ("wb-ttf", 11, 0.09), ("wb-lng-japan", 12.5, 0.05)):
            pts = _walk(rng, base, 120, month, vol, revert=0.05)
            rows += upsert_observations(
                session, sid, _pts([(t.replace(day=1, tzinfo=timezone.utc), v) for t, v in pts])
            )
        for sid, base in (("ember-usa-demand", 345), ("ember-deu-demand", 42), ("ember-ind-demand", 150),
                          ("ember-chn-demand", 760), ("ember-bra-demand", 56), ("ember-gbr-demand", 24),
                          ("ember-jpn-demand", 80)):
            pts = []
            for i, (t, v) in enumerate(_walk(rng, base, 120, month, 0.01, drift=0.0015)):
                m = t.month
                seasonal = 1 + 0.07 * math.cos((m - 1.5) / 12 * 2 * math.pi) ** 2
                pts.append((t.replace(day=1), v * seasonal))
            rows += upsert_observations(session, sid, _pts(pts))
        session.commit()

        for sid in [*DEMAND_SERIES, *PRICE_SERIES]:
            issue_forecasts(session, sid)
        run_evaluations(session)
        generate_insights(session)
        finish_refresh(session, run, success=True, rows=rows, error=None)
        print(f"demo seed: {rows} observations; forecasts, evals and insights built")


if __name__ == "__main__":
    run()
