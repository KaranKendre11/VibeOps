from __future__ import annotations

from unittest.mock import MagicMock

from vibeops.core.gcp_context import GcpContext
from vibeops.models.results import PriceEstimate
from vibeops.tools.billing import estimate_price


def _ctx() -> GcpContext:
    return MagicMock(spec=GcpContext)


def test_returns_price_estimate() -> None:
    result = estimate_price(_ctx(), "n1-standard-4", "us-central1-a", "nvidia-tesla-t4", 1, False)
    assert isinstance(result, PriceEstimate)
    assert result.hourly_usd > 0
    assert result.monthly_usd_est > 0


def test_monthly_is_730x_hourly() -> None:
    result = estimate_price(_ctx(), "n1-standard-4", "us-central1-a", "nvidia-tesla-t4", 1, False)
    assert abs(result.monthly_usd_est - result.hourly_usd * 730) < 0.01


def test_preemptible_is_cheaper() -> None:
    full = estimate_price(_ctx(), "n1-standard-4", "us-central1-a", "nvidia-tesla-t4", 1, False)
    preemptible = estimate_price(_ctx(), "n1-standard-4", "us-central1-a", "nvidia-tesla-t4", 1, True)
    assert preemptible.hourly_usd < full.hourly_usd


def test_more_gpus_cost_more() -> None:
    one = estimate_price(_ctx(), "n1-standard-4", "us-central1-a", "nvidia-tesla-t4", 1, False)
    two = estimate_price(_ctx(), "n1-standard-4", "us-central1-a", "nvidia-tesla-t4", 2, False)
    assert two.hourly_usd > one.hourly_usd


def test_passthrough_fields() -> None:
    result = estimate_price(_ctx(), "n1-standard-8", "europe-west4-a", "nvidia-l4", 2, True)
    assert result.machine_type == "n1-standard-8"
    assert result.zone == "europe-west4-a"
    assert result.gpu_type == "nvidia-l4"
    assert result.gpu_count == 2
    assert result.preemptible is True
