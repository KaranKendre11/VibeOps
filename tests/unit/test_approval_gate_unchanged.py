from __future__ import annotations

from unittest.mock import MagicMock

from vibeops.graph.orchestrator import approval_router
from vibeops.models.state import FlowStage, GraphState


def _state(**kwargs: object) -> GraphState:
    return GraphState(user_prompt="test", **kwargs)  # type: ignore[arg-type]


class TestApprovalGateUnchanged:
    def test_unapproved_routes_to_cancelled(self) -> None:
        state = _state(approved=False, stage=FlowStage.AWAITING_APPROVAL)
        assert approval_router(state) == "cancelled"

    def test_approved_routes_to_deployment(self) -> None:
        state = _state(approved=True, stage=FlowStage.AWAITING_APPROVAL)
        assert approval_router(state) == "deployment"

    def test_deployment_node_unreachable_without_approval(self, mocker: MagicMock) -> None:
        from vibeops.graph.orchestrator import build_graph

        deploy_spy = mocker.patch("vibeops.agents.deployment.deployment_agent")
        graph = build_graph()
        thread = {"configurable": {"thread_id": "gate-test-m3"}}

        initial = GraphState(user_prompt="test prompt")
        graph.invoke(initial.model_dump(), thread)

        graph.update_state(thread, {"approved": False})
        graph.invoke(None, thread)

        deploy_spy.assert_not_called()
