from __future__ import annotations

from unittest.mock import patch

from vibeops.agents.deployment import deployment_agent
from vibeops.models.deployment import DeploymentOutcome, DeploymentPhase, PlanResult, StateResource
from vibeops.models.state import FlowStage, GraphState
from vibeops.terraform.errors import TerraformApplyError


def _state() -> GraphState:
    return GraphState(
        user_prompt="deploy",
        terraform_dir="/tmp/tf",
        approved=True,
        stage=FlowStage.AWAITING_APPROVAL,
    )


_ONE_RESOURCE = [StateResource(type="google_compute_instance", name="vm", zone="us-central1-a")]


def test_partial_failure_outcome() -> None:
    err = TerraformApplyError("disk attach failed", partial_state=True, created_resources=_ONE_RESOURCE)
    with (
        patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file="/tmp/tf/tfplan")),
        patch("vibeops.agents.deployment.runner.apply", side_effect=err),
    ):
        result = deployment_agent(_state())

    assert result.deployment_outcome == DeploymentOutcome.PARTIAL_FAIL


def test_partial_failure_resources_preserved() -> None:
    err = TerraformApplyError("fail", partial_state=True, created_resources=_ONE_RESOURCE)
    with (
        patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file="/tmp/tf/tfplan")),
        patch("vibeops.agents.deployment.runner.apply", side_effect=err),
    ):
        result = deployment_agent(_state())

    assert len(result.created_resources) == 1
    assert result.created_resources[0].name == "vm"


def test_partial_failure_phase_is_failed() -> None:
    err = TerraformApplyError("fail", partial_state=True, created_resources=_ONE_RESOURCE)
    with (
        patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file="/tmp/tf/tfplan")),
        patch("vibeops.agents.deployment.runner.apply", side_effect=err),
    ):
        result = deployment_agent(_state())

    assert result.deployment_phase == DeploymentPhase.FAILED
