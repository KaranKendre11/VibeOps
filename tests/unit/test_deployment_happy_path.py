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


def _state() -> GraphState:
    return GraphState(
        user_prompt="deploy T4",
        terraform_dir="/tmp/tf",
        approved=True,
        stage=FlowStage.AWAITING_APPROVAL,
    )


def test_happy_path_outcome_succeeded() -> None:
    resources = [StateResource(type="google_compute_instance", name="vm", zone="us-central1-a")]
    with (
        patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file="/tmp/tf/tfplan", add_count=1)),
        patch("vibeops.agents.deployment.runner.apply", return_value=ApplyResult(full_log="Apply complete! Resources: 1 added.", resources_created=1)),
        patch("vibeops.agents.deployment.runner.parse_state_resources", return_value=resources),
    ):
        result = deployment_agent(_state())

    assert result.deployment_outcome == DeploymentOutcome.SUCCEEDED


def test_happy_path_phase_succeeded() -> None:
    resources = [StateResource(type="google_compute_instance", name="vm")]
    with (
        patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file="/tmp/tf/tfplan", add_count=1)),
        patch("vibeops.agents.deployment.runner.apply", return_value=ApplyResult(full_log="done", resources_created=1)),
        patch("vibeops.agents.deployment.runner.parse_state_resources", return_value=resources),
    ):
        result = deployment_agent(_state())

    assert result.deployment_phase == DeploymentPhase.SUCCEEDED


def test_happy_path_created_resources_populated() -> None:
    resources = [
        StateResource(type="google_compute_instance", name="vm", zone="us-central1-a"),
        StateResource(type="google_compute_disk", name="disk"),
    ]
    with (
        patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file="/tmp/tf/tfplan", add_count=2)),
        patch("vibeops.agents.deployment.runner.apply", return_value=ApplyResult(full_log="done", resources_created=2)),
        patch("vibeops.agents.deployment.runner.parse_state_resources", return_value=resources),
    ):
        result = deployment_agent(_state())

    assert len(result.created_resources) == 2


def test_happy_path_logs_accumulated() -> None:
    with (
        patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file="/tmp/tf/tfplan", add_count=1)),
        patch("vibeops.agents.deployment.runner.apply", return_value=ApplyResult(full_log="line1\nline2", resources_created=1)),
        patch("vibeops.agents.deployment.runner.parse_state_resources", return_value=[]),
    ):
        result = deployment_agent(_state())

    assert len(result.deployment_logs) > 0
