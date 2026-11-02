from datetime import datetime, timezone
from typing import Any

import httpx

EMBER_BASE = "https://api.ember-energy.org/v1"


class EmberError(RuntimeError):
    pass


def parse_month(period: str) -> datetime:
    return datetime.strptime(period.strip()[:7], "%Y-%m").replace(tzinfo=timezone.utc)


def rows_from_monthly_payload(payload: Any, iso3: str, field: str = "demand_twh") -> list[dict]:
    """Ember v1 shape: {"stats": {...}, "data": [{"entity_code", "date", "demand_twh", ...}]}."""
    records = payload.get("data") if isinstance(payload, dict) else None
    if records is None:
        raise EmberError("Ember: response has no 'data' array")
    out: list[dict] = []
    for row in records:
        if str(row.get("entity_code", "")).upper() != iso3.upper():
            continue
        period = row.get("date")
        value = row.get(field)
        if period is None or value is None:
            continue
        try:
            out.append({"ts_utc": parse_month(str(period)), "value": float(value)})
        except (TypeError, ValueError):
            continue
    return out


def fetch_monthly_demand(
    client: httpx.Client,
    api_key: str,
    iso3: str,
    start_date: str = "2015-01",
) -> list[dict]:
    if not api_key:
        raise EmberError("EMBER_API_KEY is missing")
    response = client.get(
        f"{EMBER_BASE}/electricity-demand/monthly",
        params={
            "entity_code": iso3,
            "is_aggregate_entity": "false",
            "start_date": start_date,
            "api_key": api_key,
        },
        timeout=60.0,
    )
    if response.status_code != 200:
        raise EmberError(f"Ember HTTP {response.status_code}: {response.text[:300]}")
    return rows_from_monthly_payload(response.json(), iso3)
