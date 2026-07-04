from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibeops.core.gcp_context import GcpContext
from vibeops.cost import estimate
from vibeops.models.iac import CostEstimate
from vibeops.models.spec import ComputeSpec, DeploymentSpec, GpuType, NetworkSpec, StorageSpec


def _spec() -> DeploymentSpec:
    return DeploymentSpec(
        compute=ComputeSpec(
            machine_type="n1-standard-8",
            zone="us-central1-a",
            gpu_type=GpuType.T4,
            gpu_count=1,
            preemptible=False,
        ),
        storage=StorageSpec(
            disk_size_gb=100,
            os_image_family="common-cu121",
            os_image_project="deeplearning-platform-release",
        ),
        network=NetworkSpec(network_name="default"),
        project_id="test-project",
    )


def _price_table_result() -> CostEstimate:
    from datetime import UTC, datetime
    return CostEstimate(
        hourly_usd=0.8,
        monthly_usd=584.0,
        source="price_table",
        confidence="medium",
        estimated_at=datetime.now(UTC),
    )


class TestFallbackOrchestration:
    def test_infracost_success_returns_infracost_result(self, tmp_path: Path) -> None:
        from datetime import UTC, datetime
        ic_result = CostEstimate(
            hourly_usd=0.5, monthly_usd=365.0,
            source="infracost", confidence="high",
            estimated_at=datetime.now(UTC),
        )
        ctx = MagicMock(spec=GcpContext)
        with patch("vibeops.cost.run_infracost", return_value=ic_result) as mock_ic:
            result = estimate(tmp_path, _spec(), ctx)
        assert result.source == "infracost"
        mock_ic.assert_called_once()

    def test_infracost_none_falls_back_to_price_table(self, tmp_path: Path) -> None:
        ctx = MagicMock(spec=GcpContext)
        pt_result = _price_table_result()
        with (
            patch("vibeops.cost.run_infracost", return_value=None),
            patch("vibeops.cost.price_table.estimate_from_price_table", return_value=pt_result) as mock_pt,
        ):
            result = estimate(tmp_path, _spec(), ctx)
        assert result.source == "price_table"
        mock_pt.assert_called_once()

    def test_infracost_none_no_ctx_returns_zero_estimate(self, tmp_path: Path) -> None:
        with patch("vibeops.cost.run_infracost", return_value=None):
            result = estimate(tmp_path, _spec(), ctx=None)
        assert result.monthly_usd == pytest.approx(0.0)
        assert result.confidence == "low"

    def test_price_table_exception_returns_zero_estimate(self, tmp_path: Path) -> None:
        ctx = MagicMock(spec=GcpContext)
        with (
            patch("vibeops.cost.run_infracost", return_value=None),
            patch("vibeops.cost.price_table.estimate_from_price_table", side_effect=RuntimeError("boom")),
        ):
            result = estimate(tmp_path, _spec(), ctx)
        assert result.monthly_usd == pytest.approx(0.0)

    def test_zero_estimate_has_note(self, tmp_path: Path) -> None:
        with patch("vibeops.cost.run_infracost", return_value=None):
            result = estimate(tmp_path, _spec(), ctx=None)
        assert len(result.notes) > 0
