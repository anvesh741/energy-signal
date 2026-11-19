"use client";

import Link from "next/link";

import { InsightInputs, InsightList } from "@/components/InsightList";
import { Term } from "@/components/Term";
import { Card, DemoBanner, Loading, Stat } from "@/components/ui";
import { useViewMode } from "@/components/ViewMode";
import { useApi } from "@/lib/api";
import { demandWeekMeaning, insightMeaning, priceMeaning } from "@/lib/explain";
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

function PriceTile({ p }: { p: Latest }) {
  const { mode } = useViewMode();
  const change = p.value != null && p.prior_value ? (p.value / p.prior_value - 1) * 100 : null;
  return (
    <Stat
      label={p.title}
      value={p.value == null ? "—" : num(p.value, 2)}
      unit={p.unit}
      delta={
        change == null
          ? null
          : { text: pct(change), dir: change > 0 ? "up" : change < 0 ? "down" : "flat", vs: "vs prior observation" }
      }
      note={
        !p.as_of ? (
          "No data yet"
        ) : mode === "simple" ? (
          <>
            <span className="ink-2">{priceMeaning(p.id, change)}</span>
            <span className="mt-1.5 block">Price on {day(p.as_of)}; these come out in weekly batches.</span>
          </>
        ) : (
          <>
            Data as of <strong>{day(p.as_of)}</strong> · {lag(p.data_lag_hours)} behind. Daily values are usually
            published in weekly batches, so up to ~7 days of lag is normal.
          </>
        )
      }
    />
  );
}

export default function OverviewPage() {
  const { data, error } = useApi<Overview>("/api/overview");
  const { mode } = useViewMode();
  if (!data) return <Loading error={error} />;
  const w = data.demand_week;
  return (
    <>
      <DemoBanner show={data.demo} />
      <section
        className="hero mb-6 grid gap-6 p-6 sm:p-8 lg:grid-cols-[1.15fr_1fr] lg:items-center"
        style={{ boxShadow: "var(--shadow)" }}
      >
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="chip" style={{ background: "var(--hero-line)", color: "var(--hero-ink)" }}>
              <span className="live-dot" aria-hidden />
              Live · updated every 6 hours
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
            Power demand, oil and gas prices and gas storage in one place, updated every 6 hours from government data.
            Every number says what date it's for, and every forecast shows how often it has been right.
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
                as of {day(data.headline.as_of, data.headline.rule_id === "demand_week" ? "America/New_York" : "UTC")}
              </span>
            </div>
            <p className="mt-3 text-[19px] font-semibold leading-snug">{data.headline.headline}</p>
            <p className="hero-2 mt-2 text-[14px] leading-relaxed">{insightMeaning(data.headline)}</p>
            <div className="hero-2 mt-2 [&_summary]:!text-[var(--hero-ink-2)] [&_td]:!border-[var(--hero-line)] [&_td]:!text-[var(--hero-ink-2)]">
              <InsightInputs inputs={data.headline.inputs} />
            </div>
          </div>
        )}
      </section>

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {data.prices.map((p) => (
          <PriceTile key={p.id} p={p} />
        ))}
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
            w && mode === "simple" ? (
              <>
                <span className="ink-2">{demandWeekMeaning(w.pct_change)}</span>
                <span className="mt-1.5 block">
                  {day(w.recent_start)}–{day(w.recent_end)}, full days only.
                </span>
              </>
            ) : w ? (
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
        <Card
          className="lg:col-span-2"
          title="Other signals"
          subtitle="Ranked; each fires only when its series gets a new observation"
        >
          <InsightList items={data.insights} />
        </Card>
        <Card className="lg:self-start" title="Read these numbers with care">
          <ul className="list-disc space-y-2 pl-4 text-[13px] leading-relaxed ink-2">
            <li>
              Oil and gas prices are daily, but the government publishes them about once a week, so they can be up to a
              week old.
            </li>
            <li>Gasoline, diesel and gas storage come out weekly and slip in holiday weeks.</li>
            <li>
              Hourly power demand gets corrected for 2–3 days after the fact, and today is never complete, so today is
              left out of totals (a <Term k="partial day" />
              ).
            </li>
            <li>
              Forecasts are statistical baselines, not advice — see{" "}
              <Link className="underline" href="/forecasts">
                Forecasts
              </Link>
              .
            </li>
          </ul>
        </Card>
      </div>
    </>
  );
}
