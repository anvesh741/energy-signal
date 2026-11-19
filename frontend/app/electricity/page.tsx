"use client";

import { useEffect, useState } from "react";

import { Columns } from "@/components/Bars";
import { TimeChart } from "@/components/TimeChart";
import { Term } from "@/components/Term";
import { Card, DemoBanner, Empty, Legend, Loading, PageTitle, TableView } from "@/components/ui";
import { useApi } from "@/lib/api";
import { compact, dateTime, day, ms, num } from "@/lib/format";
import type { Bucketed, Latest, Pt, Rollup, SeriesMeta } from "@/lib/types";

type Grid = {
  region: { code: string; name: string };
  regions: { code: string; name: string }[];
  local_tz: string;
  note: string;
  demand: Bucketed[];
  day_ahead: Bucketed[];
  daily: Rollup[];
  fuel_mix: { id: string; fuel: string; days: { date: string; total: number }[] }[];
  latest: Latest;
};
type Global = { series: (SeriesMeta & { points: Pt[] })[] };

const RANGES = [7, 14, 30, 90];
const REGION_KEY = "energysignal:region";
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

const localDate = (x: number, tz: string) => new Date(x).toLocaleDateString("en-CA", { timeZone: tz });
const localHour = (x: number, tz: string) =>
  new Date(x).toLocaleTimeString("en-US", { hour: "numeric", timeZone: tz }).replace(" ", "\u00a0");

/** Three plain sentences about the last complete day: how much, when it peaked, how good the forecast was. */
function PlainSummary({ d }: { d: Grid }) {
  const complete = d.daily.filter((r) => r.quality === "complete");
  const last = complete.at(-1);
  if (!last) return null;
  const weekAgo = complete.find((r) => ms(r.date) === ms(last.date) - 7 * 864e5);
  const where = d.region.code === "US48" ? "The Lower 48 states" : d.region.name;
  const weekday = new Date(ms(last.date)).toLocaleDateString("en-US", { weekday: "long", timeZone: "UTC" });

  const sameDay = mergeHourly(d.demand, d.day_ahead).filter((r) => localDate(r.x, d.local_tz) === last.date);
  const peak = sameDay.reduce<(typeof sameDay)[number] | null>(
    (best, r) => (r.demand != null && (!best || r.demand > best.demand) ? r : best),
    null,
  );
  const paired = sameDay.filter((r) => r.demand != null && r.df != null);
  const missPct = paired.length
    ? (paired.reduce((sum, r) => sum + Math.abs(r.df - r.demand) / r.demand, 0) / paired.length) * 100
    : null;

  const change = weekAgo ? (last.total / weekAgo.total - 1) * 100 : null;
  const vsLastWeek =
    change == null
      ? ""
      : Math.abs(change) < 1
        ? `, about the same as the ${weekday} before`
        : `, ${Math.abs(change).toFixed(1)}% ${change > 0 ? "more" : "less"} than the ${weekday} before`;

  return (
    <div className="plain mb-4">
      <strong>In plain words.</strong> {where} used {compact(last.total / 1e6, 2)} <Term k="TWh" /> of electricity on{" "}
      {weekday}, {day(last.date)}
      {vsLastWeek}.{" "}
      {peak && (
        <>
          Demand peaked around {localHour(peak.x, d.local_tz)} local time at {compact(peak.demand, 1)} <Term k="MWh" /> in
          that hour.{" "}
        </>
      )}
      {missPct != null && (
        <>
          The grid operators&apos; <Term k="day-ahead forecast" /> for that day missed by {missPct.toFixed(1)}% in a
          typical hour.
        </>
      )}
    </div>
  );
}

export default function ElectricityPage() {
  const [days, setDays] = useState(14);
  const [region, setRegionState] = useState("US48");
  useEffect(() => {
    try {
      const saved = localStorage.getItem(REGION_KEY);
      if (saved) setRegionState(saved);
    } catch {}
  }, []);
  const setRegion = (r: string) => {
    setRegionState(r);
    try {
      localStorage.setItem(REGION_KEY, r);
    } catch {}
  };
  const us = useApi<Grid>(`/api/electricity/grid?region=${region}&days=${days}`);
  const global = useApi<Global>("/api/electricity/global");
  const overview = useApi<{ demo: boolean }>("/api/overview");
  const d = us.data;

  return (
    <>
      <DemoBanner show={overview.data?.demo} />
      <PageTitle title="Electricity" eyebrow="Grid · hourly demand">
        How much electricity people are using, hour by hour, for the whole country or your part of it. Data comes from
        the grid operators&apos; reports to the EIA. Unfinished days are marked and left out of totals.
      </PageTitle>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-[13px] ink-2" htmlFor="region">
          Region
          <select id="region" value={region} onChange={(e) => setRegion(e.target.value)}>
            {(d?.regions ?? [{ code: "US48", name: "United States (Lower 48)" }]).map((r) => (
              <option key={r.code} value={r.code}>
                {r.name}
              </option>
            ))}
          </select>
        </label>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Time range">
          {RANGES.map((r) => (
            <button key={r} className="btn" aria-pressed={days === r} onClick={() => setDays(r)}>
              {r} days
            </button>
          ))}
        </div>
      </div>

      {!d ? (
        <Loading error={us.error} />
      ) : (
        <div className="grid grid-cols-1 gap-4">
          <PlainSummary d={d} />
          <Card
            title={`${d.region.code === "US48" ? "U.S. (Lower 48)" : d.region.name} hourly demand`}
            subtitle={`MWh per hour · latest hour ${dateTime(d.latest?.as_of, d.local_tz)} · the last 2–3 days still get corrected`}
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
                xFormat={(x) => day(x, d.local_tz)}
                tipX={(x) => dateTime(x, d.local_tz)}
                height={300}
              />
            ) : (
              <Empty>No hourly data yet.</Empty>
            )}
          </Card>

          <Card
            title="Daily demand by local day"
            subtitle={`Total MWh per local calendar day (${d.local_tz.replace("_", " ")})`}
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
                  <div>
                    Total {compact(Number(r.total), 2)} MWh · peak {compact(Number(r.peak), 1)} MWh/h
                  </div>
                  <div className="ink-2">
                    {r.hour_count}/{r.expected_hours} hours · {r.quality}
                    {r.dst_flag ? " · DST transition day" : ""}
                  </div>
                </>
              )}
            />
            <TableView
              columns={["Local date", "Total MWh", "Peak MWh/h", "Hours", "Expected", "Quality"]}
              rows={d.daily.map((r) => [
                r.date,
                num(r.total, 0),
                num(r.peak, 0),
                r.hour_count,
                r.expected_hours,
                r.quality,
              ])}
            />
          </Card>

          {d.fuel_mix.length > 0 && (
            <Card
              title="U.S. generation by fuel"
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
                              <span
                                className="inline-block h-2 w-2 rounded-sm"
                                style={{ background: FUEL_COLORS[i] }}
                              />
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
          )}
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
                subtitle={
                  last ? `${num(last.value, 1)} TWh in ${day(last.t, "UTC", true).replace(/ \d+,/, "")}` : "No data"
                }
              >
                {s.points.length ? (
                  <TimeChart
                    rows={s.points.slice(-60).map((p) => ({ x: ms(p.t), v: p.value }))}
                    series={[{ key: "v", label: "TWh", color: "var(--series-1)" }]}
                    yFormat={(v) => num(v, 0)}
                    xFormat={(x) =>
                      new Date(x).toLocaleDateString("en-US", { year: "2-digit", month: "short", timeZone: "UTC" })
                    }
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
