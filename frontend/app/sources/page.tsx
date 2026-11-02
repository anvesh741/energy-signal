"use client";

import { Card, DemoBanner, Loading, PageTitle } from "@/components/ui";
import { useApi } from "@/lib/api";
import { dateTime, day, lag } from "@/lib/format";
import type { SeriesMeta } from "@/lib/types";

type Item = SeriesMeta & {
  route: string;
  feed: string;
  latest_period: string | null;
  data_lag_hours: number | null;
  last_success: string | null;
  fetch_staleness_hours: number | null;
  last_failure: { at: string; error: string | null } | null;
};
type Run = {
  source: string;
  started_at: string;
  finished_at: string | null;
  success: boolean;
  rows_upserted: number;
  new_period: boolean;
  error: string | null;
};

const LIMITS = [
  "Spot prices (WTI, Brent, Henry Hub) are daily values usually published in weekly batches; they can be up to ~7 days behind. Insights use the data date.",
  "Gasoline, diesel and gas storage are weekly and slip in holiday weeks; we poll inside a release window until the new week appears.",
  "Hourly demand is revised by balancing authorities for 48–72 hours; we re-pull and overwrite (no revision history in v1).",
  "Partial local days are omitted from daily totals, KPIs, insights and forecasts, so an incomplete today never looks like a demand drop.",
  "A US48 “day” is a calendar day in America/New_York.",
  "Ember data is monthly; the World Bank Pink Sheet is a monthly Excel file.",
  "Price forecasts: the naive model often wins; naive 80% bands are empirical quantiles of historical h-step returns.",
  "Demand forecasts use no weather, so beyond a few days they are mostly climatology.",
  "Interval labels report measured coverage and the number of backtest origins; few origins means noisy coverage.",
];

function feedState(i: Item) {
  if (i.last_failure) return { icon: "✕", text: "last refresh failed", tone: "var(--critical)" };
  if (!i.last_success) return { icon: "—", text: "never fetched", tone: "var(--muted)" };
  return { icon: "✓", text: "ok", tone: "var(--good)" };
}

export default function SourcesPage() {
  const { data, error } = useApi<{ demo: boolean; items: Item[]; runs: Run[] }>("/api/sources");
  if (!data) return <Loading error={error} />;
  const failures = data.runs.filter((r) => !r.success && r.finished_at);
  return (
    <>
      <DemoBanner show={data.demo} />
      <PageTitle title="Sources">
        Where every series comes from, its license, and two different kinds of age: <strong>data lag</strong> (how
        old the newest period is — often normal for weekly-published data) and <strong>fetch staleness</strong> (how
        long since we last successfully checked).
      </PageTitle>

      <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card title="U.S. Energy Information Administration">
          <p className="text-[13px] ink-2">
            EIA Open Data API v2 — hourly grid data (Form EIA-930), spot and retail prices, weekly gas storage. U.S.
            government data, public domain; please cite EIA.
          </p>
        </Card>
        <Card title="Ember">
          <p className="text-[13px] ink-2">
            Monthly electricity demand by country. Licensed <strong>CC BY 4.0</strong> — attribution: “Ember”.
          </p>
        </Card>
        <Card title="World Bank Pink Sheet">
          <p className="text-[13px] ink-2">
            Monthly commodity prices (coal, European gas, Japan LNG). Licensed <strong>CC BY 4.0</strong> —
            attribution: “World Bank Commodity Price Data (The Pink Sheet)”. Change detection by ETag/Last-Modified,
            else content hash.
          </p>
        </Card>
      </div>

      <Card title="Series" subtitle={`${data.items.length} pinned series; each maps to exactly one upstream id`} className="mb-4">
        <div className="overflow-x-auto">
          <table className="data">
            <thead>
              <tr>
                <th>Series</th>
                <th>Upstream</th>
                <th>Cadence</th>
                <th>Latest period</th>
                <th>Data lag</th>
                <th>Last fetched</th>
                <th>Fetch staleness</th>
                <th>Status</th>
                <th>Expected lag</th>
                <th>License</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((i) => {
                const st = feedState(i);
                return (
                  <tr key={i.id}>
                    <td>
                      {i.title}
                      <div className="text-[11px] muted">{i.unit}{i.local_tz ? ` · day = ${i.local_tz}` : ""}</div>
                    </td>
                    <td className="text-[12px]">
                      <code>{i.route}</code>
                      <div><code>{i.source_code}</code></div>
                    </td>
                    <td>{i.frequency}</td>
                    <td className="whitespace-nowrap">{i.frequency === "hourly" ? dateTime(i.latest_period) : day(i.latest_period, "UTC", true)}</td>
                    <td>{lag(i.data_lag_hours)}</td>
                    <td className="whitespace-nowrap">{i.last_success ? dateTime(i.last_success) : "—"}</td>
                    <td>{lag(i.fetch_staleness_hours)}</td>
                    <td className="whitespace-nowrap">
                      <span aria-hidden style={{ color: st.tone }}>{st.icon}</span> {st.text}
                      {i.last_failure?.error && <div className="max-w-xs text-[11px] muted">{i.last_failure.error}</div>}
                    </td>
                    <td className="max-w-[16rem] text-[12px] ink-2">{i.expected_lag}</td>
                    <td className="text-[12px]">{i.license}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Recent refresh runs" subtitle={failures.length ? `${failures.length} failed in the last ${data.runs.length} runs` : "No recent failures"}>
          <div className="max-h-96 overflow-auto">
            <table className="data">
              <thead>
                <tr>
                  <th>Feed</th>
                  <th>Finished</th>
                  <th>Result</th>
                  <th>Rows</th>
                </tr>
              </thead>
              <tbody>
                {data.runs.map((r, idx) => (
                  <tr key={idx}>
                    <td>{r.source}</td>
                    <td className="whitespace-nowrap">{dateTime(r.finished_at)}</td>
                    <td>
                      <span aria-hidden style={{ color: r.success ? "var(--good)" : "var(--critical)" }}>{r.success ? "✓" : "✕"}</span>{" "}
                      {r.success ? (r.new_period ? "new period" : "ok") : "failed"}
                      {r.error && <div className="max-w-sm text-[11px] muted">{r.error}</div>}
                    </td>
                    <td>{r.rows_upserted.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card title="Honest limits">
          <ul className="list-disc space-y-1.5 pl-4 text-[13px] ink-2">
            {LIMITS.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </Card>
      </div>
    </>
  );
}
