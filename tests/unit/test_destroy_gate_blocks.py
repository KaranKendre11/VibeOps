from __future__ import annotations

from unittest.mock import MagicMock, patch

from vibeops.graph.orchestrator import build_graph, destroy_router
from vibeops.models.deployment import DeploymentPhase
from vibeops.models.state import FlowStage, GraphState


def _state(**kwargs: object) -> GraphState:
    return GraphState(user_prompt="test prompt", **kwargs)  # type: ignore[arg-type]


def test_no_confirm_routes_to_blocked() -> None:
    state = _state(destroy_confirmed=False, deployment_phase=DeploymentPhase.AWAITING_DESTROY_CONFIRM)
    assert destroy_router(state) == "blocked"


def test_only_literal_true_unlocks_destroy() -> None:
    for falsy in (False, None):
        state = GraphState.model_construct(
            user_prompt="test",
            destroy_confirmed=falsy,
            deployment_phase=DeploymentPhase.AWAITING_DESTROY_CONFIRM,
            chat_history=[],
            terraform_files={},
            stage=FlowStage.REQUIREMENT,
            created_resources=[],
            deployment_logs=[],
            validation_errors=[],
        )
        assert destroy_router(state) != "destroy", f"destroy_confirmed={falsy!r} should not destroy"


def test_confirmed_routes_to_destroy() -> None:
    state = _state(destroy_confirmed=True, deployment_phase=DeploymentPhase.AWAITING_DESTROY_CONFIRM)
    assert destroy_router(state) == "destroy"


def test_destroy_node_unreachable_without_confirmation(mocker: MagicMock) -> None:
    """Compiled graph must not reach destroy_agent when destroy_confirmed=False."""
    from vibeops.models.iac import TerraformValidationResult

    destroy_spy = mocker.patch("vibeops.agents.deployment.destroy_agent")
    deploy_mock = mocker.patch(
        "vibeops.agents.deployment.deployment_agent",
        return_value=GraphState(
            user_prompt="test",
            deployment_phase=DeploymentPhase.SUCCEEDED,
            stage=FlowStage.DEPLOYMENT,
        ),
    )

    graph = build_graph()
    thread: dict = {"configurable": {"thread_id": "destroy-gate-test"}}
    initial = GraphState(user_prompt="test prompt")

    with (
        patch("vibeops.agents.iac.init"),
        patch("vibeops.agents.iac.validate", return_value=TerraformValidationResult(ok=True)),
        patch("vibeops.cost.infracost.run_infracost", return_value=None),
    ):
        graph.invoke(initial.model_dump(), thread)
        # Approve → deployment runs
        graph.update_state(thread, {"approved": True})
        graph.invoke(None, thread)

    # At deployment_decision pause — set destroy_requested but NOT destroy_confirmed
    graph.update_state(thread, {"destroy_requested": True, "destroy_confirmed": False})
    graph.invoke(None, thread)

    # destroy_agent must never have been called
    destroy_spy.assert_not_called()
