"use client";

import { useState } from "react";

import { Columns } from "@/components/Bars";
import { TimeChart } from "@/components/TimeChart";
import { Card, DemoBanner, Empty, Legend, Loading, PageTitle, TableView } from "@/components/ui";
import { useApi } from "@/lib/api";
import { compact, dateTime, day, ms, num, US48_TZ } from "@/lib/format";
import type { Bucketed, Latest, Pt, Rollup, SeriesMeta } from "@/lib/types";

type US48 = {
  note: string;
  demand: Bucketed[];
  day_ahead: Bucketed[];
  daily: Rollup[];
  fuel_mix: { id: string; fuel: string; days: { date: string; total: number }[] }[];
  latest: Latest;
};
type Global = { series: (SeriesMeta & { points: Pt[] })[] };

const RANGES = [7, 14, 30, 90];
const FUEL_COLORS = Array.from({ length: 8 }, (_, i) => `var(--series-${i + 1})`);

function mergeHourly(demand: Bucketed[], df: Bucketed[]) {
  const rows = new Map<number, Record<string, number> & { x: number }>();
  for (const p of demand) rows.set(ms(p.t), { x: ms(p.t), demand: p.value, lo: p.min, hi: p.max });
  for (const p of df) {
    const x = ms(p.t);
    rows.set(x, { ...(rows.get(x) ?? { x }), df: p.value });
  }
  return [...rows.values()].sort((a, b) => a.x - b.x);
}

export default function ElectricityPage() {
  const [days, setDays] = useState(14);
  const us = useApi<US48>(`/api/electricity/us48?days=${days}`);
  const global = useApi<Global>("/api/electricity/global");
  const overview = useApi<{ demo: boolean }>("/api/overview");
  const d = us.data;

  return (
    <>
      <DemoBanner show={overview.data?.demo} />
      <PageTitle title="Electricity">
        US48 hourly demand from EIA balancing-authority reports. Days are local calendar days in {US48_TZ}; days
        with missing hours are shown as partial and left out of totals, insights and forecasts.
      </PageTitle>

      <div className="mb-3 flex flex-wrap gap-1.5" role="group" aria-label="Time range">
        {RANGES.map((r) => (
          <button key={r} className="btn" aria-pressed={days === r} onClick={() => setDays(r)}>
            {r} days
          </button>
        ))}
      </div>

      {!d ? (
        <Loading error={us.error} />
      ) : (
        <div className="grid grid-cols-1 gap-4">
          <Card
            title="US48 hourly demand"
            subtitle={`MWh per hour · latest hour ${dateTime(d.latest?.as_of)} · recent hours are revised as balancing authorities report`}
            footer="Downsampled on the server with min/max per bucket so peaks survive; the shaded envelope is each bucket's range. Source: U.S. EIA (Form EIA-930)."
          >
            {d.demand.length ? (
              <TimeChart
                rows={mergeHourly(d.demand, d.day_ahead)}
                series={[
                  { key: "range", label: "Hourly range in bucket", color: "var(--series-1)", band: ["lo", "hi"] },
                  { key: "demand", label: "Demand (actual)", color: "var(--series-1)" },
                  { key: "df", label: "Operator day-ahead forecast (EIA DF)", color: "var(--series-2)", width: 1.5 },
                ]}
                yFormat={(v) => compact(v, 0)}
                xFormat={(x) => day(x, US48_TZ)}
                tipX={(x) => dateTime(x)}
                height={300}
              />
            ) : (
              <Empty>No hourly data yet.</Empty>
            )}
          </Card>

          <Card
            title="Daily demand by local day"
            subtitle="Total MWh per America/New_York calendar day"
            footer={d.note}
          >
            <Legend
              items={[
                { label: "Complete day", color: "var(--series-1)", kind: "box" },
                { label: "Partial day (excluded)", color: "var(--muted)", kind: "hatch" },
              ]}
            />
            <Columns
              rows={d.daily.slice(-days).map((r) => ({ label: day(r.date), ...r }))}
              keys={[{ key: "total", label: "Total", color: "var(--series-1)" }]}
              yFormat={(v) => compact(v, 0)}
              hatched={(r) => r.quality === "partial"}
              tooltip={(r) => (
                <>
                  <div className="font-medium">{day(String(r.date), "UTC", true)}</div>
                  <div>Total {compact(Number(r.total), 2)} MWh · peak {compact(Number(r.peak), 1)} MWh/h</div>
                  <div className="ink-2">
                    {r.hour_count}/{r.expected_hours} hours · {r.quality}
                    {r.dst_flag ? " · DST transition day" : ""}
                  </div>
                </>
              )}
            />
            <TableView
              columns={["Local date", "Total MWh", "Peak MWh/h", "Hours", "Expected", "Quality"]}
              rows={d.daily.map((r) => [r.date, num(r.total, 0), num(r.peak, 0), r.hour_count, r.expected_hours, r.quality])}
            />
          </Card>

          <Card
            title="US48 generation by fuel"
            subtitle="GWh per complete local day (EIA hourly fuel-type data)"
            footer="Source: U.S. EIA (Form EIA-930). Fixed color per fuel."
          >
            {d.fuel_mix.some((f) => f.days.length) ? (
              (() => {
                const byDate = new Map<string, Record<string, number | string>>();
                for (const f of d.fuel_mix)
                  for (const r of f.days) {
                    const row = byDate.get(r.date) ?? { date: r.date, label: day(r.date) };
                    row[f.id] = r.total / 1000;
                    byDate.set(r.date, row);
                  }
                const rows = [...byDate.values()].sort((a, b) => String(a.date).localeCompare(String(b.date)));
                return (
                  <Columns
                    rows={rows as never}
                    keys={d.fuel_mix.map((f, i) => ({ key: f.id, label: f.fuel, color: FUEL_COLORS[i] }))}
                    yFormat={(v) => compact(v, 0)}
                    height={260}
                    tooltip={(r) => (
                      <>
                        <div className="mb-1 font-medium">{day(String(r.date), "UTC", true)}</div>
                        {d.fuel_mix.map((f, i) => (
                          <div key={f.id} className="flex items-center gap-1.5">
                            <span className="inline-block h-2 w-2 rounded-sm" style={{ background: FUEL_COLORS[i] }} />
                            <span className="ink-2">{f.fuel}</span>
                            <span className="ml-auto pl-3 tabular">{num(Number(r[f.id] ?? 0), 0)} GWh</span>
                          </div>
                        ))}
                      </>
                    )}
                  />
                );
              })()
            ) : (
              <Empty>No fuel-type data yet.</Empty>
            )}
          </Card>
        </div>
      )}

      <h2 className="mb-1 mt-8 text-[17px] font-semibold">Global electricity demand (monthly)</h2>
      <p className="mb-3 text-[13px] ink-2">
        Ember monthly country data, each panel on its own scale (countries differ ~30× in size). Monthly data arrives
        with a lag of one to several months.
      </p>
      {!global.data ? (
        <Loading error={global.error} />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {global.data.series.map((s) => {
            const last = s.points.at(-1);
            return (
              <Card
                key={s.id}
                title={s.region}
                subtitle={last ? `${num(last.value, 1)} TWh in ${day(last.t, "UTC", true).replace(/ \d+,/, "")}` : "No data"}
              >
                {s.points.length ? (
                  <TimeChart
                    rows={s.points.slice(-60).map((p) => ({ x: ms(p.t), v: p.value }))}
                    series={[{ key: "v", label: "TWh", color: "var(--series-1)" }]}
                    yFormat={(v) => num(v, 0)}
                    xFormat={(x) => new Date(x).toLocaleDateString("en-US", { year: "2-digit", month: "short", timeZone: "UTC" })}
                    height={140}
                  />
                ) : (
                  <Empty>No data</Empty>
                )}
              </Card>
            );
          })}
        </div>
      )}
      <p className="mt-3 text-[12px] muted">Source: Ember, licensed CC BY 4.0.</p>
    </>
  );
}
