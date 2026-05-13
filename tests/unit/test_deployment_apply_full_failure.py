from __future__ import annotations

from unittest.mock import patch

from vibeops.agents.deployment import deployment_agent
from vibeops.models.deployment import ApplyResult, DeploymentOutcome, DeploymentPhase, PlanResult
from vibeops.models.state import FlowStage, GraphState
from vibeops.terraform.errors import TerraformApplyError


def _state() -> GraphState:
    return GraphState(
        user_prompt="deploy",
        terraform_dir="/tmp/tf",
        approved=True,
        stage=FlowStage.AWAITING_APPROVAL,
    )


def test_full_failure_outcome() -> None:
    err = TerraformApplyError("API error", partial_state=False, created_resources=[])
    with (
        patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file="/tmp/tf/tfplan")),
        patch("vibeops.agents.deployment.runner.apply", side_effect=err),
    ):
        result = deployment_agent(_state())

    assert result.deployment_outcome == DeploymentOutcome.FULL_FAIL


def test_full_failure_phase() -> None:
    err = TerraformApplyError("fail", partial_state=False, created_resources=[])
    with (
        patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file="/tmp/tf/tfplan")),
        patch("vibeops.agents.deployment.runner.apply", side_effect=err),
    ):
        result = deployment_agent(_state())

    assert result.deployment_phase == DeploymentPhase.FAILED


def test_full_failure_created_resources_empty() -> None:
    err = TerraformApplyError("fail", partial_state=False, created_resources=[])
    with (
        patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file="/tmp/tf/tfplan")),
        patch("vibeops.agents.deployment.runner.apply", side_effect=err),
    ):
        result = deployment_agent(_state())

    assert result.created_resources == []
