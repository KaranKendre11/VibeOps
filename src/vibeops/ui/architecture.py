from __future__ import annotations

import logging
from typing import Any

import streamlit as st

from vibeops.models.architecture import ArchitectureCandidate
from vibeops.models.conversation import RequirementPhase
from vibeops.models.state import FlowStage, GraphState
from vibeops.ui.graph_sync import sync_graph_stage

logger = logging.getLogger(__name__)

_ARCH_CSS = """
<style>
.arch-label {
  font-size: 14px;
  font-weight: 600;
  color: #ffffff;
  margin-bottom: 2px;
  letter-spacing: -0.01em;
}
.arch-meta {
  font-size: 12px;
  color: #888;
  font-family: 'JetBrains Mono', monospace;
  letter-spacing: 0.02em;
}
.quota-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}
.quota-green  { background: #00DEFF; box-shadow: 0 0 8px rgba(0,222,255,0.6); }
.quota-orange { background: #fbbf24; box-shadow: 0 0 8px rgba(251,191,36,0.5); }
.quota-red    { background: #f87171; box-shadow: 0 0 8px rgba(248,113,113,0.5); }
</style>
"""


def render_architecture_card(state: GraphState, graph: Any, thread: dict[str, Any]) -> None:
    options = state.architecture_options
    if options is None:
        st.error("No architecture options available.")
        if st.button("Restart", key="architecture.restart_no_opts"):
            for k in ("graph", "graph_stage", "display_history", "graph_thread_id"):
                st.session_state.pop(k, None)
            st.rerun()
        return

    st.markdown(_ARCH_CSS, unsafe_allow_html=True)

    # Header + warning + cards INSIDE chat_message
    with st.chat_message("assistant", avatar="🤖"):
        if state.excluded_zones:
            excluded_str = ", ".join(f"`{z}`" for z in state.excluded_zones)
            st.warning(
                f"Zone(s) {excluded_str} excluded — insufficient capacity. "
                "Showing remaining available options."
            )

        st.markdown("**Pick a deployment target**")

        candidates = options.candidates

        def _label(c: ArchitectureCandidate) -> str:
            q_pct = c.quota_remaining / c.quota_total if c.quota_total > 0 else 0
            dot = "green" if q_pct >= 0.5 else ("orange" if q_pct > 0 else "red")
            return (
                f"{c.zone}  ·  {c.machine_type}  ·  "
                f"{c.cpus} vCPU / {c.memory_gb:.0f} GB  ·  "
                f"[{dot}] quota {c.quota_remaining}/{c.quota_total}"
            )

        selected_idx = st.radio(
            "Zone",
            options=list(range(len(candidates))),
            format_func=lambda i: _label(candidates[i]),
            key="architecture.candidate",
            label_visibility="collapsed",
        )

        if selected_idx is not None and 0 <= selected_idx < len(candidates):
            c: ArchitectureCandidate = candidates[selected_idx]
            st.caption(c.rationale)

        network_names = [n.name for n in options.networks] or ["default"]
        if len(network_names) > 1:
            st.selectbox("Network", options=network_names, key="architecture.network")
        else:
            st.session_state["architecture.network"] = network_names[0]

    # Buttons OUTSIDE the chat_message — flex layout inside chat_message
    # was eating the click area in some viewport widths.
    col_confirm, _, col_back = st.columns([2, 4, 1])
    with col_confirm:
        if st.button("Confirm →", type="primary", key="architecture.confirm", use_container_width=True):
            _on_confirm(graph, thread)
    with col_back:
        if st.button("← Back", key="architecture.back", use_container_width=True):
            _on_back(graph, thread)


def _on_confirm(graph: Any, thread: dict[str, Any]) -> None:
    ss = st.session_state
    idx = ss.get("architecture.candidate", 0)
    network = ss.get("architecture.network", "default")

    # The `as_node="architecture_pause"` argument is critical here. Without
    # it, update_state leaves the checkpoint exactly where it was — which
    # after a `_on_try_different_zone` recovery is the interrupt point
    # BEFORE architecture_pause. Calling invoke(None) from that position
    # re-runs the architecture agent in discovery mode (architecture_response
    # is read AFTER the interrupt resumes) and we loop back to the same
    # screen. Anchoring as the architecture_pause exit guarantees the next
    # invoke advances to architecture → iac → review.
    try:
        graph.update_state(
            thread,
            {"architecture_response": {"candidate_index": idx, "network_name": network}},
            as_node="architecture_pause",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("architecture confirm: update_state failed")
        st.error(f"Could not record selection: {exc}")
        return

    try:
        with st.status("Generating Terraform configuration…", expanded=True) as status:
            st.write("Resolving OS image")
            st.write("Rendering templates")
            st.write("Initializing Terraform providers (may take a minute on first run)")
            graph.invoke(None, thread)
            status.update(label="Configuration ready", state="complete", expanded=False)
    except Exception as exc:  # noqa: BLE001
        logger.exception("architecture confirm: graph.invoke failed")
        st.error(f"Could not generate configuration: {exc}")
        return

    try:
        sync_graph_stage(graph, thread)
    except Exception as exc:  # noqa: BLE001
        logger.exception("architecture confirm: sync_graph_stage failed")
        st.error(f"Could not read updated state: {exc}")
        return
    st.rerun()


def _on_back(graph: Any, thread: dict[str, Any]) -> None:
    """Return to the conversational asking phase in REVISION mode.

    We append an explicit assistant turn that says we're going back to revise.
    This gives the LLM the context it needs on the next user message to treat
    that input as a CHANGE request rather than a confirmation — the
    conversational system prompt already handles "user requests change → apply
    + show updated summary + ask again".
    """
    from vibeops.models.conversation import ConversationTurn, TurnRole

    # Read current conversation off the graph and append a revision-mode turn.
    try:
        snapshot: dict[str, Any] = graph.get_state(thread).values
        current_state = GraphState.model_validate(snapshot)
        conv = list(current_state.conversation)
    except Exception as exc:  # noqa: BLE001
        logger.exception("architecture back: could not read state")
        st.error(f"Could not go back: {exc}")
        return

    revision_msg = (
        "Going back — what would you like to change about the configuration? "
        "(GPU type, region, OS, ports, container, anything.)"
    )
    conv.append(ConversationTurn(role=TurnRole.AGENT, content=revision_msg))

    try:
        graph.update_state(
            thread,
            {
                "conversation": [t.model_dump() for t in conv],
                "back_to_requirements": False,
                "architecture_response": None,
                "architecture_options": None,
                "stage": FlowStage.REQUIREMENT.value,
                "requirement_phase": RequirementPhase.ASKING.value,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("architecture back: update_state failed")
        st.error(f"Could not go back: {exc}")
        return

    # Force the UI back to the chat view. We don't invoke the graph here —
    # the chat reads from state.conversation and the user can continue.
    st.session_state["graph_stage"] = "asking"
    st.session_state.pop("architecture.candidate", None)
    st.session_state.pop("architecture.network", None)
    st.rerun()
