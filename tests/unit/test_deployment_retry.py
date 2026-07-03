from __future__ import annotations

from unittest.mock import patch

from vibeops.agents.deployment import deployment_agent
from vibeops.models.deployment import (
    ApplyResult,
    DeploymentOutcome,
    DeploymentPhase,
    PlanResult,
    StateResource,
)
from vibeops.models.state import FlowStage, GraphState


def _failed_state() -> GraphState:
    return GraphState(
        user_prompt="deploy",
        terraform_dir="/tmp/tf",
        approved=True,
        stage=FlowStage.DEPLOYMENT,
        deployment_phase=DeploymentPhase.FAILED,
        retry_requested=True,
        deployment_logs=["old log"],
    )


def test_retry_clears_previous_logs() -> None:
    resources = [StateResource(type="google_compute_instance", name="vm")]
    with (
        patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file="/tmp/tf/tfplan")),
        patch("vibeops.agents.deployment.runner.apply", return_value=ApplyResult(full_log="new log", resources_created=1)),
        patch("vibeops.agents.deployment.runner.parse_state_resources", return_value=resources),
    ):
        result = deployment_agent(_failed_state())

    assert "old log" not in result.deployment_logs


def test_retry_clears_retry_requested_flag() -> None:
    resources = [StateResource(type="google_compute_instance", name="vm")]
    with (
        patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file="/tmp/tf/tfplan")),
        patch("vibeops.agents.deployment.runner.apply", return_value=ApplyResult(full_log="done", resources_created=1)),
        patch("vibeops.agents.deployment.runner.parse_state_resources", return_value=resources),
    ):
        result = deployment_agent(_failed_state())

    assert result.retry_requested is False


def test_retry_succeeds_after_previous_failure() -> None:
    resources = [StateResource(type="google_compute_instance", name="vm")]
    with (
        patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file="/tmp/tf/tfplan")),
        patch("vibeops.agents.deployment.runner.apply", return_value=ApplyResult(full_log="done", resources_created=1)),
        patch("vibeops.agents.deployment.runner.parse_state_resources", return_value=resources),
    ):
        result = deployment_agent(_failed_state())

    assert result.deployment_outcome == DeploymentOutcome.SUCCEEDED
    assert result.deployment_phase == DeploymentPhase.SUCCEEDED
