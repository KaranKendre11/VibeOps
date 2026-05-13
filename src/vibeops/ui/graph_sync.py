from __future__ import annotations

from typing import Any

import streamlit as st

from vibeops.models.conversation import RequirementPhase
from vibeops.models.deployment import DeploymentPhase
from vibeops.models.state import FlowStage, GraphState

_ACTIVE_DEPLOYMENT_PHASES = {
    DeploymentPhase.PLANNING,
    DeploymentPhase.APPLYING,
    DeploymentPhase.SUCCEEDED,
    DeploymentPhase.FAILED,
    DeploymentPhase.AWAITING_DESTROY_CONFIRM,
    DeploymentPhase.DESTROYING,
    DeploymentPhase.DESTROYED,
}


def sync_graph_stage(graph: Any, thread: dict[str, Any]) -> None:
    """Read graph state after an invoke and update session_state accordingly."""
    snapshot: dict[str, object] = graph.get_state(thread).values
    current = GraphState.model_validate(snapshot)

    if current.deployment_phase in _ACTIVE_DEPLOYMENT_PHASES:
        st.session_state["graph_stage"] = "deployment_active"
    elif current.stage == FlowStage.AWAITING_APPROVAL:
        st.session_state["graph_stage"] = "awaiting_approval"
    elif current.requirement_phase == RequirementPhase.ASKING:
        st.session_state["graph_stage"] = "asking"
    elif current.requirement_phase == RequirementPhase.AWAITING_CONFIRMATION:
        st.session_state["graph_stage"] = "awaiting_confirmation"
    elif current.stage == FlowStage.AWAITING_ARCHITECTURE:
        st.session_state["graph_stage"] = "awaiting_architecture"
    elif current.stage == FlowStage.CANCELLED:
        st.session_state["graph_stage"] = "cancelled"
    else:
        st.session_state["graph_stage"] = current.stage.value

    st.session_state["display_history"] = list(current.chat_history)
