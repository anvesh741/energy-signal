"""Pinned series. Each row maps to exactly one upstream series via source_code.

If an upstream id turns out to differ (confirm in the EIA API browser), change
source_code only — a Series must still map to one upstream series.
"""

from app.models import Series

EIA_LICENSE = "U.S. EIA open data (public domain); cite EIA"
EIA_ATTR = "U.S. Energy Information Administration"
WB_LICENSE = "CC-BY-4.0"
WB_ATTR = "World Bank Commodity Price Data (The Pink Sheet), CC BY 4.0"
EMBER_LICENSE = "CC-BY-4.0"
EMBER_ATTR = "Ember, CC BY 4.0"

SPOT_LAG = "Daily values, usually published in weekly batches (Wednesdays); up to ~7 days behind"
RETAIL_LAG = "Weekly; usually Monday, holiday weeks slip to Tuesday"
STORAGE_LAG = "Weekly (Thursday); holiday weeks shift"
HOURLY_LAG = "Hours; balancing authorities submit late and revise the trailing 48–72h"


def _eia(id, route, code, unit, freq, region, title, lag, category, **kw) -> Series:
    return Series(
        id=id,
        source="eia",
        source_code=code,
        route=route,
        unit=unit,
        frequency=freq,
        region=region,
        license=EIA_LICENSE,
        expected_lag=lag,
        title=title,
        attribution=EIA_ATTR,
        category=category,
        **kw,
    )


def _us48_hourly(id, route, code, title, category, lag=HOURLY_LAG) -> Series:
    return _eia(
        id, route, code, "MWh", "hourly", "US48", title, lag, category,
        local_tz="America/New_York", mase_season=168,
    )


FUELS = {
    "NG": "Natural gas",
    "COL": "Coal",
    "NUC": "Nuclear",
    "WND": "Wind",
    "SUN": "Solar",
    "WAT": "Hydro",
    "OIL": "Petroleum",
    "OTH": "Other",
}

STORAGE_REGIONS = {
    "R48": "Lower 48",
    "R31": "East",
    "R32": "Midwest",
    "R33": "South Central",
    "R34": "Mountain",
    "R35": "Pacific",
}

EMBER_COUNTRIES = {
    "USA": ("United States", "America/New_York"),
    "DEU": ("Germany", "Europe/Berlin"),
    "IND": ("India", "Asia/Kolkata"),
    "CHN": ("China", "Asia/Shanghai"),
    "BRA": ("Brazil", "America/Sao_Paulo"),
    "GBR": ("United Kingdom", "Europe/London"),
    "JPN": ("Japan", "Asia/Tokyo"),
}

CATALOG: list[Series] = [
    _us48_hourly("eia-us48-demand", "electricity/rto/region-data", "US48|D", "US48 electricity demand", "demand"),
    _us48_hourly(
        "eia-us48-df", "electricity/rto/region-data", "US48|DF",
        "US48 day-ahead demand forecast (EIA DF)", "demand_forecast",
        lag="Operator day-ahead forecast; published before the target day",
    ),
    _us48_hourly("eia-us48-ng", "electricity/rto/region-data", "US48|NG", "US48 net generation", "generation"),
    _us48_hourly("eia-us48-ti", "electricity/rto/region-data", "US48|TI", "US48 total interchange", "interchange"),
    *[
        _us48_hourly(
            f"eia-us48-gen-{code.lower()}", "electricity/rto/fuel-type-data", f"US48|{code}",
            f"US48 generation: {name}", "fuel_mix",
        )
        for code, name in FUELS.items()
    ],
    _eia("eia-wti", "petroleum/pri/spt", "RWTC", "$/bbl", "daily", "Cushing, OK", "WTI crude spot", SPOT_LAG, "price"),
    _eia("eia-brent", "petroleum/pri/spt", "RBRTE", "$/bbl", "daily", "Europe", "Brent crude spot", SPOT_LAG, "price"),
    # Henry Hub spot lives under the futures route; RNGC1 is the front-month contract and must not be mixed in.
    _eia(
        "eia-henry-hub", "natural-gas/pri/fut", "RNGWHHD", "$/MMBtu", "daily", "Henry Hub, LA",
        "Henry Hub natural gas spot", SPOT_LAG, "price",
    ),
    _eia(
        "eia-gasoline", "petroleum/pri/gnd", "EMM_EPMR_PTE_NUS_DPG", "$/gal", "weekly", "United States",
        "U.S. regular gasoline, retail", RETAIL_LAG, "retail",
    ),
    _eia(
        "eia-diesel", "petroleum/pri/gnd", "EMD_EPD2D_PTE_NUS_DPG", "$/gal", "weekly", "United States",
        "U.S. No. 2 diesel, retail", RETAIL_LAG, "retail",
    ),
    *[
        _eia(
            f"eia-storage-{code.lower()}", "natural-gas/stor/wkly", f"NW2_EPG0_SWO_{code}_BCF", "Bcf",
            "weekly", name, f"Working gas in storage: {name}", STORAGE_LAG, "storage", mase_season=52,
        )
        for code, name in STORAGE_REGIONS.items()
    ],
    *[
        Series(
            id=id,
            source="worldbank",
            source_code=column,
            route="pink-sheet",
            unit=unit,
            frequency="monthly",
            region=region,
            license=WB_LICENSE,
            expected_lag="Monthly Excel; typically early in the following month",
            mase_season=12,
            title=title,
            attribution=WB_ATTR,
            category="global_price",
        )
        for id, column, unit, region, title in (
            ("wb-coal-australia", "Coal, Australian", "$/mt", "Australia", "Australian thermal coal"),
            ("wb-ttf", "Natural gas, Europe", "$/MMBtu", "Europe (TTF)", "European natural gas (TTF)"),
            ("wb-lng-japan", "Liquefied natural gas, Japan", "$/MMBtu", "Japan", "Japan LNG"),
        )
    ],
    *[
        Series(
            id=f"ember-{iso3.lower()}-demand",
            source="ember",
            source_code=f"{iso3}|demand_twh",
            route="electricity-demand/monthly",
            unit="TWh",
            frequency="monthly",
            region=name,
            license=EMBER_LICENSE,
            expected_lag="Monthly; country data arrives with a lag of one to several months",
            local_tz=tz,
            mase_season=12,
            title=f"{name} electricity demand",
            attribution=EMBER_ATTR,
            category="global_demand",
        )
        for iso3, (name, tz) in EMBER_COUNTRIES.items()
    ],
]

_BY_ID = {s.id: s for s in CATALOG}


def series_by_id(series_id: str) -> Series:
    return _BY_ID[series_id]


def ids_where(**filters) -> list[str]:
    return [
        s.id for s in CATALOG if all(getattr(s, k) == v for k, v in filters.items())
    ]
