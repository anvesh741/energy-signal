"use client";

import { useState } from "react";

import { InsightList } from "@/components/InsightList";
import { TimeChart } from "@/components/TimeChart";
import { Card, DemoBanner, Empty, Loading, PageTitle, Stat, TableView } from "@/components/ui";
import { useApi } from "@/lib/api";
import { day, lag, ms, num, pct } from "@/lib/format";
import type { Insight, Latest, Pt, SeriesMeta } from "@/lib/types";

type Packed = Latest & { points: Pt[] };
type Fuels = { spot: Packed[]; retail: Packed[]; global: Packed[]; insights: Insight[] };
type Storage = {
  series: SeriesMeta;
  regions: { id: string; region: string }[];
  band: { week: number; min: number; max: number; mean: number; n_years: number; years_used: string[]; current: number | null } | null;
  history: { t: string; value: number; min: number | null; max: number | null; mean: number | null; n_years: number }[];
  method: string;
};

const monthFmt = (x: number) => new Date(x).toLocaleDateString("en-US", { month: "short", year: "2-digit", timeZone: "UTC" });

/** One chart per unit; series in it share the axis. */
function PriceChart({ items, digits = 2 }: { items: Packed[]; digits?: number }) {
  const rows = new Map<number, Record<string, number> & { x: number }>();
  items.forEach((s, i) => {
    for (const p of s.points) {
      const x = ms(p.t);
      rows.set(x, { ...(rows.get(x) ?? { x }), [`s${i}`]: p.value });
    }
  });
  if (!rows.size) return <Empty>No data yet.</Empty>;
  return (
    <TimeChart
      rows={[...rows.values()].sort((a, b) => a.x - b.x)}
      series={items.map((s, i) => ({ key: `s${i}`, label: s.title, color: `var(--series-${i + 1})` }))}
      yFormat={(v) => num(v, digits)}
      xFormat={monthFmt}
      tipX={(x) => day(x, "UTC", true)}
    />
  );
}

function lagNote(items: Packed[]) {
  return items
    .filter((s) => s.as_of)
    .map((s) => `${s.title}: data as of ${day(s.as_of)} (${lag(s.data_lag_hours)} behind)`)
    .join(" · ");
}

export default function FuelsPage() {
  const fuels = useApi<Fuels>("/api/fuels");
  const [region, setRegion] = useState("eia-storage-r48");
  const storage = useApi<Storage>(`/api/fuels/storage?region=${region}`);
  const overview = useApi<{ demo: boolean }>("/api/overview");
  const f = fuels.data;
  const s = storage.data;

  return (
    <>
      <DemoBanner show={overview.data?.demo} />
      <PageTitle title="Fuels">
        Oil and natural-gas spot prices, U.S. retail fuel, working gas in storage against its 5-year range, and
        monthly international benchmarks.
      </PageTitle>

      {!f ? (
        <Loading error={fuels.error} />
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card
            title="Crude oil spot"
            subtitle="$/bbl, daily"
            footer={`Daily values usually published weekly (Wednesdays). ${lagNote(f.spot.slice(0, 2))}. Source: U.S. EIA.`}
          >
            <PriceChart items={f.spot.slice(0, 2)} />
          </Card>
          <Card
            title="Henry Hub natural gas spot"
            subtitle="$/MMBtu, daily (spot, not futures)"
            footer={`${lagNote(f.spot.slice(2))}. Source: U.S. EIA.`}
          >
            <PriceChart items={f.spot.slice(2)} />
          </Card>
          <Card
            title="U.S. retail gasoline and diesel"
            subtitle="$/gal, weekly"
            footer={`Weekly, usually Monday; holiday weeks slip to Tuesday. ${lagNote(f.retail)}. Source: U.S. EIA.`}
          >
            <PriceChart items={f.retail} digits={2} />
          </Card>
          <Card title="Fuel signals" subtitle="Latest per rule, ranked · as-of = data date">
            <InsightList items={f.insights} />
          </Card>
        </div>
      )}

      <h2 className="mb-3 mt-8 text-[17px] font-semibold">Working gas in storage</h2>
      {!s ? (
        <Loading error={storage.error} />
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div className="grid grid-cols-1 content-start gap-3">
            <label className="text-[13px] ink-2">
              Region{" "}
              <select value={region} onChange={(e) => setRegion(e.target.value)}>
                {s.regions.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.region}
                  </option>
                ))}
              </select>
            </label>
            {s.band && s.band.current != null ? (
              <Stat
                label={`${s.series.region}, week ${s.band.week}`}
                value={num(s.band.current, 0)}
                unit="Bcf"
                delta={{
                  text: pct((s.band.current / s.band.mean - 1) * 100),
                  dir: s.band.current >= s.band.mean ? "up" : "down",
                  vs: "vs 5-year mean",
                }}
                note={`5-year range ${num(s.band.min, 0)}–${num(s.band.max, 0)} Bcf from ${s.band.years_used.join(", ")}. Data as of ${day(s.history.at(-1)?.t)}.`}
              />
            ) : (
              <Stat label="Storage" value="—" note="Needs 5+ years of weekly history (backfilled on first run)." />
            )}
          </div>
          <Card className="lg:col-span-2" title={`${s.series.title}`} subtitle="Bcf, weekly, last two years" footer={`${s.method} Source: U.S. EIA.`}>
            {s.history.length ? (
              <>
                <TimeChart
                  rows={s.history.map((h) => ({ x: ms(h.t), v: h.value, lo: h.min, hi: h.max, mean: h.mean }))}
                  series={[
                    { key: "band", label: "5-year range", color: "var(--series-1)", band: ["lo", "hi"] },
                    { key: "mean", label: "5-year mean", color: "var(--muted)", width: 1.5 },
                    { key: "v", label: "This year", color: "var(--series-1)" },
                  ]}
                  yFormat={(v) => num(v, 0)}
                  xFormat={monthFmt}
                  tipX={(x) => `Week ending ${day(x, "UTC", true)}`}
                />
                <TableView
                  columns={["Week ending", "Bcf", "5-yr min", "5-yr max", "5-yr mean", "Years"]}
                  rows={s.history.map((h) => [h.t, num(h.value, 0), num(h.min, 0), num(h.max, 0), num(h.mean, 0), h.n_years])}
                />
              </>
            ) : (
              <Empty>No storage data yet.</Empty>
            )}
          </Card>
        </div>
      )}

      {f && (
        <>
          <h2 className="mb-3 mt-8 text-[17px] font-semibold">International benchmarks (monthly)</h2>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card title="Australian thermal coal" subtitle="$/mt, monthly average" footer="World Bank Commodity Price Data (The Pink Sheet), CC BY 4.0.">
              <PriceChart items={f.global.filter((g) => g.unit === "$/mt")} digits={0} />
            </Card>
            <Card title="European gas (TTF) and Japan LNG" subtitle="$/MMBtu, monthly average" footer="World Bank Commodity Price Data (The Pink Sheet), CC BY 4.0. Monthly Excel, typically updated early in the following month.">
              <PriceChart items={f.global.filter((g) => g.unit === "$/MMBtu")} />
            </Card>
          </div>
        </>
      )}
    </>
  );
}
