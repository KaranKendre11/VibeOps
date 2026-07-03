"""deployment_agent forwards runner logs to an external on_log sink from config (for SSE)."""
from __future__ import annotations

import tempfile
from typing import Any
from unittest.mock import patch

from vibeops.agents.deployment import deployment_agent
from vibeops.models.deployment import ApplyResult, DeploymentPhase, PlanResult
from vibeops.models.state import FlowStage, GraphState


def test_deployment_forwards_logs_to_external_sink() -> None:
    collected: list[str] = []
    state = GraphState(
        user_prompt="x",
        stage=FlowStage.DEPLOYMENT,
        approved=True,
        terraform_dir=tempfile.mkdtemp(prefix="vibeops_onlog_"),
    )
    config = {"configurable": {"on_log": collected.append}}

    def fake_apply(work_dir: Any, on_log: Any = None, **kwargs: Any) -> ApplyResult:
        on_log("Applying...")
        on_log("Apply complete!")
        return ApplyResult(full_log="Applying...\nApply complete!", resources_created=1)

    with (
        patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file="p")),
        patch("vibeops.agents.deployment.runner.apply", side_effect=fake_apply),
        patch("vibeops.agents.deployment.runner.parse_state_resources", return_value=[]),
    ):
        result = deployment_agent(state, config)

    assert result.deployment_phase == DeploymentPhase.SUCCEEDED
    assert "Applying..." in collected
    assert "Apply complete!" in collected


def test_deployment_without_sink_still_works() -> None:
    # Backward compat: no on_log in config → behaves exactly as before.
    state = GraphState(
        user_prompt="x",
        stage=FlowStage.DEPLOYMENT,
        approved=True,
        terraform_dir=tempfile.mkdtemp(prefix="vibeops_onlog_"),
    )
    with (
        patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file="p")),
        patch(
            "vibeops.agents.deployment.runner.apply",
            return_value=ApplyResult(full_log="done", resources_created=1),
        ),
        patch("vibeops.agents.deployment.runner.parse_state_resources", return_value=[]),
    ):
        result = deployment_agent(state)  # no config at all
    assert result.deployment_phase == DeploymentPhase.SUCCEEDED
