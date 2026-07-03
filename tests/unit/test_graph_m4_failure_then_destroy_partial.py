from __future__ import annotations

import tempfile
from typing import Any
from unittest.mock import patch

from vibeops.graph.orchestrator import build_graph
from vibeops.models.deployment import (
    DeploymentOutcome,
    DeploymentPhase,
    DestroyResult,
    PlanResult,
    StateResource,
)
from vibeops.models.iac import TerraformValidationResult
from vibeops.models.state import GraphState
from vibeops.terraform.errors import TerraformApplyError


class TestGraphM4FailureThenDestroyPartial:
    def test_partial_fail_then_destroy_succeeds(self) -> None:
        graph = build_graph()
        thread: dict[str, Any] = {"configurable": {"thread_id": "m4-partial-destroy"}}
        initial = GraphState(user_prompt="deploy")
        tmp = tempfile.mkdtemp()
        created = [StateResource(type="google_compute_instance", name="vm", zone="us-central1-a")]

        with (
            patch("vibeops.agents.iac.init"),
            patch("vibeops.agents.iac.validate", return_value=TerraformValidationResult(ok=True)),
            patch("vibeops.cost.infracost.run_infracost", return_value=None),
        ):
            graph.invoke(initial.model_dump(), thread)
            graph.update_state(thread, {"approved": True, "terraform_dir": tmp})

            apply_fail = TerraformApplyError("disk fail", partial_state=True, created_resources=created)
            with (
                patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file=f"{tmp}/tfplan")),
                patch("vibeops.agents.deployment.runner.apply", side_effect=apply_fail),
            ):
                graph.invoke(None, thread)

        # deployment_decision pause — user requests destroy and confirms in one step
        # (destroy_confirm is not an interrupt; one invoke goes all the way to destroy_agent)
        graph.update_state(thread, {"destroy_requested": True, "destroy_confirmed": True})
        with patch("vibeops.agents.deployment.runner.destroy", return_value=DestroyResult(full_log="done", resources_destroyed=1)):
            graph.invoke(None, thread)

        # back at deployment_decision — route to END (destroy_requested reset by destroy_agent)
        graph.invoke(None, thread)

        snapshot = dict(graph.get_state(thread).values)
        state = GraphState.model_validate(snapshot)
        assert state.deployment_outcome == DeploymentOutcome.DESTROYED
        assert state.deployment_phase == DeploymentPhase.DESTROYED
        assert state.created_resources == []
