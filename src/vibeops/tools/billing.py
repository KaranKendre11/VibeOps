from __future__ import annotations

from vibeops.core.gcp_context import GcpContext
from vibeops.core.prices import MONTHLY_HOURS, estimate_hourly
from vibeops.models.results import PriceEstimate


def estimate_price(
    ctx: GcpContext,
    machine_type: str,
    zone: str,
    gpu_type: str,
    gpu_count: int,
    preemptible: bool,
) -> PriceEstimate:
    _ = ctx  # GcpContext available for future live-pricing calls in M3
    hourly = estimate_hourly(machine_type, gpu_type, gpu_count, preemptible)
    monthly = round(hourly * MONTHLY_HOURS, 2)
    return PriceEstimate(
        machine_type=machine_type,
        zone=zone,
        gpu_type=gpu_type,
        gpu_count=gpu_count,
        preemptible=preemptible,
        hourly_usd=hourly,
        monthly_usd_est=monthly,
    )
