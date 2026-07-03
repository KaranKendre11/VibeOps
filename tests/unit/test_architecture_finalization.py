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
from vibeops.models.spec import DeploymentSpec, GpuType
from vibeops.models.state import FlowStage, GraphState

_RESOLVED_OS = ("deeplearning-platform-release", "common-cu121")


def _ctx() -> GcpContext:
    ctx = MagicMock(spec=GcpContext)
    ctx.project_id = "my-project"
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
                rationale="Full quota.",
            )
        ],
        networks=[Network(name="default", self_link="", auto_create_subnetworks=True)],
        requirement=_draft(),
    )


@patch("vibeops.agents.architecture.resolve_os_image", return_value=_RESOLVED_OS)
def test_valid_response_produces_deployment_spec(_mock: MagicMock) -> None:
    ctx = _ctx()
    state = GraphState(
        user_prompt="T4 VM",
        requirement_draft=_draft(),
        architecture_options=_options(),
        architecture_response={"candidate_index": 0, "network_name": "default"},
    )
    result = architecture_agent(state, {"configurable": {"gcp_context": ctx}})

    assert result.deployment_spec is not None
    assert isinstance(result.deployment_spec, DeploymentSpec)
    assert result.deployment_spec.compute.machine_type == "n1-standard-8"
    assert result.deployment_spec.compute.zone == "us-central1-a"
    assert result.deployment_spec.project_id == "my-project"
    assert result.stage == FlowStage.IAC


def test_out_of_range_candidate_index_returns_error() -> None:
    ctx = _ctx()
    state = GraphState(
        user_prompt="T4 VM",
        requirement_draft=_draft(),
        architecture_options=_options(),
        architecture_response={"candidate_index": 99, "network_name": "default"},
    )
    result = architecture_agent(state, {"configurable": {"gcp_context": ctx}})
    assert result.error is not None
    assert result.deployment_spec is None


@patch("vibeops.agents.architecture.resolve_os_image", return_value=_RESOLVED_OS)
def test_network_name_used_in_spec(_mock: MagicMock) -> None:
    ctx = _ctx()
    state = GraphState(
        user_prompt="T4 VM",
        requirement_draft=_draft(),
        architecture_options=_options(),
        architecture_response={"candidate_index": 0, "network_name": "my-custom-vpc"},
    )
    result = architecture_agent(state, {"configurable": {"gcp_context": ctx}})
    assert result.deployment_spec is not None
    assert result.deployment_spec.network.network_name == "my-custom-vpc"


@patch("vibeops.agents.architecture.resolve_os_image", return_value=_RESOLVED_OS)
def test_project_id_injected_from_context(_mock: MagicMock) -> None:
    ctx = _ctx()
    state = GraphState(
        user_prompt="T4 VM",
        requirement_draft=_draft(),
        architecture_options=_options(),
        architecture_response={"candidate_index": 0, "network_name": "default"},
    )
    result = architecture_agent(state, {"configurable": {"gcp_context": ctx}})
    assert result.deployment_spec is not None
    assert result.deployment_spec.project_id == "my-project"
