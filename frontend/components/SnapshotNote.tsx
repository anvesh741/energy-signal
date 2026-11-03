"use client";

import { IS_STATIC, useApi } from "@/lib/api";
import { dateTime } from "@/lib/format";

/** Static builds only: when the JSON snapshot was taken (lags shown elsewhere are as of then). */
export function SnapshotNote() {
  const { data } = useApi<{ built_at: string }>(IS_STATIC ? "/api/meta" : null);
  if (!data) return null;
  return <> Snapshot updated {dateTime(data.built_at)}; refreshed daily.</>;
}
