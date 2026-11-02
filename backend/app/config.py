from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        extra="ignore",
    )

    eia_api_key: str = ""
    ember_api_key: str = ""
    pink_sheet_url: str = (
        "https://thedocs.worldbank.org/en/doc/"
        "5d903e848db1d1b83e0ec8f744e55570-0350012021/related/"
        "CMO-Historical-Data-Monthly.xlsx"
    )
    database_url: str = f"sqlite:///{DATA_DIR / 'energysignal.db'}"
    scheduler_enabled: bool = True
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    forecast_retention_days: int = 90


settings = Settings()
DATA_DIR.mkdir(parents=True, exist_ok=True)
