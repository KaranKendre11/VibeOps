from __future__ import annotations

from unittest.mock import patch

from vibeops.agents.deployment import destroy_agent
from vibeops.models.deployment import DeploymentOutcome, DeploymentPhase, StateResource
from vibeops.models.state import GraphState
from vibeops.terraform.errors import TerraformDestroyError


def _state() -> GraphState:
    return GraphState(
        user_prompt="test",
        terraform_dir="/tmp/tf",
        destroy_confirmed=True,
        deployment_phase=DeploymentPhase.AWAITING_DESTROY_CONFIRM,
        created_resources=[StateResource(type="google_compute_instance", name="vm")],
    )


def test_destroy_failure_outcome() -> None:
    remaining = [StateResource(type="google_compute_instance", name="vm")]
    err = TerraformDestroyError("dependent resource", created_resources=remaining)
    with patch("vibeops.agents.deployment.runner.destroy", side_effect=err):
        result = destroy_agent(_state())

    assert result.deployment_outcome == DeploymentOutcome.DESTROY_FAILED


def test_destroy_failure_phase() -> None:
    err = TerraformDestroyError("fail", created_resources=[])
    with patch("vibeops.agents.deployment.runner.destroy", side_effect=err):
        result = destroy_agent(_state())

    assert result.deployment_phase == DeploymentPhase.FAILED


def test_destroy_failure_preserves_remaining_resources() -> None:
    remaining = [StateResource(type="google_compute_instance", name="vm")]
    err = TerraformDestroyError("fail", created_resources=remaining)
    with patch("vibeops.agents.deployment.runner.destroy", side_effect=err):
        result = destroy_agent(_state())

    assert len(result.created_resources) == 1
