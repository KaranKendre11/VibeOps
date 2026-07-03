from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vibeops.core.gcp_context import GcpContext
from vibeops.cost.cloud_catalog import estimate_from_catalog
from vibeops.cost.pricing_constants import (
    GPU_HOURLY_USD,
    HOURS_PER_MONTH,
    PREEMPTIBLE_DISCOUNT,
)
from vibeops.models.spec import ComputeSpec, DeploymentSpec, GpuType, NetworkSpec, StorageSpec


def _spec(
    machine_type: str = "n1-standard-8",
    gpu_type: GpuType = GpuType.T4,
    gpu_count: int = 1,
    preemptible: bool = False,
    disk_size_gb: int = 100,
) -> DeploymentSpec:
    return DeploymentSpec(
        compute=ComputeSpec(
            machine_type=machine_type,
            zone="us-central1-a",
            gpu_type=gpu_type,
            gpu_count=gpu_count,
            preemptible=preemptible,
        ),
        storage=StorageSpec(
            disk_size_gb=disk_size_gb,
            os_image_family="common-cu121",
            os_image_project="deeplearning-platform-release",
        ),
        network=NetworkSpec(network_name="default"),
        project_id="test-project",
    )


def _ctx(vcpus: int = 8, memory_mb: int = 30720) -> GcpContext:
    ctx = MagicMock(spec=GcpContext)
    ctx.project_id = "test-project"
    ctx.credentials = MagicMock()
    mt = MagicMock()
    mt.guest_cpus = vcpus
    mt.memory_mb = memory_mb
    return ctx


def _patch_machine(ctx: GcpContext, vcpus: int, memory_mb: int) -> MagicMock:
    mt = MagicMock()
    mt.guest_cpus = vcpus
    mt.memory_mb = memory_mb
    return mt


class TestEstimateFromCatalog:
    def test_source_is_cloud_catalog(self) -> None:
        ctx = _ctx()
        with patch("vibeops.cost.cloud_catalog._parse_machine_resources", return_value=(8, 30.0)):
            result = estimate_from_catalog(_spec(), ctx)
        assert result.source == "cloud_catalog"

    def test_confidence_is_medium(self) -> None:
        ctx = _ctx()
        with patch("vibeops.cost.cloud_catalog._parse_machine_resources", return_value=(8, 30.0)):
            result = estimate_from_catalog(_spec(), ctx)
        assert result.confidence == "medium"

    def test_on_demand_t4_positive_cost(self) -> None:
        ctx = _ctx()
        with patch("vibeops.cost.cloud_catalog._parse_machine_resources", return_value=(8, 30.0)):
            result = estimate_from_catalog(_spec(gpu_type=GpuType.T4), ctx)
        assert result.hourly_usd > 0
        assert result.monthly_usd > 0

    def test_on_demand_t4_includes_gpu_cost(self) -> None:
        ctx = _ctx()
        with patch("vibeops.cost.cloud_catalog._parse_machine_resources", return_value=(8, 30.0)):
            result = estimate_from_catalog(_spec(gpu_type=GpuType.T4), ctx)
        # Monthly must exceed the GPU cost alone
        gpu_monthly = GPU_HOURLY_USD["nvidia-tesla-t4"] * HOURS_PER_MONTH
        assert result.monthly_usd > gpu_monthly

    def test_preemptible_cheaper_than_on_demand(self) -> None:
        ctx = _ctx()
        with patch("vibeops.cost.cloud_catalog._parse_machine_resources", return_value=(8, 30.0)):
            on_demand = estimate_from_catalog(_spec(preemptible=False), ctx)
            preemptible = estimate_from_catalog(_spec(preemptible=True), ctx)
        assert preemptible.monthly_usd < on_demand.monthly_usd

    def test_preemptible_discount_applied(self) -> None:
        ctx = _ctx()
        with patch("vibeops.cost.cloud_catalog._parse_machine_resources", return_value=(8, 30.0)):
            on_demand = estimate_from_catalog(_spec(preemptible=False), ctx)
            preemptible = estimate_from_catalog(_spec(preemptible=True), ctx)
        assert preemptible.monthly_usd == pytest.approx(
            on_demand.monthly_usd * PREEMPTIBLE_DISCOUNT, rel=0.01
        )

    def test_preemptible_note_present(self) -> None:
        ctx = _ctx()
        with patch("vibeops.cost.cloud_catalog._parse_machine_resources", return_value=(8, 30.0)):
            result = estimate_from_catalog(_spec(preemptible=True), ctx)
        assert any("preemptible" in n.lower() for n in result.notes)

    def test_a100_more_expensive_than_t4(self) -> None:
        ctx = _ctx()
        with patch("vibeops.cost.cloud_catalog._parse_machine_resources", return_value=(8, 30.0)):
            t4 = estimate_from_catalog(_spec(gpu_type=GpuType.T4), ctx)
            a100 = estimate_from_catalog(_spec(gpu_type=GpuType.A100_40), ctx)
        assert a100.monthly_usd > t4.monthly_usd

    def test_breakdown_has_three_line_items(self) -> None:
        ctx = _ctx()
        with patch("vibeops.cost.cloud_catalog._parse_machine_resources", return_value=(8, 30.0)):
            result = estimate_from_catalog(_spec(), ctx)
        assert len(result.breakdown) == 3

    def test_monthly_is_hourly_times_730(self) -> None:
        ctx = _ctx()
        with patch("vibeops.cost.cloud_catalog._parse_machine_resources", return_value=(8, 30.0)):
            result = estimate_from_catalog(_spec(), ctx)
        assert result.monthly_usd == pytest.approx(result.hourly_usd * HOURS_PER_MONTH, rel=0.01)
