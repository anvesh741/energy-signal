export type SeriesMeta = {
  id: string;
  title: string;
  unit: string;
  frequency: string;
  region: string;
  source: string;
  source_code: string;
  license: string;
  attribution: string;
  expected_lag: string;
  local_tz: string | null;
  category: string;
};

export type Latest = SeriesMeta & {
  value: number | null;
  prior_value?: number | null;
  as_of: string | null;
  data_lag_hours?: number | null;
  fetched_at?: string | null;
};

export type Insight = {
  rule_id: string;
  series_id: string;
  headline: string;
  rank: number;
  state: string;
  as_of: string;
  issued_at: string;
  inputs: string;
};

export type Rollup = {
  date: string;
  total: number;
  peak: number;
  hour_count: number;
  expected_hours: number;
  quality: "complete" | "partial";
  dst_flag: boolean;
};

export type Bucketed = { t: string; min: number; max: number; value: number };
export type Pt = { t: string; value: number };
