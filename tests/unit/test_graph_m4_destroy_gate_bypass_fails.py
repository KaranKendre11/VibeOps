from __future__ import annotations

import tempfile
from typing import Any
from unittest.mock import MagicMock, patch

from vibeops.graph.orchestrator import build_graph
from vibeops.models.deployment import ApplyResult, PlanResult, StateResource
from vibeops.models.iac import TerraformValidationResult
from vibeops.models.state import GraphState


class TestGraphM4DestroyGateBypassFails:
    def test_destroy_agent_not_called_without_confirm(self) -> None:
        """At the graph edge level, destroy_agent must not run without destroy_confirmed."""
        destroy_spy = MagicMock()
        graph = build_graph()
        thread: dict[str, Any] = {"configurable": {"thread_id": "m4-gate-bypass"}}
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
            with (
                patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file=f"{tmp}/tfplan")),
                patch("vibeops.agents.deployment.runner.apply", return_value=ApplyResult(full_log="done", resources_created=1)),
                patch("vibeops.agents.deployment.runner.parse_state_resources", return_value=[resource]),
            ):
                graph.invoke(None, thread)

        # Attempt bypass: set destroy_requested=True but destroy_confirmed=False
        graph.update_state(thread, {"destroy_requested": True, "destroy_confirmed": False})

        with patch("vibeops.agents.deployment.destroy_agent", side_effect=destroy_spy):
            graph.invoke(None, thread)
            graph.invoke(None, thread)  # second invoke after destroy_blocked

        destroy_spy.assert_not_called()

    def test_confirmed_false_goes_to_blocked_not_destroy(self) -> None:
        """destroy_router returning 'blocked' routes to destroy_blocked, not destroy."""
        from vibeops.graph.orchestrator import destroy_router
        from vibeops.models.state import GraphState

        state = GraphState(user_prompt="t", destroy_confirmed=False)
        assert destroy_router(state) == "blocked"
