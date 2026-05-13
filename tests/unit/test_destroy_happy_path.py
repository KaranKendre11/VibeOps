from __future__ import annotations

from unittest.mock import patch

from vibeops.agents.deployment import destroy_agent
from vibeops.models.deployment import DeploymentOutcome, DeploymentPhase, DestroyResult, StateResource
from vibeops.models.state import GraphState


def _state() -> GraphState:
    return GraphState(
        user_prompt="test",
        terraform_dir="/tmp/tf",
        destroy_confirmed=True,
        deployment_phase=DeploymentPhase.AWAITING_DESTROY_CONFIRM,
        created_resources=[StateResource(type="google_compute_instance", name="vm")],
    )


def test_destroy_outcome_destroyed() -> None:
    with patch("vibeops.agents.deployment.runner.destroy", return_value=DestroyResult(full_log="done", resources_destroyed=1)):
        result = destroy_agent(_state())

    assert result.deployment_outcome == DeploymentOutcome.DESTROYED


def test_destroy_phase_destroyed() -> None:
    with patch("vibeops.agents.deployment.runner.destroy", return_value=DestroyResult(full_log="done", resources_destroyed=1)):
        result = destroy_agent(_state())

    assert result.deployment_phase == DeploymentPhase.DESTROYED


def test_destroy_logs_accumulated() -> None:
    with patch("vibeops.agents.deployment.runner.destroy", return_value=DestroyResult(full_log="Destroying...\nDone.", resources_destroyed=1)):
        result = destroy_agent(_state())

    assert len(result.deployment_logs) > 0


def test_destroy_clears_created_resources() -> None:
    with patch("vibeops.agents.deployment.runner.destroy", return_value=DestroyResult(full_log="done", resources_destroyed=1)):
        result = destroy_agent(_state())

    assert result.created_resources == []
