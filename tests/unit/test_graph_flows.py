from __future__ import annotations

from typing import Any
from unittest.mock import patch

from vibeops.graph.orchestrator import build_graph
from vibeops.models.deployment import ApplyResult, DeploymentOutcome, DeploymentPhase, PlanResult
from vibeops.models.state import FlowStage, GraphState

_Thread = dict[str, Any]


def _thread(tid: str) -> _Thread:
    return {"configurable": {"thread_id": tid}}


def _run_to_interrupt(graph: Any, thread: _Thread) -> dict[str, Any]:
    """Invoke graph from initial state; return state snapshot at the interrupt point."""
    initial = GraphState(user_prompt="get me a T4 GPU VM")
    graph.invoke(initial.model_dump(), thread)
    return dict(graph.get_state(thread).values)


def _resume_and_leave(graph: Any, thread: _Thread) -> dict[str, Any]:
    """Approve, run deployment (mocked runner), then choose leave-as-is to reach END."""
    import tempfile

    # IaC stub doesn't set terraform_dir; inject a temp dir so deployment_agent can run
    tmp = tempfile.mkdtemp(prefix="vibeops_graphflow_")
    graph.update_state(thread, {"approved": True, "terraform_dir": tmp})

    with (
        patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file=f"{tmp}/tfplan")),
        patch("vibeops.agents.deployment.runner.apply", return_value=ApplyResult(full_log="done", resources_created=1)),
        patch("vibeops.agents.deployment.runner.parse_state_resources", return_value=[]),
    ):
        graph.invoke(None, thread)
    # Now at deployment_decision pause — choose leave-as-is
    graph.update_state(thread, {"leave_as_is_requested": True})
    graph.invoke(None, thread)
    return dict(graph.get_state(thread).values)


def _resume(graph: Any, thread: _Thread, approved: bool) -> dict[str, Any]:
    """Update approved flag and resume from the interrupt point."""
    graph.update_state(thread, {"approved": approved})
    graph.invoke(None, thread)
    return dict(graph.get_state(thread).values)


class TestHappyPath:
    def test_full_approved_flow_reaches_succeeded(self) -> None:
        graph = build_graph()
        thread = _thread("happy-path-test")

        snapshot = _run_to_interrupt(graph, thread)
        assert snapshot["stage"] == FlowStage.AWAITING_APPROVAL
        assert snapshot["terraform_files"]

        final = _resume_and_leave(graph, thread)
        assert final["deployment_phase"] == DeploymentPhase.SUCCEEDED.value

    def test_approved_flow_deployment_outcome(self) -> None:
        graph = build_graph()
        thread = _thread("happy-path-outcome")

        _run_to_interrupt(graph, thread)
        final = _resume_and_leave(graph, thread)
        assert final["deployment_outcome"] == DeploymentOutcome.SUCCEEDED.value


class TestCancelPath:
    def test_cancel_ends_cancelled(self) -> None:
        graph = build_graph()
        thread = _thread("cancel-test")

        _run_to_interrupt(graph, thread)
        final = _resume(graph, thread, approved=False)
        assert final["stage"] == FlowStage.CANCELLED

    def test_cancel_leaves_terraform_files_intact(self) -> None:
        """Cancellation must not wipe the generated Terraform files."""
        graph = build_graph()
        thread = _thread("cancel-files-test")

        _run_to_interrupt(graph, thread)
        final = _resume(graph, thread, approved=False)
        assert final["terraform_files"]
