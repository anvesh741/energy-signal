"use client";

import Link from "next/link";

import { InsightInputs, InsightList } from "@/components/InsightList";
import { Card, DemoBanner, Loading, PageTitle, Stat } from "@/components/ui";
import { useApi } from "@/lib/api";
import { compact, day, lag, num, pct } from "@/lib/format";
import type { Insight, Latest, Rollup } from "@/lib/types";

type Overview = {
  demo: boolean;
  prices: Latest[];
  retail: Latest[];
  demand_week: {
    recent_start: string;
    recent_end: string;
    prior_start: string;
    prior_end: string;
    recent_total: number;
    prior_total: number;
    pct_change: number;
    local_tz: string;
  } | null;
  demand_latest_day: Rollup | null;
  us48_day_convention: string;
  headline: Insight | null;
  insights: Insight[];
};

function priceTile(p: Latest) {
  const change = p.value != null && p.prior_value ? (p.value / p.prior_value - 1) * 100 : null;
  return (
    <Stat
      key={p.id}
      label={p.title}
      value={p.value == null ? "—" : num(p.value, 2)}
      unit={p.unit}
      delta={
        change == null
          ? null
          : { text: pct(change), dir: change > 0 ? "up" : change < 0 ? "down" : "flat", vs: "vs prior observation" }
      }
      note={
        p.as_of ? (
          <>
            Data as of <strong>{day(p.as_of)}</strong> · {lag(p.data_lag_hours)} behind. Daily values are usually
            published in weekly batches, so up to ~7 days of lag is normal.
          </>
        ) : (
          "No data yet"
        )
      }
    />
  );
}

export default function OverviewPage() {
  const { data, error } = useApi<Overview>("/api/overview");
  if (!data) return <Loading error={error} />;
  const w = data.demand_week;
  return (
    <>
      <DemoBanner show={data.demo} />
      <PageTitle title="Overview">
        Latest oil, gas and US electricity readings, each stamped with the date the data describes — not the time we
        fetched it.
      </PageTitle>

      {data.headline && (
        <Card className="mb-4" title="What changed" subtitle={`as of ${day(data.headline.as_of, data.headline.rule_id === "demand_week" ? "America/New_York" : "UTC")}`}>
          <p className="text-[17px] font-medium leading-snug">{data.headline.headline}</p>
          <InsightInputs inputs={data.headline.inputs} />
        </Card>
      )}

      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {data.prices.map(priceTile)}
        <Stat
          label="US48 demand, last 7 complete days"
          value={w ? compact(w.recent_total / 1e6, 1) : "—"}
          unit="TWh"
          delta={
            w
              ? {
                  text: pct(w.pct_change),
                  dir: w.pct_change > 0 ? "up" : w.pct_change < 0 ? "down" : "flat",
                  vs: `vs ${day(w.prior_start)}–${day(w.prior_end)}`,
                }
              : null
          }
          note={
            w ? (
              <>
                {day(w.recent_start)}–{day(w.recent_end)}. US48 local day = {data.us48_day_convention}. Partial days
                (including today) are left out.
              </>
            ) : (
              "Needs 14 complete local days."
            )
          }
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2" title="Other signals" subtitle="Ranked; each fires only when its series gets a new observation">
          <InsightList items={data.insights} />
        </Card>
        <Card title="Read these numbers with care">
          <ul className="list-disc space-y-1.5 pl-4 text-[13px] ink-2">
            <li>Spot prices are daily values published roughly weekly; they can be ~7 days behind.</li>
            <li>Gasoline, diesel and gas storage are weekly and slip in holiday weeks.</li>
            <li>Hourly demand is revised for 2–3 days after the fact; we overwrite with the latest values.</li>
            <li>Forecasts are statistical baselines, not advice — see <Link className="underline" href="/forecasts">Forecasts</Link>.</li>
          </ul>
        </Card>
      </div>
    </>
  );
}
