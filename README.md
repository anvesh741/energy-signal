# EnergySignal

A web dashboard for US electricity demand/generation and oil & gas prices, with
cadence-aware statistical forecasts whose uncertainty is **measured, not assumed**.
It does not claim to beat markets and is not trading advice — the Forecasts page
carries the disclaimer.

- **Backend**: FastAPI (read-only API) + a separate scheduler process, SQLite in WAL mode.
- **Frontend**: Next.js (App Router) + Recharts; `/api/*` is rewritten to FastAPI.

```
backend/app/
  catalog.py        pinned series (each maps to exactly one upstream id)
  models.py         Series, Observation, DailyRollup, Forecast, ModelEval, Insight, RefreshRun, SchedulerLease
  sources/          eia.py, ember.py, pink_sheet.py  (+ tests/fixtures)
  rollup.py         local-day aggregation, completeness, DST 23/25h
  ingest.py         upserts, touched-date rollup rebuilds
  jobs.py           refresh jobs, resumable backfill, weekly release windows
  scheduler.py      dedicated process + single-row lease
  forecast.py       models, empirical bands, issuance + 90-day retention
  eval.py           rolling-origin backtests -> ModelEval
  insights.py       ranked rules with cooldown + hysteresis
  main.py           API
frontend/app/       Overview, Electricity, Fuels, Forecasts, Sources
```

## Run it

Requirements: Python 3.11+ and Node 20+.

```bash
cp .env.example .env            # add EIA_API_KEY (and EMBER_API_KEY) — .env is gitignored

cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest      # unit + fixture tests

# no keys yet? load clearly-labeled synthetic data instead:
.venv/bin/python -m app.demo_seed

# three processes:
.venv/bin/uvicorn app.main:app --port 8000          # API
.venv/bin/python -m app.scheduler                   # ingestion (or --once)
cd ../frontend && npm install && npm run dev        # http://localhost:3000
```

Keys: EIA — https://www.eia.gov/opendata/register.php · Ember — https://ember-energy.org/data/api/.
The World Bank Pink Sheet needs no key. The UI shows a **Demo data** banner until a
real refresh lands; delete `data/energysignal.db` before the first real run if you seeded demo data.

## Free hosting (GitHub Pages)

`.github/workflows/pages.yml` runs the whole pipeline hourly on GitHub Actions, with no server:
`scheduler --once` refreshes → `python -m app.export_static` snapshots every API response the
dashboard requests into JSON → `next build` with `STATIC_EXPORT=1` produces a static site that
reads those files → deploy to Pages. The SQLite database rides along in the Actions cache.

Setup: add `EIA_API_KEY` and `EMBER_API_KEY` as repository secrets, and set
Settings → Pages → Source to **GitHub Actions**. Trade-offs: data is up to ~1 hour old
(the footer shows the snapshot time), GitHub may delay scheduled runs at busy times, and it
disables scheduled workflows after 60 days without repository activity (re-enable in the Actions tab).

## What the scheduler does

Only the holder of `SchedulerLease` runs jobs (atomic conditional UPDATE, renewed by a
heartbeat thread), so `--reload` or a second scheduler stands by instead of double-running.

| Feed | Cadence | Notes |
|---|---|---|
| EIA hourly (US48 D, DF, NG, TI, fuel mix) | every 45 min | re-pulls the trailing 72 h (BAs revise) and upserts; resumable 30-day-chunk backfill (400 days for demand/DF, 45 for the rest); rebuilds rollups only for touched local dates |
| EIA spot (WTI `RWTC`, Brent `RBRTE`, Henry Hub `RNGWHHD`) | every 6 h | daily values published in weekly batches — most runs are no-ops |
| EIA retail gasoline/diesel | polled hourly Mon 12:00 – Wed 12:00 ET | stops once a new week appears |
| EIA gas storage (L48 + 5 regions) | polled hourly Wed 10:00 – Fri 18:00 ET | first run backfills 6 years for the 5-year band |
| Ember monthly demand | daily | CC BY 4.0 |
| World Bank Pink Sheet | daily | `If-None-Match` / `If-Modified-Since`, then content hash; a parse failure is a failed `RefreshRun` and writes nothing |

**Pink Sheet URL:** the default `PINK_SHEET_URL` currently serves a file last updated
January 2025 (data through 2024-12). The World Bank changes this link when it republishes;
copy the current "Monthly prices" link from https://www.worldbank.org/en/research/commodity-markets
into `.env`.

If an EIA series id turns out to be wrong (the first weekly backfill fails with "no rows for …"),
fix `source_code` in `catalog.py` — the Series still maps to one upstream series.

## Forecasting and evaluation

| Target | Horizons | Models | MASE scale |
|---|---|---|---|
| US48 demand, daily total & peak (complete local days only) | 1–30 days | naive, seasonal naive (7d), mean of last 4 same weekdays | lag 7 |
| US48 demand, hourly | 1–168 h | seasonal naive (168h), Fourier (24h+168h) + AR(1) | lag 168 (lag 24 secondary) |
| WTI, Brent, Henry Hub | 1, 5, 10, 20 business days | **naive (default)**, log-return AR(1) | plain naive |
| Gasoline, diesel | 1, 2, 4 weeks | naive, log-return AR(1) | plain naive |

- 80% bands are `point × exp(q10, q90)` of each model's own historical log errors at that
  horizon. For naive prices that is exactly the empirical quantiles of h-step log returns.
- `ModelEval` comes from a rolling-origin backtest that uses the same model functions;
  bands there use only errors already realized at each origin, so coverage is out of sample.
  The UI shows coverage next to `n_origins` and flags noisy (< 30 origins) or miscalibrated
  (±10 pts) bands.
- EIA DF (the operators' day-ahead forecast) is compared only at the 1-day horizon.
- Demand issues once per new complete local day; prices on each new observation.
  Issues older than 90 days are pruned; ModelEval rows are kept.
- No weather inputs: beyond a few days demand forecasts are mostly climatology.

## Conventions

- All stored timestamps are timezone-aware UTC; hourly `ts_utc` is the period start.
- A demand "day" is a local calendar day in `Series.local_tz`; US48 uses America/New_York.
  A day is complete when `hour_count >= expected_hours - 1` (23/24/25 from the tz calendar).
  Partial days are excluded from forecasts, backtests, insights and KPIs.
- Insights fire only on a new observation, show the data date ("as of Oct 28"), have an
  18 h cooldown and enter/exit hysteresis, and store their inputs.
- Units: electricity MWh (Ember TWh), crude $/bbl, Henry Hub $/MMBtu, retail $/gal, storage Bcf.

## Not in v1

Weather-driven demand, carbon intensity, ENTSO-E, water, air quality, and append-only EIA
revision vintages (v1 upserts overwrite revised values).

## Licenses

EIA data is U.S. government public-domain data (cite EIA). Ember and World Bank data are
CC BY 4.0 — attribution is on the Sources page and in chart footers.
