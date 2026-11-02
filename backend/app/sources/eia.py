import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

EIA_BASE = "https://api.eia.gov/v2"
PAGE_SIZE = 5000
THROTTLE_SECONDS = 0.4
RETRIES = 3


class EiaError(RuntimeError):
    pass


def parse_eia_period(period: str, frequency: str) -> datetime:
    """EIA periods -> aware UTC. Hourly periods are UTC period starts ("2024-01-15T07")."""
    period = period.strip()
    if frequency == "hourly":
        raw = period.replace("Z", "")
        if "T" in raw:
            date_part, hour_part = raw.split("T", 1)
            hour = int(hour_part[:2])
            dt = datetime.fromisoformat(date_part)
            return dt.replace(hour=hour, tzinfo=timezone.utc)
        return datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
    if frequency == "monthly":
        return datetime.strptime(period[:7], "%Y-%m").replace(tzinfo=timezone.utc)
    if frequency == "annual":
        return datetime.strptime(period[:4], "%Y").replace(tzinfo=timezone.utc)
    # daily / weekly YYYY-MM-DD
    return datetime.fromisoformat(period[:10]).replace(tzinfo=timezone.utc)


def build_query(
    route: str,
    api_key: str,
    frequency: str,
    facets: dict[str, list[str]],
    start: str | None = None,
    end: str | None = None,
    offset: int = 0,
    length: int = PAGE_SIZE,
) -> str:
    params: list[tuple[str, str]] = [
        ("api_key", api_key),
        ("frequency", frequency),
        ("data[0]", "value"),
        ("sort[0][column]", "period"),
        ("sort[0][direction]", "asc"),
        ("offset", str(offset)),
        ("length", str(length)),
    ]
    if start:
        params.append(("start", start))
    if end:
        params.append(("end", end))
    for facet, values in facets.items():
        for value in values:
            params.append((f"facets[{facet}][]", value))
    return f"{EIA_BASE}/{route}/data/?{urlencode(params)}"


def rows_from_response(payload: dict[str, Any], frequency: str) -> list[dict]:
    data = (payload.get("response") or {}).get("data") or []
    out = []
    for row in data:
        period = row.get("period")
        value = row.get("value")
        if period is None or value is None or value == "":
            continue
        try:
            ts = parse_eia_period(str(period), frequency)
            val = float(value)
        except (TypeError, ValueError):
            continue
        out.append({"ts_utc": ts, "value": val})
    return out


def facets_for_series(route: str, source_code: str) -> dict[str, list[str]]:
    if route == "electricity/rto/region-data":
        respondent, type_code = source_code.split("|", 1)
        return {"respondent": [respondent], "type": [type_code]}
    if route == "electricity/rto/fuel-type-data":
        respondent, fuel = source_code.split("|", 1)
        return {"respondent": [respondent], "fueltype": [fuel]}
    return {"series": [source_code]}


def _get_json(client: httpx.Client, url: str) -> dict:
    for attempt in range(RETRIES):
        response = client.get(url, timeout=60.0)
        if response.status_code == 200:
            payload = response.json()
            if payload.get("error"):
                raise EiaError(str(payload["error"])[:400])
            return payload
        if response.status_code in (429, 500, 502, 503, 504) and attempt < RETRIES - 1:
            time.sleep(2 ** attempt * 2)
            continue
        # never echo the key back into RefreshRun.error
        raise EiaError(f"EIA HTTP {response.status_code}: {response.text[:300]}")
    raise EiaError("EIA: retries exhausted")


def fetch_series(
    client: httpx.Client,
    api_key: str,
    route: str,
    source_code: str,
    frequency: str,
    start: str | None = None,
    end: str | None = None,
) -> list[dict]:
    """Paginate past the 5,000-row cap, throttled between pages."""
    if not api_key:
        raise EiaError("EIA_API_KEY is missing")
    facets = facets_for_series(route, source_code)
    offset = 0
    all_rows: list[dict] = []
    while True:
        url = build_query(route, api_key, frequency, facets, start=start, end=end, offset=offset)
        payload = _get_json(client, url)
        response = payload.get("response") or {}
        page_len = len(response.get("data") or [])
        all_rows.extend(rows_from_response(payload, frequency))
        total = int(response.get("total") or 0)
        offset += PAGE_SIZE
        if page_len < PAGE_SIZE or offset >= total:
            break
        time.sleep(THROTTLE_SECONDS)
    return all_rows
