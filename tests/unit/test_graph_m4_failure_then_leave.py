from __future__ import annotations

import tempfile
from typing import Any
from unittest.mock import patch

from vibeops.graph.orchestrator import build_graph
from vibeops.models.deployment import DeploymentOutcome, DeploymentPhase, PlanResult
from vibeops.models.iac import TerraformValidationResult
from vibeops.models.state import GraphState
from vibeops.terraform.errors import TerraformApplyError


class TestGraphM4FailureThenLeave:
    def test_leave_as_is_preserves_failed_outcome(self) -> None:
        graph = build_graph()
        thread: dict[str, Any] = {"configurable": {"thread_id": "m4-leave-fail"}}
        initial = GraphState(user_prompt="deploy")
        tmp = tempfile.mkdtemp()

        with (
            patch("vibeops.agents.iac.init"),
            patch("vibeops.agents.iac.validate", return_value=TerraformValidationResult(ok=True)),
            patch("vibeops.cost.infracost.run_infracost", return_value=None),
        ):
            graph.invoke(initial.model_dump(), thread)
            graph.update_state(thread, {"approved": True, "terraform_dir": tmp})

            apply_fail = TerraformApplyError("API error", partial_state=False, created_resources=[])
            with (
                patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file=f"{tmp}/tfplan")),
                patch("vibeops.agents.deployment.runner.apply", side_effect=apply_fail),
            ):
                graph.invoke(None, thread)

        # At deployment_decision: user leaves as-is
        graph.update_state(thread, {"leave_as_is_requested": True})
        graph.invoke(None, thread)

        snapshot = dict(graph.get_state(thread).values)
        state = GraphState.model_validate(snapshot)
        assert state.deployment_phase == DeploymentPhase.FAILED
        assert state.deployment_outcome == DeploymentOutcome.FULL_FAIL

    def test_leave_as_is_destroy_agent_not_called(self) -> None:
        graph = build_graph()
        thread: dict[str, Any] = {"configurable": {"thread_id": "m4-leave-nondestroy"}}
        initial = GraphState(user_prompt="deploy")
        tmp = tempfile.mkdtemp()

        destroy_called = []

        with (
            patch("vibeops.agents.iac.init"),
            patch("vibeops.agents.iac.validate", return_value=TerraformValidationResult(ok=True)),
            patch("vibeops.cost.infracost.run_infracost", return_value=None),
        ):
            graph.invoke(initial.model_dump(), thread)
            graph.update_state(thread, {"approved": True, "terraform_dir": tmp})

            apply_fail = TerraformApplyError("fail", partial_state=False, created_resources=[])
            with (
                patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file=f"{tmp}/tfplan")),
                patch("vibeops.agents.deployment.runner.apply", side_effect=apply_fail),
                patch("vibeops.agents.deployment.runner.destroy", side_effect=lambda *a, **kw: destroy_called.append(True)),
            ):
                graph.invoke(None, thread)

        graph.update_state(thread, {"leave_as_is_requested": True})
        graph.invoke(None, thread)

        assert destroy_called == []
