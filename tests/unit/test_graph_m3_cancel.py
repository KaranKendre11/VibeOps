from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from vibeops.core.gcp_context import GcpContext
from vibeops.core.llm import LLMClient
from vibeops.graph.orchestrator import build_graph
from vibeops.models.conversation import RequirementPhase
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


def _high_conf() -> ChatResult:
    return ChatResult(
        content=json.dumps({
            "workload_intent": "inference_small",
            "workload_intent_confidence": "high",
            "gpu_type": "nvidia-tesla-t4",
            "gpu_type_confidence": "high",
            "gpu_count": 1,
            "gpu_count_confidence": "high",
            "cpu_floor": "8",
            "cpu_floor_confidence": "high",
            "memory_floor": "32",
            "memory_floor_confidence": "high",
            "os_family": "deeplearning-platform-release",
            "os_family_confidence": "high",
            "disk_size_gb": 100,
            "disk_size_gb_confidence": "high",
            "preemptible": False,
            "preemptible_confidence": "high",
            "region_preference": "none",
            "region_preference_confidence": "high",
            "next_question": None,
            "scope_ok": True,
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


class TestGraphM3Cancel:
    def test_cancel_at_review_sets_cancelled(self, mocker: MagicMock) -> None:
        llm = MagicMock(spec=LLMClient)
        llm.chat_completion.return_value = _high_conf()
        ctx = _ctx()
        deploy_spy = mocker.patch("vibeops.agents.deployment.deployment_agent")

        graph = build_graph()
        thread: dict[str, Any] = {
            "configurable": {"thread_id": "m3-cancel", "llm_client": llm, "gcp_context": ctx}
        }
        initial = GraphState(user_prompt="deploy T4 VM")

        zones = [ZoneAvailability(zone="us-central1-a", region="us-central1", gpu_available=True, quota_total=4, quota_used=0)]
        machines = [MachineType(name="n1-standard-8", cpus=8, memory_gb=32.0, gpu_compatible=True)]

        with (
            patch("vibeops.agents.architecture.list_zones_with_accelerator", return_value=ZonesWithAcceleratorResult(gpu_type="nvidia-tesla-t4", zones=zones)),
            patch("vibeops.agents.architecture.get_accelerator_quota", return_value=QuotaResult(region="us-central1", gpu_type="nvidia-tesla-t4", limit=4, usage=0)),
            patch("vibeops.agents.architecture.list_machine_types", return_value=MachineTypesResult(zone="us-central1-a", machine_types=machines)),
            patch("vibeops.agents.architecture.list_existing_networks", return_value=NetworksResult(networks=[Network(name="default", self_link="", auto_create_subnetworks=True)])),
            patch("vibeops.agents.iac.init"),
            patch("vibeops.agents.iac.validate", return_value=TerraformValidationResult(ok=True)),
            patch("vibeops.cost.infracost.run_infracost", return_value=None),
        ):
            graph.invoke(initial.model_dump(), thread)

            confirmation = {
                "workload_intent": "inference_small",
                "gpu_type": "nvidia-tesla-t4",
                "gpu_count": 1,
                "cpu_floor": "8",
                "memory_floor": "32",
                "os_family": "deeplearning-platform-release",
                "disk_size_gb": 100,
                "preemptible": False,
                "region_preference": "none",
            }
            graph.update_state(
                thread,
                {"confirmation_response": confirmation, "requirement_phase": RequirementPhase.RESUMING_CONFIRMATION.value},
            )
            graph.invoke(None, thread)
            graph.update_state(
                thread,
                {"architecture_response": {"candidate_index": 0, "network_name": "default"}},
            )
            graph.invoke(None, thread)

            # At AWAITING_APPROVAL — cancel
            graph.update_state(thread, {"approved": False})
            graph.invoke(None, thread)

        snapshot = dict(graph.get_state(thread).values)
        state = GraphState.model_validate(snapshot)

        assert state.stage == FlowStage.CANCELLED
        deploy_spy.assert_not_called()

    def test_cancel_deployment_node_unreachable(self, mocker: MagicMock) -> None:
        """Same as above, confirms deployment agent is never called when cancelled."""
        deploy_spy = mocker.patch("vibeops.agents.deployment.deployment_agent")

        graph = build_graph()
        thread: dict[str, Any] = {"configurable": {"thread_id": "m3-cancel2"}}
        initial = GraphState(user_prompt="test prompt")

        # Run stub path (no LLM) to AWAITING_APPROVAL
        with (
            patch("vibeops.agents.iac.init"),
            patch("vibeops.agents.iac.validate", return_value=TerraformValidationResult(ok=True)),
            patch("vibeops.cost.infracost.run_infracost", return_value=None),
        ):
            graph.invoke(initial.model_dump(), thread)
            graph.update_state(thread, {"approved": False})
            graph.invoke(None, thread)

        deploy_spy.assert_not_called()
