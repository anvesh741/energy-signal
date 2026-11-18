"use client";

import Link from "next/link";

import { InsightInputs, InsightList } from "@/components/InsightList";
import { Card, DemoBanner, Loading, Stat } from "@/components/ui";
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
      <section className="hero mb-6 grid gap-6 p-6 sm:p-8 lg:grid-cols-[1.15fr_1fr] lg:items-center" style={{ boxShadow: "var(--shadow)" }}>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="chip" style={{ background: "var(--hero-line)", color: "var(--hero-ink)" }}>
              <span className="live-dot" aria-hidden />
              Live · refreshed daily
            </span>
            <span className="chip" style={{ background: "var(--hero-line)", color: "var(--hero-ink-2)" }}>
              EIA · Ember · World Bank
            </span>
          </div>
          <h1 className="mt-5 text-[34px] font-bold leading-[1.08] tracking-tight sm:text-[44px]">
            U.S. energy,
            <br />
            read <span style={{ color: "var(--signal)" }}>honestly.</span>
          </h1>
          <p className="hero-2 mt-4 max-w-xl text-[15px] leading-relaxed">
            Power demand, oil and gas prices and storage in one place. Every number carries the date it describes,
            unfinished days are left out, and every forecast shows how often it has been right.
          </p>
        </div>
        {data.headline && (
          <div
            className="min-w-0 rounded-2xl p-5"
            style={{ background: "rgba(255,255,255,0.06)", border: "1px solid var(--hero-line)" }}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="eyebrow" style={{ color: "var(--signal)" }}>
                What changed
              </span>
              <span className="mono text-[11.5px] hero-2">
                as of{" "}
                {day(data.headline.as_of, data.headline.rule_id === "demand_week" ? "America/New_York" : "UTC")}
              </span>
            </div>
            <p className="mt-3 text-[19px] font-semibold leading-snug">{data.headline.headline}</p>
            <div className="hero-2 mt-2 [&_summary]:!text-[var(--hero-ink-2)] [&_td]:!border-[var(--hero-line)] [&_td]:!text-[var(--hero-ink-2)]">
              <InsightInputs inputs={data.headline.inputs} />
            </div>
          </div>
        )}
      </section>

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
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
        <Card className="lg:self-start" title="Read these numbers with care">
          <ul className="list-disc space-y-2 pl-4 text-[13px] leading-relaxed ink-2">
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
