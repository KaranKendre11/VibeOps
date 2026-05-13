from __future__ import annotations

import json
import tempfile
from typing import Any
from unittest.mock import MagicMock, patch

from vibeops.core.gcp_context import GcpContext
from vibeops.core.llm import LLMClient
from vibeops.graph.orchestrator import build_graph
from vibeops.models.conversation import ConversationTurn, RequirementPhase, TurnRole
from vibeops.models.deployment import ApplyResult, DeploymentOutcome, DeploymentPhase, PlanResult, StateResource
from vibeops.models.iac import TerraformValidationResult
from vibeops.models.results import (
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


def _first_message_result() -> MagicMock:
    resp = MagicMock()
    resp.content = "T4 VM for inference. Ready to deploy?"
    resp.input_tokens = 50
    resp.output_tokens = 20
    return resp


def _extraction_result() -> MagicMock:
    resp = MagicMock()
    resp.content = json.dumps({
        "workload_intent": "inference_small",
        "gpu_type": "nvidia-tesla-t4",
        "gpu_count": 1,
        "cpu_floor": "8",
        "memory_floor": "32",
        "os_family": "deeplearning-platform-release",
        "disk_size_gb": 100,
        "preemptible": False,
        "region_preference": "none",
    })
    resp.input_tokens = 100
    resp.output_tokens = 50
    return resp


def _ctx() -> MagicMock:
    ctx = MagicMock(spec=GcpContext)
    ctx.project_id = "test-project"
    ctx.service_account_info = {"type": "service_account"}
    ctx.get_cached.return_value = None
    ctx.set_cached.return_value = None
    return ctx


def _build_zones_result() -> ZonesWithAcceleratorResult:
    zones = [ZoneAvailability(zone="us-central1-a", region="us-central1", gpu_available=True, quota_total=4, quota_used=0)]
    return ZonesWithAcceleratorResult(gpu_type="nvidia-tesla-t4", zones=zones)


def _build_machines_result() -> MachineTypesResult:
    machines = [MachineType(name="n1-standard-8", cpus=8, memory_gb=32.0, gpu_compatible=True)]
    return MachineTypesResult(zone="us-central1-a", machine_types=machines)


class TestGraphM4HappyPath:
    def test_full_flow_deployment_succeeded(self) -> None:
        llm = MagicMock(spec=LLMClient)
        llm.chat_completion.side_effect = [_first_message_result(), _extraction_result()]
        ctx = _ctx()

        graph = build_graph()
        thread: dict[str, Any] = {
            "configurable": {"thread_id": "m4-happy", "llm_client": llm, "gcp_context": ctx}
        }
        initial = GraphState(user_prompt="deploy T4 VM")
        tmp = tempfile.mkdtemp()
        resource = StateResource(type="google_compute_instance", name="vm", zone="us-central1-a")

        with (
            patch("vibeops.agents.architecture.list_zones_with_accelerator", return_value=_build_zones_result()),
            patch("vibeops.agents.architecture.get_accelerator_quota", return_value=QuotaResult(region="us-central1", gpu_type="nvidia-tesla-t4", limit=4, usage=0)),
            patch("vibeops.agents.architecture.list_machine_types", return_value=_build_machines_result()),
            patch("vibeops.agents.architecture.list_existing_networks", return_value=NetworksResult(networks=[Network(name="default", self_link="", auto_create_subnetworks=True)])),
            patch("vibeops.agents.architecture.resolve_os_image", return_value=_RESOLVED_OS),
            patch("vibeops.agents.iac.init"),
            patch("vibeops.agents.iac.validate", return_value=TerraformValidationResult(ok=True)),
            patch("vibeops.cost.infracost.run_infracost", return_value=None),
        ):
            # First invoke: initial message, pauses at asking_pause
            graph.invoke(initial.model_dump(), thread)
            snapshot = dict(graph.get_state(thread).values)
            state = GraphState.model_validate(snapshot)

            # Simulate conversation completion
            existing = [t.model_dump() for t in state.conversation]
            existing.append(ConversationTurn(role=TurnRole.USER, content="yes go ahead").model_dump())
            graph.update_state(
                thread,
                {
                    "conversation": existing,
                    "requirement_phase": RequirementPhase.RESUMING_CONFIRMATION.value,
                },
            )
            graph.invoke(None, thread)
            graph.update_state(thread, {"architecture_response": {"candidate_index": 0, "network_name": "default"}})
            graph.invoke(None, thread)

            # At review — approve
            graph.update_state(thread, {"approved": True, "terraform_dir": tmp})
            with (
                patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file=f"{tmp}/tfplan")),
                patch("vibeops.agents.deployment.runner.apply", return_value=ApplyResult(full_log="Apply complete!", resources_created=1)),
                patch("vibeops.agents.deployment.runner.parse_state_resources", return_value=[resource]),
            ):
                graph.invoke(None, thread)

        snapshot = dict(graph.get_state(thread).values)
        state = GraphState.model_validate(snapshot)
        assert state.deployment_phase == DeploymentPhase.SUCCEEDED
        assert state.deployment_outcome == DeploymentOutcome.SUCCEEDED
        assert len(state.created_resources) == 1

    def test_full_flow_then_leave_as_is(self) -> None:
        """After SUCCEEDED, user chooses leave-as-is → graph ends."""
        graph = build_graph()
        thread: dict[str, Any] = {"configurable": {"thread_id": "m4-leave"}}
        initial = GraphState(user_prompt="deploy T4 VM")
        tmp = tempfile.mkdtemp()

        with (
            patch("vibeops.agents.iac.init"),
            patch("vibeops.agents.iac.validate", return_value=TerraformValidationResult(ok=True)),
            patch("vibeops.cost.infracost.run_infracost", return_value=None),
        ):
            graph.invoke(initial.model_dump(), thread)
            graph.update_state(thread, {"approved": True, "terraform_dir": tmp})
            with (
                patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file=f"{tmp}/tfplan")),
                patch("vibeops.agents.deployment.runner.apply", return_value=ApplyResult(full_log="done", resources_created=1)),
                patch("vibeops.agents.deployment.runner.parse_state_resources", return_value=[]),
            ):
                graph.invoke(None, thread)

        # deployment_decision pause: user leaves
        graph.update_state(thread, {"leave_as_is_requested": True})
        graph.invoke(None, thread)

        snapshot = dict(graph.get_state(thread).values)
        state = GraphState.model_validate(snapshot)
        assert state.deployment_outcome == DeploymentOutcome.SUCCEEDED
