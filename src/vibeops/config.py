from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Application-level configuration driven by environment variables."""

    model_config = SettingsConfigDict(env_prefix="VIBEOPS_", case_sensitive=False)

    default_model: str = "gpt-4o-mini"
    default_cost_cap_usd: float = 200.0
    log_level: str = "INFO"
    langgraph_recursion_limit: int = 25
