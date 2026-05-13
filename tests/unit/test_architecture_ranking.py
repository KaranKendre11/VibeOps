from __future__ import annotations

from unittest.mock import MagicMock, patch

from vibeops.agents.architecture import architecture_agent
from vibeops.core.gcp_context import GcpContext
from vibeops.models.requirement import (
    CpuClass,
    MemoryClass,
    OsFamily,
    RegionPreference,
    RequirementDraft,
    WorkloadIntent,
)
from vibeops.models.results import (
    MachineType,
    MachineTypesResult,
    Network,
    NetworksResult,
    QuotaResult,
    ZoneAvailability,
    ZonesWithAcceleratorResult,
)
from vibeops.models.spec import GpuType
from vibeops.models.state import GraphState


def _ctx() -> GcpContext:
    ctx = MagicMock(spec=GcpContext)
    ctx.project_id = "test-project"
    ctx.credentials = MagicMock()
    ctx.get_cached.return_value = None
    ctx.set_cached.return_value = None
    return ctx


def test_highest_quota_ranked_first() -> None:
    """Zone with more quota should appear first."""
    ctx = _ctx()
    zones = [
        ZoneAvailability(zone="us-central1-b", region="us-central1", gpu_available=True, quota_total=2, quota_used=1),
        ZoneAvailability(zone="us-central1-a", region="us-central1", gpu_available=True, quota_total=4, quota_used=0),
    ]
    machines_a = [MachineType(name="n1-standard-8", cpus=8, memory_gb=32.0, gpu_compatible=True)]

    def _mock_quota(ctx: GcpContext, region: str, gpu_type: str) -> QuotaResult:
        return QuotaResult(region=region, gpu_type=gpu_type, limit=4, usage=0)

    def _mock_mt(ctx: GcpContext, zone: str, gpu_compatible: bool = True) -> MachineTypesResult:
        return MachineTypesResult(zone=zone, machine_types=machines_a)

    draft = RequirementDraft(
        workload_intent=WorkloadIntent.INFERENCE_SMALL,
        gpu_type=GpuType.T4,
        gpu_count=1,
        cpu_floor=CpuClass.C8,
        memory_floor=MemoryClass.M32,
        os_family=OsFamily.DEEP_LEARNING,
        disk_size_gb=100,
        preemptible=False,
        region_preference=RegionPreference.NONE,
    )

    def _mock_zones(ctx: GcpContext, gpu_type: str) -> ZonesWithAcceleratorResult:
        return ZonesWithAcceleratorResult(gpu_type=gpu_type, zones=zones)

    def _mock_nets(ctx: GcpContext) -> NetworksResult:
        return NetworksResult(networks=[Network(name="default", self_link="", auto_create_subnetworks=True)])

    with (
        patch("vibeops.agents.architecture.list_zones_with_accelerator", side_effect=_mock_zones),
        patch("vibeops.agents.architecture.get_accelerator_quota", side_effect=_mock_quota),
        patch("vibeops.agents.architecture.list_machine_types", side_effect=_mock_mt),
        patch("vibeops.agents.architecture.list_existing_networks", side_effect=_mock_nets),
    ):
        result = architecture_agent(
            GraphState(user_prompt="T4 VM", requirement_draft=draft),
            {"configurable": {"gcp_context": ctx}},
        )

    assert result.architecture_options is not None
    candidates = result.architecture_options.candidates
    assert len(candidates) >= 1


def test_max_three_candidates_returned() -> None:
    ctx = _ctx()
    zones = [
        ZoneAvailability(zone=f"us-central1-{chr(ord('a') + i)}", region="us-central1", gpu_available=True, quota_total=4, quota_used=0)
        for i in range(5)
    ]
    machines = [MachineType(name="n1-standard-8", cpus=8, memory_gb=32.0, gpu_compatible=True)]

    draft = RequirementDraft(
        workload_intent=WorkloadIntent.INFERENCE_SMALL,
        gpu_type=GpuType.T4,
        gpu_count=1,
        cpu_floor=CpuClass.C8,
        memory_floor=MemoryClass.M32,
        os_family=OsFamily.DEEP_LEARNING,
        disk_size_gb=100,
        preemptible=False,
        region_preference=RegionPreference.NONE,
    )

    with (
        patch("vibeops.agents.architecture.list_zones_with_accelerator", return_value=ZonesWithAcceleratorResult(gpu_type="nvidia-tesla-t4", zones=zones)),
        patch("vibeops.agents.architecture.get_accelerator_quota", return_value=QuotaResult(region="us-central1", gpu_type="nvidia-tesla-t4", limit=4, usage=0)),
        patch("vibeops.agents.architecture.list_machine_types", return_value=MachineTypesResult(zone="us-central1-a", machine_types=machines)),
        patch("vibeops.agents.architecture.list_existing_networks", return_value=NetworksResult(networks=[])),
    ):
        result = architecture_agent(
            GraphState(user_prompt="T4 VM", requirement_draft=draft),
            {"configurable": {"gcp_context": ctx}},
        )

    assert result.architecture_options is not None
    assert len(result.architecture_options.candidates) <= 3
