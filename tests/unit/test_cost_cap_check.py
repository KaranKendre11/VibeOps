from __future__ import annotations

from datetime import UTC, datetime

import pytest

from vibeops.models.iac import CostEstimate


def _estimate(monthly_usd: float) -> CostEstimate:
    return CostEstimate(
        hourly_usd=monthly_usd / 730.0,
        monthly_usd=monthly_usd,
        source="cloud_catalog",
        confidence="medium",
        estimated_at=datetime.now(UTC),
    )


def _exceeds_cap(estimate: CostEstimate, cap: float) -> bool:
    return estimate.monthly_usd > cap


class TestCostCapCheck:
    def test_estimate_above_cap_exceeds(self) -> None:
        assert _exceeds_cap(_estimate(150.0), cap=100.0) is True

    def test_estimate_below_cap_does_not_exceed(self) -> None:
        assert _exceeds_cap(_estimate(99.99), cap=100.0) is False

    def test_estimate_exactly_at_cap_does_not_exceed(self) -> None:
        """Strict >: exactly at cap is NOT exceeded."""
        assert _exceeds_cap(_estimate(100.0), cap=100.0) is False

    def test_estimate_zero_does_not_exceed_any_positive_cap(self) -> None:
        assert _exceeds_cap(_estimate(0.0), cap=1.0) is False

    def test_estimate_large_exceeds_small_cap(self) -> None:
        assert _exceeds_cap(_estimate(10000.0), cap=200.0) is True

    def test_fractional_overage(self) -> None:
        assert _exceeds_cap(_estimate(200.01), cap=200.0) is True

    def test_fractional_under(self) -> None:
        assert _exceeds_cap(_estimate(199.99), cap=200.0) is False
