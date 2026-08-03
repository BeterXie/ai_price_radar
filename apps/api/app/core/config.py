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
    discovery_worker_key: str = ""
    intake_lease_seconds: int = Field(default=900, ge=60, le=24 * 60 * 60)
    discovery_enabled: bool = True
    discovery_sources: str = "seed,bing,github,commoncrawl"
    discovery_max_raw_urls: int = Field(default=2000, ge=1, le=10_000)
    discovery_max_new_candidates: int = Field(default=1000, ge=1, le=10_000)
    discovery_max_processed_candidates: int = Field(default=3000, ge=1, le=10_000)
    discovery_reverify_stale_hours: float = Field(default=24, ge=1, le=24 * 30)
    discovery_bing_pages: int = Field(default=5, ge=1, le=20)
    discovery_bing_count: int = Field(default=30, ge=10, le=50)
    discovery_bing_delay_seconds: float = Field(default=2.0, ge=0, le=60)
    discovery_github_pages: int = Field(default=3, ge=1, le=10)
    discovery_github_count: int = Field(default=100, ge=1, le=100)
    discovery_github_max_candidates: int = Field(default=300, ge=0, le=500)
    discovery_commoncrawl_indexes: int = Field(default=2, ge=1, le=10)
    discovery_commoncrawl_max_urls: int = Field(default=500, ge=1, le=2000)
    discovery_request_interval_seconds: float = Field(default=2.0, ge=0.5, le=60)
    discovery_dujiao_auto_approve: bool = True
    discovery_woocommerce_auto_approve: bool = True
    discovery_schema_auto_approve: bool = False
    discovery_merchant_auto_approve: bool = False
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
