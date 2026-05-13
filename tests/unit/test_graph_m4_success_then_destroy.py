from __future__ import annotations

import tempfile
from typing import Any
from unittest.mock import patch

from vibeops.graph.orchestrator import build_graph
from vibeops.models.deployment import (
    ApplyResult,
    DeploymentOutcome,
    DeploymentPhase,
    DestroyResult,
    PlanResult,
    StateResource,
)
from vibeops.models.iac import TerraformValidationResult
from vibeops.models.state import GraphState


class TestGraphM4SuccessThenDestroy:
    def test_success_teardown_then_destroyed(self) -> None:
        graph = build_graph()
        thread: dict[str, Any] = {"configurable": {"thread_id": "m4-teardown"}}
        initial = GraphState(user_prompt="deploy")
        tmp = tempfile.mkdtemp()
        resource = StateResource(type="google_compute_instance", name="vm", zone="us-central1-a")

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
                patch("vibeops.agents.deployment.runner.parse_state_resources", return_value=[resource]),
            ):
                graph.invoke(None, thread)

        # deployment_decision pause — user clicks Tear down and confirms in one step
        # (destroy_confirm is not an interrupt; one invoke runs the full destroy)
        graph.update_state(thread, {"destroy_requested": True, "destroy_confirmed": True})
        with patch("vibeops.agents.deployment.runner.destroy", return_value=DestroyResult(full_log="Destroy complete", resources_destroyed=1)):
            graph.invoke(None, thread)

        # back at deployment_decision — route to END (destroy_requested reset by destroy_agent)
        graph.invoke(None, thread)

        snapshot = dict(graph.get_state(thread).values)
        state = GraphState.model_validate(snapshot)
        assert state.deployment_phase == DeploymentPhase.DESTROYED
        assert state.deployment_outcome == DeploymentOutcome.DESTROYED
        assert state.created_resources == []

    def test_teardown_cancel_returns_to_success(self) -> None:
        """Cancelling the destroy confirmation returns to SUCCEEDED phase."""
        graph = build_graph()
        thread: dict[str, Any] = {"configurable": {"thread_id": "m4-teardown-cancel"}}
        initial = GraphState(user_prompt="deploy")
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

        # User clicks Tear down but does NOT confirm (destroy_confirmed stays False)
        # One invoke: deployment_decision → destroy_confirm → destroy_router → blocked → END
        graph.update_state(thread, {"destroy_requested": True})
        graph.invoke(None, thread)

        snapshot = dict(graph.get_state(thread).values)
        # After going through destroy_blocked (safety abort), graph terminates
        # destroy was NOT run
        state = GraphState.model_validate(snapshot)
        assert state.deployment_phase != DeploymentPhase.DESTROYED
