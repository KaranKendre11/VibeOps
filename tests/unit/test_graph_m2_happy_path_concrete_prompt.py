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


def _first_message_result() -> ChatResult:
    return ChatResult(
        content="Looks like a T4 inference workload. Ready to proceed?",
        input_tokens=50,
        output_tokens=20,
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


def _make_mock_ctx() -> GcpContext:
    ctx = MagicMock(spec=GcpContext)
    ctx.project_id = "test-project"
    ctx.credentials = MagicMock()
    ctx.get_cached.return_value = None
    ctx.set_cached.return_value = None
    return ctx


def test_concrete_prompt_reaches_awaiting_approval() -> None:
    """Conversational flow: initial message → user confirms → architecture → IaC."""
    llm = MagicMock(spec=LLMClient)
    llm.chat_completion.side_effect = [_first_message_result(), _extraction_result()]
    ctx = _make_mock_ctx()

    graph = build_graph()
    thread_id = "concrete-test"
    thread: dict[str, Any] = {"configurable": {"thread_id": thread_id, "llm_client": llm, "gcp_context": ctx}}

    initial = GraphState(user_prompt="T4 VM, 8 vCPU, 32GB, Deep Learning, preemptible")

    zones = [ZoneAvailability(zone="us-central1-a", region="us-central1", gpu_available=True, quota_total=4, quota_used=0)]
    machines = [MachineType(name="n1-standard-8", cpus=8, memory_gb=32.0, gpu_compatible=True)]

    with (
        patch("vibeops.agents.architecture.list_zones_with_accelerator", return_value=ZonesWithAcceleratorResult(gpu_type="nvidia-tesla-t4", zones=zones)),
        patch("vibeops.agents.architecture.get_accelerator_quota", return_value=QuotaResult(region="us-central1", gpu_type="nvidia-tesla-t4", limit=4, usage=0)),
        patch("vibeops.agents.architecture.list_machine_types", return_value=MachineTypesResult(zone="us-central1-a", machine_types=machines)),
        patch("vibeops.agents.architecture.list_existing_networks", return_value=NetworksResult(networks=[Network(name="default", self_link="", auto_create_subnetworks=True)])),
        patch("vibeops.agents.architecture.resolve_os_image", return_value=_RESOLVED_OS),
        patch("vibeops.agents.iac.init"),
        patch("vibeops.agents.iac.validate", return_value=TerraformValidationResult(ok=True)),
        patch("vibeops.cost.infracost.run_infracost", return_value=None),
    ):
        # First invoke: requirement_agent runs, sends initial message, pauses at asking_pause
        graph.invoke(initial.model_dump(), thread)
        snapshot = dict(graph.get_state(thread).values)
        state = GraphState.model_validate(snapshot)

        assert state.requirement_phase == RequirementPhase.ASKING

        # Simulate user completing conversation: inject user confirmation turn + set RESUMING_CONFIRMATION
        existing_conv = [t.model_dump() for t in state.conversation]
        existing_conv.append(ConversationTurn(role=TurnRole.USER, content="yes, looks good").model_dump())
        graph.update_state(
            thread,
            {
                "conversation": existing_conv,
                "requirement_phase": RequirementPhase.RESUMING_CONFIRMATION.value,
            },
        )
        graph.invoke(None, thread)
        snapshot = dict(graph.get_state(thread).values)
        state = GraphState.model_validate(snapshot)

        # After confirmation → architecture ran → awaiting_architecture pause
        assert state.stage == FlowStage.AWAITING_ARCHITECTURE

        # Simulate user picking candidate
        graph.update_state(
            thread,
            {"architecture_response": {"candidate_index": 0, "network_name": "default"}},
        )
        graph.invoke(None, thread)
        snapshot = dict(graph.get_state(thread).values)
        state = GraphState.model_validate(snapshot)

    assert state.stage == FlowStage.AWAITING_APPROVAL
    assert state.terraform_files
