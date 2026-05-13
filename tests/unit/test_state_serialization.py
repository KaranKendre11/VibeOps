from __future__ import annotations

from enum import StrEnum

from vibeops.models.requirement import (
    CpuClass,
    MemoryClass,
    OsFamily,
    RegionPreference,
    RequirementDraft,
    WorkloadIntent,
)
from vibeops.models.spec import (
    ComputeSpec,
    DeploymentSpec,
    GpuType,
    NetworkSpec,
    StorageSpec,
)
from vibeops.models.state import FlowStage, GraphState


def _full_state() -> GraphState:
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
    spec = DeploymentSpec(
        compute=ComputeSpec(
            machine_type="n1-standard-4",
            zone="us-central1-a",
            gpu_type=GpuType.T4,
            gpu_count=1,
            preemptible=False,
        ),
        storage=StorageSpec(
            disk_size_gb=100,
            os_image_family="deeplearning-platform-release",
            os_image_project="deeplearning-platform-release",
        ),
        network=NetworkSpec(network_name="default"),
        project_id="my-gcp-project",
    )
    return GraphState(
        user_prompt="get me a VM with T4 GPU",
        chat_history=[{"role": "user", "content": "get me a VM with T4 GPU"}],
        requirement_draft=draft,
        deployment_spec=spec,
        terraform_files={"main.tf": 'resource "google_compute_instance" "vm" {}'},
        cost_estimate_usd=0.0,
        approved=False,
        stage=FlowStage.AWAITING_APPROVAL,
        error=None,
    )


def test_round_trip_json() -> None:
    original = _full_state()
    json_str = original.model_dump_json()
    restored = GraphState.model_validate_json(json_str)
    assert restored == original


def test_flow_stage_is_str_enum() -> None:
    assert issubclass(FlowStage, StrEnum)
    assert FlowStage.AWAITING_APPROVAL.value == "awaiting_approval"


def test_default_state_is_serializable() -> None:
    state = GraphState(user_prompt="hello")
    assert GraphState.model_validate_json(state.model_dump_json()) == state


def test_credentials_not_in_graph_state() -> None:
    fields = set(GraphState.model_fields.keys())
    forbidden = {"openai_key", "api_key", "sa_json", "gcp_credentials", "service_account"}
    leaked = fields & forbidden
    assert fields.isdisjoint(forbidden), f"Credential fields found in GraphState: {leaked}"
