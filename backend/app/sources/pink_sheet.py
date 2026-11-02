"""World Bank Pink Sheet (CMO-Historical-Data-Monthly.xlsx).

Layout of the "Monthly Prices" sheet: a header row of commodity names
("Coal, Australian", "Natural gas, Europe", "Liquefied natural gas, Japan", ...),
a units row, then one row per month with "1960M01"-style labels in column A.
Missing values are "…".
"""

import hashlib
import io
from datetime import datetime, timezone
from typing import Any

import httpx
from openpyxl import load_workbook

SHEET = "Monthly Prices"


class PinkSheetError(RuntimeError):
    pass


def _norm(text: Any) -> str:
    return " ".join(str(text).strip().lower().split())


def parse_month_label(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return datetime(value.year, value.month, 1, tzinfo=timezone.utc)
    text = str(value or "").strip()
    if len(text) == 7 and text[4] == "M":
        try:
            return datetime(int(text[:4]), int(text[5:]), 1, tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def parse_workbook(content: bytes, columns: dict[str, str]) -> dict[str, list[dict]]:
    """columns: series_id -> commodity header text. Raises if none are found."""
    try:
        wb = load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    except Exception as exc:  # noqa: BLE001 - corrupt/HTML response
        raise PinkSheetError(f"Pink Sheet: not a readable xlsx ({exc})") from exc
    if SHEET not in wb.sheetnames:
        raise PinkSheetError(f"Pink Sheet: sheet {SHEET!r} missing; found {wb.sheetnames}")
    rows = list(wb[SHEET].iter_rows(values_only=True))

    wanted = {_norm(header): sid for sid, header in columns.items()}
    header_idx = None
    col_for: dict[str, int] = {}
    for i, row in enumerate(rows[:30]):
        hits = {wanted[_norm(c)]: j for j, c in enumerate(row) if c and _norm(c) in wanted}
        if hits:
            header_idx, col_for = i, hits
            break
    if header_idx is None:
        raise PinkSheetError(
            "Pink Sheet: no expected columns found (" + ", ".join(columns.values()) + ")"
        )

    found: dict[str, list[dict]] = {sid: [] for sid in col_for}
    for row in rows[header_idx + 1 :]:
        if not row:
            continue
        month = parse_month_label(row[0])
        if month is None:
            continue
        for sid, j in col_for.items():
            cell = row[j] if j < len(row) else None
            if isinstance(cell, (int, float)):
                found[sid].append({"ts_utc": month, "value": float(cell)})
    found = {sid: pts for sid, pts in found.items() if pts}
    if not found:
        raise PinkSheetError("Pink Sheet: expected columns present but contain no numeric months")
    return found


def content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def fetch_workbook(
    client: httpx.Client,
    url: str,
    etag: str | None = None,
    last_modified: str | None = None,
) -> tuple[bytes | None, str | None, str | None]:
    """Conditional GET. Returns (content or None if 304, etag, last_modified)."""
    headers = {}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    response = client.get(url, headers=headers, timeout=90.0, follow_redirects=True)
    if response.status_code == 304:
        return None, etag, last_modified
    if response.status_code != 200:
        raise PinkSheetError(f"Pink Sheet HTTP {response.status_code}")
    return response.content, response.headers.get("ETag"), response.headers.get("Last-Modified")
