from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from vibeops.core.gcp_context import GcpContext
from vibeops.cost.infracost import run_infracost
from vibeops.models.iac import CostEstimate
from vibeops.models.spec import DeploymentSpec

logger = logging.getLogger(__name__)

_ZERO_ESTIMATE = CostEstimate(
    hourly_usd=0.0,
    monthly_usd=0.0,
    source="price_table",
    confidence="low",
    notes=["Cost estimation unavailable — no infracost binary or GCP context provided."],
    estimated_at=datetime.now(UTC),
)


def estimate(
    tf_dir: Path,
    spec: DeploymentSpec,
    ctx: GcpContext | None,
) -> CostEstimate:
    """Try Infracost first; fall back to the GCP price table; return zero estimate if both fail."""
    result = run_infracost(tf_dir)
    if result is not None:
        return result

    if ctx is not None:
        try:
            from vibeops.cost.price_table import estimate_from_price_table

            return estimate_from_price_table(spec, ctx)
        except Exception as exc:
            logger.warning("Price-table estimation failed: %s", exc)

    return _ZERO_ESTIMATE
