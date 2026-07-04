from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Application-level configuration driven by environment variables."""

    model_config = SettingsConfigDict(env_prefix="VIBEOPS_", case_sensitive=False)

    default_model: str = "gpt-4o-mini"
    default_cost_cap_usd: float = 200.0
    log_level: str = "INFO"
    langgraph_recursion_limit: int = 25

    # Remote Terraform state (issue #3).
    # When ``VIBEOPS_TF_STATE_BUCKET`` names a GCS bucket, generated Terraform uses a
    # ``backend "gcs"`` block so state survives process/session loss (and ``destroy`` keeps
    # working). When unset, state stays in the ephemeral local work dir and a warning is logged.
    tf_state_bucket: str | None = None
    # Base object prefix under which each deployment's state lives, e.g.
    # ``gs://<bucket>/<tf_state_prefix>/<project>/<uuid>/default.tfstate``.
    tf_state_prefix: str = "vibeops"
