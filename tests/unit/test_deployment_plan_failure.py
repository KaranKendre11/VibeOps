from __future__ import annotations

from unittest.mock import patch

from vibeops.agents.deployment import deployment_agent
from vibeops.models.deployment import DeploymentOutcome, DeploymentPhase
from vibeops.models.state import FlowStage, GraphState
from vibeops.terraform.errors import TerraformPlanError


def _state() -> GraphState:
    return GraphState(
        user_prompt="deploy",
        terraform_dir="/tmp/tf",
        approved=True,
        stage=FlowStage.AWAITING_APPROVAL,
    )


def test_plan_failure_outcome() -> None:
    with patch("vibeops.agents.deployment.runner.plan", side_effect=TerraformPlanError("quota error")):
        result = deployment_agent(_state())

    assert result.deployment_outcome == DeploymentOutcome.PLAN_FAILED


def test_plan_failure_phase() -> None:
    with patch("vibeops.agents.deployment.runner.plan", side_effect=TerraformPlanError("fail")):
        result = deployment_agent(_state())

    assert result.deployment_phase == DeploymentPhase.FAILED


def test_plan_failure_no_apply_attempted() -> None:
    with (
        patch("vibeops.agents.deployment.runner.plan", side_effect=TerraformPlanError("fail")),
        patch("vibeops.agents.deployment.runner.apply") as mock_apply,
    ):
        deployment_agent(_state())

    mock_apply.assert_not_called()


def test_plan_failure_error_captured() -> None:
    with patch("vibeops.agents.deployment.runner.plan", side_effect=TerraformPlanError("quota exceeded")):
        result = deployment_agent(_state())

    assert result.deployment_error is not None
    assert len(result.deployment_error) > 0
