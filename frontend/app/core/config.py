"""Configuración centralizada vía Pydantic Settings."""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings globales cargadas desde .env."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # API
    api_key: str = "finhub-dev-key-change-me"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # DB
    database_url: str = "sqlite:///./finhub.db"

    # FX
    fx_usd_eur: float = 0.92

    # Cache
    cache_ttl_seconds: int = 900

    # LLM (OFF por defecto — la app funciona 100% sin IA)
    llm_enabled: bool = False
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-5"
    llm_api_key: str = ""

    # Scheduler
    scheduler_enabled: bool = True
    watchlist: str = "MSFT,ADBE,NVDA,GOOG,AMZN,CRM,NVO,AAPL,TSLA,META"

    # CORS
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def watchlist_list(self) -> List[str]:
        return [t.strip().upper() for t in self.watchlist.split(",") if t.strip()]

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

