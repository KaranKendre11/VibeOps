from __future__ import annotations

from unittest.mock import MagicMock, patch

from vibeops.agents.architecture import architecture_agent
from vibeops.core.gcp_context import GcpContext
from vibeops.models.architecture import ArchitectureCandidate, ArchitectureOptions
from vibeops.models.requirement import (
    CpuClass,
    MemoryClass,
    OsFamily,
    RegionPreference,
    RequirementDraft,
    WorkloadIntent,
)
from vibeops.models.results import Network
from vibeops.models.spec import GpuType
from vibeops.models.state import GraphState


class _RaisingLLM:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"Architecture Agent called LLMClient.{name}")


def _gcp_ctx() -> GcpContext:
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


def _options() -> ArchitectureOptions:
    return ArchitectureOptions(
        candidates=[
            ArchitectureCandidate(
                zone="us-central1-a",
                region="us-central1",
                machine_type="n1-standard-8",
                cpus=8,
                memory_gb=30.0,
                quota_total=4,
                quota_remaining=4,
                rationale="Full quota; smallest machine satisfying 8 vCPU / 32 GB.",
            )
        ],
        networks=[Network(name="default", self_link="", auto_create_subnetworks=True)],
        requirement=_draft(),
    )


def test_discovery_phase_never_calls_llm() -> None:
    ctx = _gcp_ctx()
    llm = _RaisingLLM()
    config = {"configurable": {"gcp_context": ctx, "llm_client": llm}}
    state = GraphState(user_prompt="T4 VM", requirement_draft=_draft())

    with (
        patch("vibeops.agents.architecture.list_zones_with_accelerator") as mock_zones,
        patch("vibeops.agents.architecture.get_accelerator_quota") as mock_quota,
        patch("vibeops.agents.architecture.list_machine_types") as mock_mt,
        patch("vibeops.agents.architecture.list_existing_networks") as mock_nets,
    ):
        from vibeops.models.results import (
            MachineType,
            MachineTypesResult,
            NetworksResult,
            QuotaResult,
            ZoneAvailability,
            ZonesWithAcceleratorResult,
        )

        mock_zones.return_value = ZonesWithAcceleratorResult(
            gpu_type="nvidia-tesla-t4",
            zones=[ZoneAvailability(zone="us-central1-a", region="us-central1", gpu_available=True, quota_total=4, quota_used=0)],
        )
        mock_quota.return_value = QuotaResult(region="us-central1", gpu_type="nvidia-tesla-t4", limit=4, usage=0)
        mock_mt.return_value = MachineTypesResult(zone="us-central1-a", machine_types=[
            MachineType(name="n1-standard-8", cpus=8, memory_gb=30.0, gpu_compatible=True)
        ])
        mock_nets.return_value = NetworksResult(networks=[])

        # Must not raise — LLM must never be called
        architecture_agent(state, config)


def test_finalization_phase_never_calls_llm() -> None:
    ctx = _gcp_ctx()
    llm = _RaisingLLM()
    config = {"configurable": {"gcp_context": ctx, "llm_client": llm}}
    state = GraphState(
        user_prompt="T4 VM",
        requirement_draft=_draft(),
        architecture_options=_options(),
        architecture_response={"candidate_index": 0, "network_name": "default"},
    )
    # Must not raise
    architecture_agent(state, config)
