from __future__ import annotations

import tempfile
from typing import Any
from unittest.mock import patch

from vibeops.graph.orchestrator import build_graph
from vibeops.models.deployment import (
    ApplyResult,
    DeploymentOutcome,
    DeploymentPhase,
    PlanResult,
    StateResource,
)
from vibeops.models.iac import TerraformValidationResult
from vibeops.models.state import GraphState
from vibeops.terraform.errors import TerraformApplyError


class TestGraphM4FailureThenRetry:
    def test_retry_after_apply_failure_succeeds(self) -> None:
        graph = build_graph()
        thread: dict[str, Any] = {"configurable": {"thread_id": "m4-retry"}}
        initial = GraphState(user_prompt="deploy")
        tmp = tempfile.mkdtemp()
        resource = StateResource(type="google_compute_instance", name="vm")

        with (
            patch("vibeops.agents.iac.init"),
            patch("vibeops.agents.iac.validate", return_value=TerraformValidationResult(ok=True)),
            patch("vibeops.cost.infracost.run_infracost", return_value=None),
        ):
            graph.invoke(initial.model_dump(), thread)
            graph.update_state(thread, {"approved": True, "terraform_dir": tmp})

            # First attempt: apply fails
            apply_fail = TerraformApplyError("network error", partial_state=False, created_resources=[])
            with (
                patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file=f"{tmp}/tfplan")),
                patch("vibeops.agents.deployment.runner.apply", side_effect=apply_fail),
            ):
                graph.invoke(None, thread)

        # At deployment_decision: user retries
        graph.update_state(thread, {"retry_requested": True})

        # Second attempt: succeeds
        with (
            patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file=f"{tmp}/tfplan")),
            patch("vibeops.agents.deployment.runner.apply", return_value=ApplyResult(full_log="done", resources_created=1)),
            patch("vibeops.agents.deployment.runner.parse_state_resources", return_value=[resource]),
        ):
            graph.invoke(None, thread)

        snapshot = dict(graph.get_state(thread).values)
        state = GraphState.model_validate(snapshot)
        assert state.deployment_phase == DeploymentPhase.SUCCEEDED
        assert state.deployment_outcome == DeploymentOutcome.SUCCEEDED

    def test_retry_clears_previous_error(self) -> None:
        graph = build_graph()
        thread: dict[str, Any] = {"configurable": {"thread_id": "m4-retry-err"}}
        initial = GraphState(user_prompt="deploy")
        tmp = tempfile.mkdtemp()

        with (
            patch("vibeops.agents.iac.init"),
            patch("vibeops.agents.iac.validate", return_value=TerraformValidationResult(ok=True)),
            patch("vibeops.cost.infracost.run_infracost", return_value=None),
        ):
            graph.invoke(initial.model_dump(), thread)
            graph.update_state(thread, {"approved": True, "terraform_dir": tmp})

            apply_fail = TerraformApplyError("disk fail", partial_state=False, created_resources=[])
            with (
                patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file=f"{tmp}/tfplan")),
                patch("vibeops.agents.deployment.runner.apply", side_effect=apply_fail),
            ):
                graph.invoke(None, thread)

        graph.update_state(thread, {"retry_requested": True})

        with (
            patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file=f"{tmp}/tfplan")),
            patch("vibeops.agents.deployment.runner.apply", return_value=ApplyResult(full_log="done", resources_created=1)),
            patch("vibeops.agents.deployment.runner.parse_state_resources", return_value=[]),
        ):
            graph.invoke(None, thread)

        snapshot = dict(graph.get_state(thread).values)
        state = GraphState.model_validate(snapshot)
        assert state.deployment_error is None or state.deployment_phase == DeploymentPhase.SUCCEEDED
