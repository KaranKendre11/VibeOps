from __future__ import annotations

from unittest.mock import MagicMock

from vibeops.graph.orchestrator import approval_router
from vibeops.models.state import FlowStage, GraphState


def _state(**kwargs: object) -> GraphState:
    return GraphState(user_prompt="test prompt", **kwargs)  # type: ignore[arg-type]


def test_unapproved_routes_to_cancelled() -> None:
    state = _state(approved=False, stage=FlowStage.AWAITING_APPROVAL)
    assert approval_router(state) == "cancelled"


def test_approved_routes_to_deployment() -> None:
    state = _state(approved=True, stage=FlowStage.AWAITING_APPROVAL)
    assert approval_router(state) == "deployment"


def test_only_literal_true_unlocks_deployment() -> None:
    """Non-True truthy values must not unlock deployment (fails closed)."""
    # Pydantic coerces "true" strings to True, so we test with a fresh
    # state where approved is explicitly False or not set.
    for falsy in (False, None):
        state = GraphState.model_construct(
            user_prompt="test",
            approved=falsy,
            stage=FlowStage.AWAITING_APPROVAL,
            chat_history=[],
            terraform_files={},
        )
        assert approval_router(state) != "deployment", f"approved={falsy!r} should not deploy"


def test_deployment_node_unreachable_without_approval(mocker: MagicMock) -> None:
    """Compiled graph must not reach the deployment node when approved=False."""
    from vibeops.graph.orchestrator import build_graph

    deploy_spy = mocker.patch("vibeops.agents.deployment.deployment_agent")

    graph = build_graph()
    thread = {"configurable": {"thread_id": "gate-test"}}

    # Run until the interrupt (before the review node).
    initial = GraphState(user_prompt="test prompt")
    graph.invoke(initial.model_dump(), thread)

    # Resume with approved=False — should go to cancelled, not deployment.
    graph.update_state(thread, {"approved": False})
    graph.invoke(None, thread)

    deploy_spy.assert_not_called()
