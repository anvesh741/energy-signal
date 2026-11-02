import io

import pytest
from openpyxl import Workbook

from app.sources.pink_sheet import PinkSheetError, content_hash, parse_workbook

COLUMNS = {
    "wb-coal-australia": "Coal, Australian",
    "wb-ttf": "Natural gas, Europe",
    "wb-lng-japan": "Liquefied natural gas, Japan",
}


def _workbook(header: list, rows: list[list]) -> bytes:
    """Mirror the real CMO-Historical-Data-Monthly.xlsx layout."""
    wb = Workbook()
    wb.active.title = "AFOSHEET"
    ws = wb.create_sheet("Monthly Prices")
    ws.append(["World Bank Commodity Price Data (The Pink Sheet)"])
    ws.append(["monthly prices in nominal US dollars, 1960 to present"])
    ws.append([None])
    ws.append(["Updated on January 03, 2025"])
    ws.append([None, *header])
    ws.append([None, *["($/mt)"] * len(header)])
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parses_month_rows_and_skips_ellipsis():
    content = _workbook(
        ["Crude oil, Brent", "Coal, Australian", "Natural gas, Europe", "Liquefied natural gas, Japan"],
        [
            ["1960M01", 1.63, "…", 0.40, "…"],
            ["2024M11", 73.4, 140.2, 13.1, 12.9],
            ["2024M12", 73.8, 131.0, 13.9, 13.4],
        ],
    )
    parsed = parse_workbook(content, COLUMNS)
    assert [p["value"] for p in parsed["wb-coal-australia"]] == [140.2, 131.0]
    assert len(parsed["wb-ttf"]) == 3
    assert parsed["wb-lng-japan"][-1]["ts_utc"].month == 12


def test_no_expected_columns_raises_so_nothing_is_written():
    content = _workbook(["Cocoa", "Coffee, Arabica"], [["2024M12", 9.1, 7.2]])
    with pytest.raises(PinkSheetError):
        parse_workbook(content, COLUMNS)


def test_non_xlsx_raises():
    with pytest.raises(PinkSheetError):
        parse_workbook(b"<html>moved</html>", COLUMNS)


def test_hash_is_stable():
    assert content_hash(b"abc") == content_hash(b"abc") != content_hash(b"abd")
