from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AI Price Radar API"
    database_url: str = "sqlite:///./price_radar.db"
    admin_api_key: str = "replace-with-a-long-random-string"
    web_origin: str = "http://localhost:3000"
    public_site_url: str = "http://localhost:3000"
    seed_demo_data: bool = False
    stale_offer_hours: int = Field(default=72, ge=1, le=24 * 30)
    report_rate_limit_count: int = Field(default=5, ge=1, le=100)
    report_rate_limit_window_seconds: int = Field(default=3600, ge=60, le=24 * 60 * 60)
    trusted_proxy_cidrs: str = ""
    shop_intake_admin_emails: str = "admin@example.invalid"
    intake_worker_key: str = ""
    detector_worker_key: str = ""
    intake_lease_seconds: int = Field(default=900, ge=60, le=24 * 60 * 60)
    resend_api_key: str = ""
    resend_from: str = ""
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_starttls: bool = True
    smtp_timeout_seconds: int = Field(default=20, ge=1, le=120)


@lru_cache
def get_settings() -> Settings:
    return Settings()
