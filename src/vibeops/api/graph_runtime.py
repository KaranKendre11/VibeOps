"""Shared LangGraph runtime helpers used by the API routers.

Assembling the `configurable`, building/caching the per-session graph, deriving the UI stage, and
serializing a state snapshot — used by both the graph and chat routers.
"""
from __future__ import annotations

from typing import Any

from vibeops.api.session import Session
from vibeops.graph.orchestrator import build_graph
from vibeops.models.conversation import RequirementPhase
from vibeops.models.deployment import DeploymentPhase
from vibeops.models.state import FlowStage, GraphState

_ACTIVE_DEPLOYMENT = {
    DeploymentPhase.PLANNING,
    DeploymentPhase.APPLYING,
    DeploymentPhase.SUCCEEDED,
    DeploymentPhase.FAILED,
    DeploymentPhase.AWAITING_DESTROY_CONFIRM,
    DeploymentPhase.DESTROYING,
    DeploymentPhase.DESTROYED,
}


def derive_stage(state: GraphState) -> str:
    """Map GraphState -> the UI screen key (server-side port of ui.graph_sync)."""
    if state.deployment_phase in _ACTIVE_DEPLOYMENT:
        return "deployment"
    if state.stage == FlowStage.AWAITING_APPROVAL:
        return "review"
    if state.requirement_phase in (RequirementPhase.ASKING, RequirementPhase.AWAITING_CONFIRMATION):
        return "chat"
    if state.stage == FlowStage.AWAITING_ARCHITECTURE:
        return "architecture"
    if state.stage == FlowStage.CANCELLED:
        return "cancelled"
    if state.stage == FlowStage.DONE:
        return "done"
    return "idle"


def thread_config(session: Session) -> dict[str, Any]:
    """Assemble the LangGraph `configurable` from the session (creds built lazily here)."""
    session.ensure_clients()
    configurable: dict[str, Any] = {"thread_id": session.thread_id}
    if session.llm_client is not None or session.gcp_context is not None:
        configurable["llm_client"] = session.llm_client
        configurable["gcp_context"] = session.gcp_context
    if session.demo_mode:
        configurable["demo_mode"] = True
    return {"configurable": configurable}


def get_graph(session: Session) -> Any:
    if session.graph is None:
        session.graph = build_graph()
    return session.graph


def snapshot(graph: Any, thread: dict[str, Any]) -> dict[str, Any]:
    values = graph.get_state(thread).values
    if not values:  # fresh thread — no checkpoint yet
        return {"stage": "idle", "state": None}
    state = GraphState.model_validate(values)
    return {"stage": derive_stage(state), "state": state.model_dump(mode="json")}
