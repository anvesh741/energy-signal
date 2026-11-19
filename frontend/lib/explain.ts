/** Plain-language readings of the numbers. Kept short and specific; no advice. */

import type { Insight } from "@/lib/types";

/** How big a single move is, in words a non-trader would use. */
export function sizeOfMove(pctChange: number, weekly = false): string {
  const a = Math.abs(pctChange);
  if (a < 0.25) return "barely moved";
  if (a < (weekly ? 1 : 1.5)) return pctChange > 0 ? "edged up" : "edged down";
  if (a < (weekly ? 3 : 4)) return pctChange > 0 ? "rose noticeably" : "fell noticeably";
  return pctChange > 0 ? "jumped" : "dropped sharply";
}

const WHY_IT_MATTERS: Record<string, string> = {
  "eia-wti":
    "Crude oil is what gasoline and diesel are made from, so a lasting move here usually shows up at the pump a few weeks later.",
  "eia-brent": "Brent sets the price for most of the world's oil, including much of what the U.S. imports and exports.",
  "eia-henry-hub":
    "Natural gas heats nearly half of U.S. homes and makes about 40% of the country's electricity, so it feeds into both heating and power bills.",
  "eia-gasoline": "This is the national average price at the pump for regular gasoline.",
  "eia-diesel": "Diesel moves trucks and farm equipment, so it feeds into the cost of shipping almost everything.",
};

export function priceMeaning(id: string, pctChange: number | null, weekly = false): string {
  const why = WHY_IT_MATTERS[id] ?? "";
  if (pctChange == null) return why;
  const size = sizeOfMove(pctChange, weekly);
  const lead =
    size === "barely moved"
      ? "Barely moved since the last reading."
      : `It ${size} since the last reading.`;
  return `${lead} ${why}`;
}

export function demandWeekMeaning(pctChange: number): string {
  const a = Math.abs(pctChange);
  const size =
    a < 1
      ? "about the same as"
      : a < 4
        ? pctChange > 0
          ? "a little more than"
          : "a little less than"
        : pctChange > 0
          ? "clearly more than"
          : "clearly less than";
  return `The Lower 48 states used ${size} the week before. Swings of a few percent are normal and mostly follow the weather: heating in cold snaps, air conditioning in heat waves.`;
}

/** One sentence under each "what changed" headline. */
export function insightMeaning(i: Insight): string {
  switch (i.rule_id) {
    case "price_move":
      if (i.state === "high") return "That's one of the biggest upward moves of the past year for this price.";
      if (i.state === "low") return "That's one of the biggest downward moves of the past year for this price.";
      return "A normal-sized move compared with the past year.";
    case "storage_band":
      if (i.state === "below")
        return "There's less gas in storage than usual for this time of year, which can push winter prices up.";
      if (i.state === "above")
        return "There's more gas in storage than usual for this time of year, which tends to keep prices down.";
      return "Storage is in its normal range for this week of the year, so there's no sign of a shortage or a glut.";
    case "demand_week":
      return "Week-to-week changes of a few percent are normal and mostly follow the weather.";
    default:
      return "";
  }
}

/** "Off by about 4% on average" from a backtest MAE and the typical level. */
export function accuracySentence(
  maePct: number | null,
  coverage: number | null,
  nOrigins: number,
  horizon: string,
): string {
  const parts: string[] = [];
  if (maePct != null)
    parts.push(
      `Looking ${horizon} ahead, this forecast has been off by about ${maePct.toFixed(maePct < 10 ? 1 : 0)}% on average`,
    );
  if (coverage != null)
    parts.push(`the shaded range caught the real value ${Math.round(coverage * 100)} times out of 100`);
  if (!parts.length) return "There isn't enough history yet to say how accurate this forecast is.";
  return `${parts.join(", and ")}. That's measured on ${nOrigins} past forecasts, not assumed.`;
}

export const HORIZON_WORDS: Record<string, string> = {
  "1d": "one day",
  "2-7d": "2 to 7 days",
  "8-14d": "1 to 2 weeks",
  "15-30d": "2 to 4 weeks",
  "1-24h": "up to a day",
  "25-72h": "1 to 3 days",
  "73-168h": "3 to 7 days",
  "1w": "one week",
  "2w": "two weeks",
  "4w": "four weeks",
  "1m": "one month",
};
