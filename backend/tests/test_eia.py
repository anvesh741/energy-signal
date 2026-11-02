import json
from pathlib import Path

from app.sources.eia import build_query, facets_for_series, parse_eia_period, rows_from_response

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_hourly_is_utc_period_start():
    ts = parse_eia_period("2024-01-15T07", "hourly")
    assert ts.hour == 7
    assert ts.utcoffset().total_seconds() == 0


def test_parse_daily():
    assert parse_eia_period("2024-01-15", "daily").day == 15


def test_spot_fixture_skips_empty_values():
    rows = rows_from_response(json.loads((FIXTURES / "eia_spot.json").read_text()), "daily")
    assert [r["value"] for r in rows] == [70.1, 71.4]


def test_hourly_fixture():
    rows = rows_from_response(json.loads((FIXTURES / "eia_hourly.json").read_text()), "hourly")
    assert len(rows) == 2
    assert rows[0]["ts_utc"].hour == 5


def test_facets_region_fuel_and_series():
    assert facets_for_series("electricity/rto/region-data", "US48|D") == {"respondent": ["US48"], "type": ["D"]}
    assert facets_for_series("electricity/rto/fuel-type-data", "US48|SUN") == {
        "respondent": ["US48"],
        "fueltype": ["SUN"],
    }
    # Henry Hub spot: exactly one upstream series, not mixed with RNGC1 futures
    assert facets_for_series("natural-gas/pri/fut", "RNGWHHD") == {"series": ["RNGWHHD"]}


def test_query_paginates_with_offset():
    url = build_query("petroleum/pri/spt", "k", "daily", {"series": ["RWTC"]}, offset=5000)
    assert "offset=5000" in url and "length=5000" in url and "facets%5Bseries%5D%5B%5D=RWTC" in url
