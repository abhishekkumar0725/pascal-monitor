from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_toml_defaults() -> dict[str, Any]:
    """Load defaults from config.toml if it exists."""
    config_path = Path(__file__).parent.parent / "config.toml"
    if config_path.exists():
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        return {
            "port": data.get("app", {}).get("port", 8000),
            "timezone": data.get("app", {}).get("timezone", "America/New_York"),
            "log_users": data.get("app", {}).get("log_users", ["Abhishek"]),
            "csv_export_dir": data.get("paths", {}).get("csv_export_dir", ".."),
            "legacy_csv_dir": data.get("paths", {}).get("legacy_csv_dir", ".."),
        }
    return {}


class Settings(BaseSettings):
    """Application settings, loaded from env vars with config.toml defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "sqlite+aiosqlite:///pascal.db"

    # App settings
    port: int = 1331
    timezone: str = "America/New_York"
    log_users: list[str] = ["Abhishek", "Vivian", "Other"]

    # Paths (relative to web/ directory or absolute)
    csv_export_dir: str = ".."
    legacy_csv_dir: str = ".."

    # Auth (v2)
    app_token: str | None = None

    def __init__(self, **kwargs: Any) -> None:
        toml_defaults = _load_toml_defaults()
        for key, value in toml_defaults.items():
            if key not in kwargs:
                kwargs[key] = value
        super().__init__(**kwargs)

    @property
    def csv_export_path(self) -> Path:
        """Resolved path for CSV exports."""
        p = Path(self.csv_export_dir)
        if not p.is_absolute():
            p = Path(__file__).parent.parent / p
        return p.resolve()

    @property
    def legacy_csv_path(self) -> Path:
        """Resolved path for legacy CSV imports."""
        p = Path(self.legacy_csv_dir)
        if not p.is_absolute():
            p = Path(__file__).parent.parent / p
        return p.resolve()


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


settings = get_settings()
