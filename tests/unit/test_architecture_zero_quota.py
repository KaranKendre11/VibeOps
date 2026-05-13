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


def _draft() -> RequirementDraft:
    return RequirementDraft(
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


def test_zero_quota_surfaces_error_message() -> None:
    ctx = _ctx()
    zones = [ZoneAvailability(zone="us-central1-a", region="us-central1", gpu_available=True, quota_total=0, quota_used=0)]

    with (
        patch("vibeops.agents.architecture.list_zones_with_accelerator", return_value=ZonesWithAcceleratorResult(gpu_type="nvidia-tesla-t4", zones=zones)),
        patch("vibeops.agents.architecture.get_accelerator_quota", return_value=QuotaResult(region="us-central1", gpu_type="nvidia-tesla-t4", limit=0, usage=0)),
        patch("vibeops.agents.architecture.list_machine_types", return_value=MachineTypesResult(zone="us-central1-a", machine_types=[MachineType(name="n1-standard-8", cpus=8, memory_gb=30.0, gpu_compatible=True)])),
        patch("vibeops.agents.architecture.list_existing_networks", return_value=NetworksResult(networks=[])),
    ):
        result = architecture_agent(
            GraphState(user_prompt="T4 VM", requirement_draft=_draft()),
            {"configurable": {"gcp_context": ctx}},
        )

    assert result.error is not None
    assert "quota" in result.error.lower()
    assert result.architecture_options is None


def test_zero_quota_no_architecture_card_data() -> None:
    ctx = _ctx()
    zones = [ZoneAvailability(zone="us-central1-a", region="us-central1", gpu_available=True, quota_total=0, quota_used=0)]

    with (
        patch("vibeops.agents.architecture.list_zones_with_accelerator", return_value=ZonesWithAcceleratorResult(gpu_type="nvidia-tesla-t4", zones=zones)),
        patch("vibeops.agents.architecture.get_accelerator_quota", return_value=QuotaResult(region="us-central1", gpu_type="nvidia-tesla-t4", limit=0, usage=0)),
        patch("vibeops.agents.architecture.list_machine_types", return_value=MachineTypesResult(zone="us-central1-a", machine_types=[MachineType(name="n1-standard-8", cpus=8, memory_gb=30.0, gpu_compatible=True)])),
        patch("vibeops.agents.architecture.list_existing_networks", return_value=NetworksResult(networks=[])),
    ):
        result = architecture_agent(
            GraphState(user_prompt="T4 VM", requirement_draft=_draft()),
            {"configurable": {"gcp_context": ctx}},
        )

    assert result.architecture_options is None
