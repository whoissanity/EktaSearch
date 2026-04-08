"""
app/core/config.py
Central settings loaded from .env — import Settings from here everywhere.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Retailer API keys + base URLs
    ryans_api_key: str = ""
    ryans_api_base: str = "https://www.ryanscomputers.com/api"

    startech_api_key: str = ""
    startech_api_base: str = "https://www.startech.com.bd/api"

    techland_api_key: str = ""
    techland_api_base: str = "https://www.techlandbd.com/api"

    skyland_api_key: str = ""
    skyland_api_base: str = "https://www.skyland.com.bd/api"

    ultra_api_key: str = ""
    ultra_api_base: str = "https://www.ultratech.com.bd/api"

    vibe_api_key: str = ""
    vibe_api_base: str = "https://www.vibegaming.com.bd/api"

    potaka_api_key: str = ""
    potaka_api_base: str = "https://www.potakait.com/api"

    blisstyle_api_key: str = ""
    blisstyle_api_base: str = "https://www.blisstyle.com.bd/api"

    # App
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "sqlite+aiosqlite:///./pcbd.db"
    cache_ttl_seconds: int = 900
    cors_origins: str = "http://localhost:5173"
    debug: bool = True

    # Search: live scrape tuning (Tier A/B — for Tier C see search_service module docstring)
    search_shop_timeout_seconds: float = 6.0
    search_max_per_shop: int = 50
    search_max_total: int = 200
    # Per-retailer HTML pagination (page 2+); safety cap to avoid unbounded scrapes
    search_max_retailer_pages: int = 60
    # For category browsing with empty query (PC builder): keep fast and progressive
    search_browse_max_retailer_pages: int = 3
    prewarm_enabled: bool = True
    prewarm_interval_seconds: int = 3600

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
