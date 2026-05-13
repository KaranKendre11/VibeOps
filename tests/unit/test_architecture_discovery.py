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
from vibeops.models.state import FlowStage, GraphState


def _ctx() -> GcpContext:
    ctx = MagicMock(spec=GcpContext)
    ctx.project_id = "test-project"
    ctx.credentials = MagicMock()
    ctx.get_cached.return_value = None
    ctx.set_cached.return_value = None
    return ctx


def _draft(region_pref: RegionPreference = RegionPreference.NONE) -> RequirementDraft:
    return RequirementDraft(
        workload_intent=WorkloadIntent.INFERENCE_SMALL,
        gpu_type=GpuType.T4,
        gpu_count=1,
        cpu_floor=CpuClass.C8,
        memory_floor=MemoryClass.M32,
        os_family=OsFamily.DEEP_LEARNING,
        disk_size_gb=100,
        preemptible=False,
        region_preference=region_pref,
    )


def _base_state(region_pref: RegionPreference = RegionPreference.NONE) -> GraphState:
    return GraphState(user_prompt="T4 VM", requirement_draft=_draft(region_pref))


def test_calls_zones_with_correct_gpu_type() -> None:
    ctx = _ctx()
    zones = [ZoneAvailability(zone="us-central1-a", region="us-central1", gpu_available=True, quota_total=4, quota_used=0)]
    machines = [MachineType(name="n1-standard-8", cpus=8, memory_gb=32.0, gpu_compatible=True)]
    mock_zones = MagicMock(return_value=ZonesWithAcceleratorResult(gpu_type="nvidia-tesla-t4", zones=zones))

    with (
        patch("vibeops.agents.architecture.list_zones_with_accelerator", mock_zones),
        patch("vibeops.agents.architecture.get_accelerator_quota", return_value=QuotaResult(region="us-central1", gpu_type="nvidia-tesla-t4", limit=4, usage=0)),
        patch("vibeops.agents.architecture.list_machine_types", return_value=MachineTypesResult(zone="us-central1-a", machine_types=machines)),
        patch("vibeops.agents.architecture.list_existing_networks", return_value=NetworksResult(networks=[Network(name="default", self_link="", auto_create_subnetworks=True)])),
    ):
        architecture_agent(_base_state(), {"configurable": {"gcp_context": ctx}})

    mock_zones.assert_called_once_with(ctx, "nvidia-tesla-t4")


def test_drops_candidates_below_cpu_floor() -> None:
    ctx = _ctx()
    zones = [ZoneAvailability(zone="us-central1-a", region="us-central1", gpu_available=True, quota_total=4, quota_used=0)]
    # cpu_floor is C8 (8), machine only has 4 cpus → must be dropped
    machines = [MachineType(name="n1-standard-4", cpus=4, memory_gb=15.0, gpu_compatible=True)]

    with (
        patch("vibeops.agents.architecture.list_zones_with_accelerator", return_value=ZonesWithAcceleratorResult(gpu_type="nvidia-tesla-t4", zones=zones)),
        patch("vibeops.agents.architecture.get_accelerator_quota", return_value=QuotaResult(region="us-central1", gpu_type="nvidia-tesla-t4", limit=4, usage=0)),
        patch("vibeops.agents.architecture.list_machine_types", return_value=MachineTypesResult(zone="us-central1-a", machine_types=machines)),
        patch("vibeops.agents.architecture.list_existing_networks", return_value=NetworksResult(networks=[])),
    ):
        result = architecture_agent(_base_state(), {"configurable": {"gcp_context": ctx}})

    # No candidates → error path
    assert result.error is not None


def test_filters_by_region_preference() -> None:
    ctx = _ctx()
    zones = [
        ZoneAvailability(zone="us-central1-a", region="us-central1", gpu_available=True, quota_total=4, quota_used=0),
        ZoneAvailability(zone="europe-west4-a", region="europe-west4", gpu_available=True, quota_total=4, quota_used=0),
    ]
    machines = [MachineType(name="n1-standard-8", cpus=8, memory_gb=32.0, gpu_compatible=True)]

    with (
        patch("vibeops.agents.architecture.list_zones_with_accelerator", return_value=ZonesWithAcceleratorResult(gpu_type="nvidia-tesla-t4", zones=zones)),
        patch("vibeops.agents.architecture.get_accelerator_quota", return_value=QuotaResult(region="europe-west4", gpu_type="nvidia-tesla-t4", limit=4, usage=0)),
        patch("vibeops.agents.architecture.list_machine_types", return_value=MachineTypesResult(zone="europe-west4-a", machine_types=machines)),
        patch("vibeops.agents.architecture.list_existing_networks", return_value=NetworksResult(networks=[])),
    ):
        result = architecture_agent(
            _base_state(RegionPreference.EUROPE),
            {"configurable": {"gcp_context": ctx}},
        )

    if result.architecture_options:
        for c in result.architecture_options.candidates:
            assert c.region.startswith("europe-")


def test_result_has_awaiting_architecture_stage() -> None:
    ctx = _ctx()
    zones = [ZoneAvailability(zone="us-central1-a", region="us-central1", gpu_available=True, quota_total=4, quota_used=0)]
    machines = [MachineType(name="n1-standard-8", cpus=8, memory_gb=32.0, gpu_compatible=True)]

    with (
        patch("vibeops.agents.architecture.list_zones_with_accelerator", return_value=ZonesWithAcceleratorResult(gpu_type="nvidia-tesla-t4", zones=zones)),
        patch("vibeops.agents.architecture.get_accelerator_quota", return_value=QuotaResult(region="us-central1", gpu_type="nvidia-tesla-t4", limit=4, usage=0)),
        patch("vibeops.agents.architecture.list_machine_types", return_value=MachineTypesResult(zone="us-central1-a", machine_types=machines)),
        patch("vibeops.agents.architecture.list_existing_networks", return_value=NetworksResult(networks=[Network(name="default", self_link="", auto_create_subnetworks=True)])),
    ):
        result = architecture_agent(_base_state(), {"configurable": {"gcp_context": ctx}})

    assert result.stage == FlowStage.AWAITING_ARCHITECTURE
    assert result.architecture_options is not None
