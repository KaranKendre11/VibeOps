from __future__ import annotations

from unittest.mock import patch

from vibeops.agents.deployment import deployment_agent
from vibeops.models.deployment import ApplyResult, DeploymentOutcome, DeploymentPhase, PlanResult
from vibeops.models.state import FlowStage, GraphState


def _state_with_dir(terraform_dir: str = "/tmp/tf") -> GraphState:
    return GraphState(
        user_prompt="test",
        approved=True,
        stage=FlowStage.DEPLOYMENT,
        terraform_dir=terraform_dir,
    )


def _state_no_dir() -> GraphState:
    return GraphState(
        user_prompt="test",
        approved=True,
        stage=FlowStage.DEPLOYMENT,
    )


class TestDeploymentM4:
    """M4 deployment agent: real terraform plan+apply, no stub."""

    def test_deployment_calls_plan_and_apply(self) -> None:
        with (
            patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file="/tmp/tf/tfplan")) as mock_plan,
            patch("vibeops.agents.deployment.runner.apply", return_value=ApplyResult(full_log="done", resources_created=1)) as mock_apply,
            patch("vibeops.agents.deployment.runner.parse_state_resources", return_value=[]),
        ):
            deployment_agent(_state_with_dir())

        mock_plan.assert_called_once()
        mock_apply.assert_called_once()

    def test_deployment_succeeds_when_runner_succeeds(self) -> None:
        with (
            patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file="/tmp/tf/tfplan")),
            patch("vibeops.agents.deployment.runner.apply", return_value=ApplyResult(full_log="done", resources_created=1)),
            patch("vibeops.agents.deployment.runner.parse_state_resources", return_value=[]),
        ):
            result = deployment_agent(_state_with_dir())

        assert result.deployment_phase == DeploymentPhase.SUCCEEDED
        assert result.deployment_outcome == DeploymentOutcome.SUCCEEDED

    def test_no_terraform_dir_returns_failed(self) -> None:
        result = deployment_agent(_state_no_dir())
        assert result.deployment_phase == DeploymentPhase.FAILED
        assert result.deployment_outcome == DeploymentOutcome.PLAN_FAILED
