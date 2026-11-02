"use client";

import { useEffect, useMemo, useState } from "react";

import { TimeChart } from "@/components/TimeChart";
import { Card, DemoBanner, Empty, Loading, PageTitle } from "@/components/ui";
import { useApi } from "@/lib/api";
import { compact, dateTime, day, ms, num, US48_TZ } from "@/lib/format";
import type { SeriesMeta } from "@/lib/types";

type Option = {
  series_id: string;
  title: string;
  unit: string;
  target_kind: string;
  models: string[];
  steps: number[];
  buckets: Record<string, number[]>;
};
type FRow = { horizon: number; target: string; point: number; lo: number | null; hi: number | null; level: number };
type Eval = {
  model: string;
  model_version: string;
  horizon_bucket: string;
  mase: number | null;
  mase_lag24: number | null;
  mae: number | null;
  coverage: number | null;
  interval_level: number;
  n_origins: number;
  backtest_start: string | null;
  backtest_end: string | null;
};
type FResp = {
  series: SeriesMeta;
  target_kind: string;
  issued_at: string | null;
  training_window_end: string | null;
  models: Record<string, FRow[]>;
  actuals: { t: string; value: number }[];
  evals: Eval[];
  df_benchmark: {
    label: string;
    note: string;
    next_day: { date: string; total: number; quality: string; hour_count: number; expected_hours: number } | null;
    eval: Eval | null;
  } | null;
  disclaimer: string;
  note: string;
};
type History = { models: Record<string, { target: string; point: number; lo: number | null; hi: number | null; actual: number | null }[]> };

const MODEL_COLOR: Record<string, string> = {
  naive: "var(--series-2)",
  seasonal_naive: "var(--series-3)",
  seasonal_mean4: "var(--series-4)",
  fourier_ar: "var(--series-7)",
  logret_ar: "var(--series-5)",
};
const MODEL_LABEL: Record<string, string> = {
  naive: "Naive (last value)",
  seasonal_naive: "Seasonal naive",
  seasonal_mean4: "Mean of last 4 same weekdays",
  fourier_ar: "Fourier + AR(1)",
  logret_ar: "Log-return AR(1)",
};
const KIND_LABEL: Record<string, string> = {
  daily_total: "daily total, 1–30 days",
  daily_peak: "daily peak, 1–30 days",
  hourly: "hourly, 1–7 days",
  daily: "daily, 1 day – 1 month",
  weekly: "weekly, 1–4 weeks",
};
const MIN_ORIGINS = 30;

function coverageStatus(e: Eval) {
  if (e.coverage == null) return { icon: "—", text: "no band", tone: "var(--muted)" };
  if (e.n_origins < MIN_ORIGINS) return { icon: "⚠", text: `only ${e.n_origins} origins — noisy`, tone: "var(--warning)" };
  const gap = e.coverage - e.interval_level;
  if (gap < -0.1) return { icon: "✕", text: "too narrow", tone: "var(--critical)" };
  if (gap > 0.1) return { icon: "⚠", text: "too wide", tone: "var(--warning)" };
  return { icon: "✓", text: "calibrated", tone: "var(--good)" };
}

export default function ForecastsPage() {
  const options = useApi<Option[]>("/api/forecasts/options");
  const overview = useApi<{ demo: boolean }>("/api/overview");
  const [key, setKey] = useState("eia-us48-demand|daily_total");
  const opt = options.data?.find((o) => `${o.series_id}|${o.target_kind}` === key);
  const [seriesId, kind] = key.split("|");
  const fc = useApi<FResp>(`/api/forecasts?series_id=${seriesId}&target_kind=${kind}`);
  const isDemand = seriesId === "eia-us48-demand";
  const [model, setModel] = useState<string>("");
  const [horizon, setHorizon] = useState(1);

  useEffect(() => {
    if (opt) {
      setModel(opt.models.includes("seasonal_naive") ? "seasonal_naive" : opt.models[0]);
      setHorizon(opt.steps[0]);
    }
  }, [opt?.series_id, opt?.target_kind]); // eslint-disable-line react-hooks/exhaustive-deps

  const hist = useApi<History>(opt ? `/api/forecasts/history?series_id=${seriesId}&target_kind=${kind}&horizon=${horizon}` : null);
  const d = fc.data;

  const fmtY = (v: number) => (isDemand ? compact(v, 1) : num(v, 2));
  const tz = isDemand ? US48_TZ : "UTC";
  const fmtX = (x: number) => (kind === "hourly" ? dateTime(x) : day(x, tz, true));
  const axisX = (x: number) => day(x, tz);

  const firstBucket = opt ? Object.keys(opt.buckets)[0] : "";
  const evalFor = (m: string, bucket: string) => d?.evals.find((e) => e.model === m && e.horizon_bucket === bucket);

  const chartRows = useMemo(() => {
    if (!d) return [];
    const rows = new Map<number, Record<string, number | null> & { x: number }>();
    const put = (x: number, patch: Record<string, number | null>) => rows.set(x, { ...(rows.get(x) ?? { x }), ...patch });
    for (const a of d.actuals) put(ms(a.t), { actual: a.value });
    for (const [m, rs] of Object.entries(d.models))
      for (const r of rs) put(ms(r.target), { [m]: r.point, ...(m === model ? { lo: r.lo, hi: r.hi } : {}) });
    return [...rows.values()].sort((a, b) => a.x - b.x);
  }, [d, model]);

  const bandEval = evalFor(model, firstBucket);
  const naiveWins = opt
    ? Object.keys(opt.buckets).filter((b) => {
        const scored = opt.models.map((m) => evalFor(m, b)).filter((e): e is Eval => !!e && e.mase != null);
        if (!scored.length) return false;
        const best = scored.reduce((a, e) => (e.mase! < a.mase! ? e : a));
        return best.model === "naive";
      })
    : [];

  return (
    <>
      <DemoBanner show={overview.data?.demo} />
      <PageTitle title="Forecasts">
        Statistical baselines with measured, not assumed, uncertainty. Every band says how often it actually
        contained the outcome in a rolling-origin backtest, and over how many forecast origins.
      </PageTitle>

      <div className="card mb-4 px-4 py-3 text-[13px]" role="note" style={{ borderColor: "var(--axis)" }}>
        <strong>Not advice.</strong> <span className="ink-2">{d?.disclaimer ?? "Statistical extrapolations for context, not trading or operational advice."}</span>
      </div>

      {!options.data ? (
        <Loading error={options.error} />
      ) : (
        <div className="mb-4 flex flex-wrap items-center gap-3 text-[13px]">
          <label className="ink-2">
            Series{" "}
            <select value={key} onChange={(e) => setKey(e.target.value)}>
              {options.data.map((o) => (
                <option key={`${o.series_id}|${o.target_kind}`} value={`${o.series_id}|${o.target_kind}`}>
                  {o.title} — {KIND_LABEL[o.target_kind] ?? o.target_kind}
                </option>
              ))}
            </select>
          </label>
          {opt && (
            <div className="flex flex-wrap gap-1.5" role="group" aria-label="Model for the band">
              {opt.models.map((m) => (
                <button key={m} className="btn" aria-pressed={model === m} onClick={() => setModel(m)}>
                  {MODEL_LABEL[m] ?? m}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {!d || !opt ? (
        options.data && <Loading error={fc.error} />
      ) : (
        <div className="grid grid-cols-1 gap-4">
          <Card
            title={`${d.series.title} — ${KIND_LABEL[kind] ?? kind}`}
            subtitle={
              d.issued_at
                ? `${d.series.unit} · issued ${dateTime(d.issued_at)} · trained through ${fmtX(ms(d.training_window_end!))}`
                : "No forecast issued yet"
            }
            footer={d.note}
          >
            {Object.keys(d.models).length ? (
              <TimeChart
                rows={chartRows}
                series={[
                  {
                    key: "band",
                    label: bandEval?.coverage != null
                      ? `${MODEL_LABEL[model]} 80% band — measured ${Math.round(bandEval.coverage * 100)}% over ${bandEval.n_origins} origins (${firstBucket})`
                      : `${MODEL_LABEL[model]} 80% band — not yet backtested`,
                    color: MODEL_COLOR[model],
                    band: ["lo", "hi"],
                  },
                  { key: "actual", label: "Actual", color: "var(--series-1)" },
                  ...opt.models.map((m) => ({
                    key: m,
                    label: MODEL_LABEL[m] ?? m,
                    color: MODEL_COLOR[m] ?? "var(--series-8)",
                    width: m === model ? 2 : 1.25,
                  })),
                ]}
                yFormat={fmtY}
                xFormat={axisX}
                tipX={fmtX}
                height={320}
                refX={d.training_window_end ? { x: ms(d.training_window_end), label: "issued from here" } : undefined}
              />
            ) : (
              <Empty>Not enough complete history to issue a forecast yet.</Empty>
            )}
          </Card>

          <Card
            title="Backtest (ModelEval)"
            subtitle="Rolling-origin backtest. MASE < 1 beats the in-sample seasonal-naive scale; lower is better. Coverage = how often the 80% band contained the actual."
            footer={
              <>
                MASE scale: {kind === "hourly" ? "lag-168 seasonal naive (lag-24 shown as secondary)" : isDemand ? "lag-7 (same weekday)" : "plain naive (prices)"}.
                Coverage from fewer than {MIN_ORIGINS} origins is flagged as noise. Bands come only from errors already realized at each origin.
              </>
            }
          >
            {!isDemand && naiveWins.length > 0 && (
              <p className="mb-3 text-[13px]">
                <strong>Naive wins</strong> <span className="ink-2">in {naiveWins.length} of {Object.keys(opt.buckets).length} horizons ({naiveWins.join(", ")}) — expected for prices that behave like a random walk.</span>
              </p>
            )}
            {d.evals.length ? (
              <div className="overflow-x-auto">
                <table className="data">
                  <thead>
                    <tr>
                      <th>Horizon</th>
                      <th>Model</th>
                      <th>MASE</th>
                      {kind === "hourly" && <th>MASE (lag-24)</th>}
                      <th>MAE ({d.series.unit})</th>
                      <th>80% coverage</th>
                      <th>Origins</th>
                      <th>Backtest window</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.keys(opt.buckets).flatMap((b) => {
                      const rows = opt.models.map((m) => evalFor(m, b)).filter((e): e is Eval => !!e);
                      const best = rows.filter((e) => e.mase != null).reduce<Eval | null>((a, e) => (!a || e.mase! < a.mase! ? e : a), null);
                      return rows.map((e, i) => {
                        const st = coverageStatus(e);
                        return (
                          <tr key={`${b}-${e.model}`}>
                            <td>{i === 0 ? b : ""}</td>
                            <td>
                              <span className="mr-1.5 inline-block h-[2px] w-3 align-middle" style={{ background: MODEL_COLOR[e.model] }} />
                              {MODEL_LABEL[e.model] ?? e.model}
                              {best?.model === e.model && <span className="ml-1.5 text-[11px] font-semibold">★ best</span>}
                            </td>
                            <td>{num(e.mase, 2)}</td>
                            {kind === "hourly" && <td>{num(e.mase_lag24, 2)}</td>}
                            <td>{isDemand ? compact(e.mae, 1) : num(e.mae, 2)}</td>
                            <td>
                              {e.coverage == null ? "—" : `${Math.round(e.coverage * 100)}%`}{" "}
                              <span className="whitespace-nowrap text-[12px]">
                                <span aria-hidden style={{ color: st.tone }}>{st.icon}</span> <span className="ink-2">{st.text}</span>
                              </span>
                            </td>
                            <td>{e.n_origins}</td>
                            <td className="whitespace-nowrap muted">
                              {day(e.backtest_start, tz, true)} – {day(e.backtest_end, tz, true)}
                            </td>
                          </tr>
                        );
                      });
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty>No backtest yet.</Empty>
            )}
          </Card>

          {d.df_benchmark && (
            <Card title={d.df_benchmark.label} subtitle={d.df_benchmark.note}>
              {(() => {
                const ours = d.models[model]?.[0];
                const ourEval = evalFor(model, "1d");
                const dfEval = d.df_benchmark.eval;
                return (
                  <div className="overflow-x-auto">
                    <table className="data">
                      <thead>
                        <tr>
                          <th>1-day horizon</th>
                          <th>Next local day ({ours ? day(ours.target, US48_TZ, true) : "—"})</th>
                          <th>Backtest MAE (MWh)</th>
                          <th>MASE</th>
                          <th>Days</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td>Operator day-ahead (EIA DF)</td>
                          <td>
                            {d.df_benchmark.next_day
                              ? `${compact(d.df_benchmark.next_day.total, 2)} (${d.df_benchmark.next_day.hour_count}/${d.df_benchmark.next_day.expected_hours} h${d.df_benchmark.next_day.quality === "partial" ? ", partial" : ""})`
                              : "not published yet"}
                          </td>
                          <td>{compact(dfEval?.mae, 2)}</td>
                          <td>{num(dfEval?.mase, 2)}</td>
                          <td>{dfEval?.n_origins ?? "—"}</td>
                        </tr>
                        <tr>
                          <td>{MODEL_LABEL[model]}</td>
                          <td>{ours ? compact(ours.point, 2) : "—"}</td>
                          <td>{compact(ourEval?.mae, 2)}</td>
                          <td>{num(ourEval?.mase, 2)}</td>
                          <td>{ourEval?.n_origins ?? "—"}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                );
              })()}
            </Card>
          )}

          <Card
            title="Past issues vs what happened"
            subtitle="Each point is a forecast made earlier for that target, at the chosen horizon (90-day retention)"
            actions={
              <label className="text-[13px] ink-2">
                Horizon{" "}
                <select value={horizon} onChange={(e) => setHorizon(Number(e.target.value))}>
                  {opt.steps.filter((s, i) => i < 8 || s % 7 === 0 || s % 24 === 0).map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>
            }
          >
            {hist.data && Object.values(hist.data.models).some((r) => r.some((p) => p.actual != null)) ? (
              (() => {
                const rows = new Map<number, Record<string, number | null> & { x: number }>();
                for (const [m, rs] of Object.entries(hist.data!.models))
                  for (const r of rs) {
                    const x = ms(r.target);
                    rows.set(x, { ...(rows.get(x) ?? { x }), [m]: r.point, ...(r.actual != null ? { actual: r.actual } : {}) });
                  }
                return (
                  <TimeChart
                    rows={[...rows.values()].sort((a, b) => a.x - b.x)}
                    series={[
                      { key: "actual", label: "Actual", color: "var(--series-1)" },
                      ...opt.models.map((m) => ({ key: m, label: MODEL_LABEL[m] ?? m, color: MODEL_COLOR[m], width: 1.5 })),
                    ]}
                    yFormat={fmtY}
                    xFormat={axisX}
                    tipX={fmtX}
                  />
                );
              })()
            ) : (
              <Empty>Past issues appear here once their targets have happened. Issues accumulate daily (demand) or on each new price.</Empty>
            )}
          </Card>
        </div>
      )}
    </>
  );
}
