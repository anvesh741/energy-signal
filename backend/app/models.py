"""Schema. Every datetime column is timezone-aware UTC (SQLModel enforces this on bind)."""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Series(SQLModel, table=True):
    id: str = Field(primary_key=True)
    source: str
    # exactly one upstream series id
    source_code: str
    unit: str
    # hourly | daily | weekly | monthly
    frequency: str
    region: str
    license: str
    expected_lag: str
    # IANA tz; required for electricity
    local_tz: Optional[str] = None
    # seasonal-naive lag for MASE (hourly 168, daily 7, weekly 52); null = plain naive
    mase_season: Optional[int] = None
    route: str = ""
    title: str = ""
    attribution: str = ""
    # grouping for the UI, e.g. "demand", "generation", "price", "storage"
    category: str = ""


class Observation(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("series_id", "ts_utc", name="uq_obs_series_ts"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    series_id: str = Field(index=True, foreign_key="series.id")
    # hourly electricity: period start
    ts_utc: datetime = Field(index=True)
    value: float
    fetched_at: datetime


class DailyRollup(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("series_id", "local_date", name="uq_rollup_series_date"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    series_id: str = Field(index=True, foreign_key="series.id")
    local_date: date = Field(index=True)
    local_tz: str
    total: float
    peak: float
    hour_count: int
    # 23 / 24 / 25 from the tz calendar
    expected_hours: int
    # complete | partial
    quality: str
    dst_flag: bool = False


class Forecast(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "series_id",
            "model",
            "issued_at",
            "target_ts_utc",
            "target_kind",
            name="uq_forecast_issue",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    series_id: str = Field(index=True, foreign_key="series.id")
    # naive | seasonal_naive | seasonal_mean4 | fourier_ar | logret_ar
    model: str
    model_version: str
    issued_at: datetime = Field(index=True)
    target_ts_utc: datetime
    horizon: int
    # hourly | daily_total | daily_peak | daily | weekly | monthly
    target_kind: str
    point: float
    interval_lo: Optional[float] = None
    interval_hi: Optional[float] = None
    interval_level: float = 0.8
    training_window_start: Optional[datetime] = None
    training_window_end: Optional[datetime] = None


class ModelEval(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "series_id",
            "model_version",
            "target_kind",
            "horizon_bucket",
            name="uq_model_eval",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    series_id: str
    # "<MODEL_VERSION>:<model>", or "eia_df" for the operator day-ahead benchmark
    model_version: str
    target_kind: str
    horizon_bucket: str
    mase: Optional[float] = None
    # hourly only: MASE against the lag-24 baseline
    mase_lag24: Optional[float] = None
    mae: Optional[float] = None
    coverage: Optional[float] = None
    interval_level: float = 0.8
    n_origins: int = 0
    backtest_start: Optional[datetime] = None
    backtest_end: Optional[datetime] = None
    evaluated_at: datetime


class Insight(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    rule_id: str
    series_id: str
    rank: int = 0
    issued_at: datetime
    # data date the insight describes ("as of Oct 28")
    as_of_ts: datetime
    cooldown_until: Optional[datetime] = None
    headline: str
    # e.g. "inside" / "below" for band rules; used for hysteresis
    state: str = ""
    inputs_json: str = "{}"


class RefreshRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(index=True)
    started_at: datetime
    finished_at: Optional[datetime] = None
    success: bool = False
    rows_upserted: int = 0
    error: Optional[str] = None
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    content_hash: Optional[str] = None
    # weekly releases: a new period landed during this run
    new_period: bool = False


class SchedulerLease(SQLModel, table=True):
    id: int = Field(default=1, primary_key=True)
    owner: str
    expires_at: datetime
