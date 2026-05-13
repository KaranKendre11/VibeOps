from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from vibeops.core.gcp_context import GcpContext
from vibeops.core.llm import LLMClient
from vibeops.graph.orchestrator import build_graph
from vibeops.models.conversation import ConversationTurn, RequirementPhase, TurnRole
from vibeops.models.iac import TerraformValidationResult
from vibeops.models.results import (
    ChatResult,
    MachineType,
    MachineTypesResult,
    Network,
    NetworksResult,
    QuotaResult,
    ZoneAvailability,
    ZonesWithAcceleratorResult,
)
from vibeops.models.state import FlowStage, GraphState

_RESOLVED_OS = ("deeplearning-platform-release", "common-cu121")


def _first_message() -> ChatResult:
    return ChatResult(
        content="T4 inference workload. Any preference on region or preemptible?",
        input_tokens=100,
        output_tokens=30,
    )


def _extraction_result() -> ChatResult:
    return ChatResult(
        content=json.dumps({
            "workload_intent": "inference_small",
            "gpu_type": "nvidia-tesla-t4",
            "gpu_count": 1,
            "cpu_floor": "8",
            "memory_floor": "32",
            "os_family": "deeplearning-platform-release",
            "disk_size_gb": 100,
            "preemptible": False,
            "region_preference": "none",
        }),
        input_tokens=100,
        output_tokens=50,
    )


def _ctx() -> GcpContext:
    ctx = MagicMock(spec=GcpContext)
    ctx.project_id = "test-project"
    ctx.credentials = MagicMock()
    ctx.get_cached.return_value = None
    ctx.set_cached.return_value = None
    return ctx


def _zones() -> ZonesWithAcceleratorResult:
    return ZonesWithAcceleratorResult(
        gpu_type="nvidia-tesla-t4",
        zones=[ZoneAvailability(zone="us-central1-a", region="us-central1", gpu_available=True, quota_total=4, quota_used=0)],
    )


def _machines() -> MachineTypesResult:
    return MachineTypesResult(
        zone="us-central1-a",
        machine_types=[MachineType(name="n1-standard-8", cpus=8, memory_gb=32.0, gpu_compatible=True)],
    )


def _networks() -> NetworksResult:
    return NetworksResult(networks=[Network(name="default", self_link="", auto_create_subnetworks=True)])


def _run_to_awaiting_approval() -> GraphState:
    llm = MagicMock(spec=LLMClient)
    llm.chat_completion.side_effect = [_first_message(), _extraction_result()]
    ctx = _ctx()

    graph = build_graph()
    thread: dict[str, Any] = {
        "configurable": {"thread_id": "m3-happy", "llm_client": llm, "gcp_context": ctx}
    }
    initial = GraphState(user_prompt="T4 VM for ML inference")

    with (
        patch("vibeops.agents.architecture.list_zones_with_accelerator", return_value=_zones()),
        patch("vibeops.agents.architecture.get_accelerator_quota", return_value=QuotaResult(region="us-central1", gpu_type="nvidia-tesla-t4", limit=4, usage=0)),
        patch("vibeops.agents.architecture.list_machine_types", return_value=_machines()),
        patch("vibeops.agents.architecture.list_existing_networks", return_value=_networks()),
        patch("vibeops.agents.architecture.resolve_os_image", return_value=_RESOLVED_OS),
        patch("vibeops.agents.iac.init"),
        patch("vibeops.agents.iac.validate", return_value=TerraformValidationResult(ok=True)),
        patch("vibeops.cost.infracost.run_infracost", return_value=None),
    ):
        # First invoke: initial message from requirement agent, pauses at asking_pause
        graph.invoke(initial.model_dump(), thread)
        snapshot = dict(graph.get_state(thread).values)
        state = GraphState.model_validate(snapshot)
        assert state.requirement_phase == RequirementPhase.ASKING

        # Simulate user confirming: add user turn, set RESUMING_CONFIRMATION
        existing = [t.model_dump() for t in state.conversation]
        existing.append(ConversationTurn(role=TurnRole.USER, content="yes proceed").model_dump())
        graph.update_state(
            thread,
            {
                "conversation": existing,
                "requirement_phase": RequirementPhase.RESUMING_CONFIRMATION.value,
            },
        )
        graph.invoke(None, thread)
        snapshot = dict(graph.get_state(thread).values)
        state = GraphState.model_validate(snapshot)
        assert state.stage == FlowStage.AWAITING_ARCHITECTURE

        graph.update_state(
            thread,
            {"architecture_response": {"candidate_index": 0, "network_name": "default"}},
        )
        graph.invoke(None, thread)
        snapshot = dict(graph.get_state(thread).values)
        return GraphState.model_validate(snapshot)


class TestGraphM3HappyPath:
    def test_reaches_awaiting_approval(self) -> None:
        state = _run_to_awaiting_approval()
        assert state.stage == FlowStage.AWAITING_APPROVAL

    def test_terraform_files_populated(self) -> None:
        state = _run_to_awaiting_approval()
        assert set(state.terraform_files.keys()) == {"main.tf", "variables.tf", "outputs.tf"}
        for content in state.terraform_files.values():
            assert len(content) > 0

    def test_no_validation_errors(self) -> None:
        state = _run_to_awaiting_approval()
        assert state.validation_errors == []

    def test_deployment_spec_present(self) -> None:
        state = _run_to_awaiting_approval()
        assert state.deployment_spec is not None
        assert state.deployment_spec.compute.gpu_type.value == "nvidia-tesla-t4"
