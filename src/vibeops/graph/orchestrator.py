from __future__ import annotations

from typing import Any, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from vibeops.agents.architecture import architecture_agent
from vibeops.agents.deployment import deployment_agent, destroy_agent
from vibeops.agents.iac import iac_agent
from vibeops.agents.requirement import requirement_agent
from vibeops.models.conversation import RequirementPhase
from vibeops.models.state import FlowStage, GraphState


def approval_router(state: GraphState) -> Literal["deployment", "cancelled"]:
    """Fails closed — deploy only when approved AND within the cost cap.

    Defence in depth behind the deploy route's 409: even if ``approved`` is forced True by a
    direct API call, an over-cap plan (``cost_cap_exceeded``) is cancelled unless the user has
    explicitly set ``cost_cap_override`` to literal True.
    """
    if state.approved is not True:
        return "cancelled"
    if state.cost_cap_exceeded and state.cost_cap_override is not True:
        return "cancelled"
    return "deployment"


def destroy_router(state: GraphState) -> Literal["destroy", "blocked"]:
    """Fails closed — only literal True unlocks destroy."""
    if state.destroy_confirmed is True:
        return "destroy"
    return "blocked"


def _requirement_router(
    state: GraphState,
) -> Literal["asking_pause", "confirmation_pause", "architecture", "requirement"]:
    phase = state.requirement_phase
    if phase == RequirementPhase.ASKING:
        return "asking_pause"
    if phase == RequirementPhase.AWAITING_CONFIRMATION:
        return "confirmation_pause"
    if state.stage == FlowStage.ARCHITECTURE:
        return "architecture"
    if state.stage in (FlowStage.DONE, FlowStage.CANCELLED):
        return "requirement"
    return "requirement"


def _architecture_router(
    state: GraphState,
) -> Literal["architecture_pause", "confirmation_pause", "iac"]:
    if state.stage == FlowStage.AWAITING_ARCHITECTURE:
        return "architecture_pause"
    if state.stage == FlowStage.REQUIREMENT:
        return "confirmation_pause"
    return "iac"


def _deployment_decision_router(
    state: GraphState,
) -> Literal["deployment", "destroy_confirm", "end"]:
    if state.retry_requested:
        return "deployment"
    if state.destroy_requested:
        return "destroy_confirm"
    return "end"


def _review_node(state: GraphState) -> GraphState:
    return state


def _asking_pause(state: GraphState) -> GraphState:
    return state


def _confirmation_pause(state: GraphState) -> GraphState:
    return state


def _architecture_pause(state: GraphState) -> GraphState:
    return state


def _deployment_decision_node(state: GraphState) -> GraphState:
    return state


def _destroy_confirm_node(state: GraphState) -> GraphState:
    return state


def _destroy_blocked_node(state: GraphState) -> GraphState:
    return state.model_copy(
        update={"deployment_error": "Destroy attempted without confirmation — blocked."}
    )


def _cancelled_node(state: GraphState) -> GraphState:
    return state.model_copy(
        update={
            "stage": FlowStage.CANCELLED,
            "chat_history": state.chat_history
            + [
                {
                    "role": "system",
                    "agent": "orchestrator",
                    "content": "Deployment cancelled by user.",
                }
            ],
        }
    )


def build_graph() -> Any:
    """Compile the VibeOps LangGraph state machine.

    M4 topology:
        requirement → [router] → asking_pause | confirmation_pause | architecture | (loop)
        asking_pause → requirement
        confirmation_pause → requirement
        architecture → [router] → architecture_pause | confirmation_pause | iac
        architecture_pause → architecture
        iac → [INTERRUPT] → review → approval_router → deployment | cancelled
        deployment → [INTERRUPT] → deployment_decision → [router]:
            retry       → deployment
            destroy     → destroy_confirm → [INTERRUPT] → destroy_router:
                              confirmed → destroy_agent → deployment_decision
                              blocked   → destroy_blocked → END
            done/leave  → END
    """
    builder: StateGraph[GraphState, GraphState, GraphState] = StateGraph(GraphState)

    builder.add_node("requirement", requirement_agent)
    builder.add_node("asking_pause", _asking_pause)
    builder.add_node("confirmation_pause", _confirmation_pause)
    builder.add_node("architecture", architecture_agent)
    builder.add_node("architecture_pause", _architecture_pause)
    builder.add_node("iac", iac_agent)
    builder.add_node("review", _review_node)
    builder.add_node("deployment", deployment_agent)
    builder.add_node("deployment_decision", _deployment_decision_node)
    builder.add_node("destroy_confirm", _destroy_confirm_node)
    builder.add_node("destroy", destroy_agent)
    builder.add_node("destroy_blocked", _destroy_blocked_node)
    builder.add_node("cancelled", _cancelled_node)

    builder.set_entry_point("requirement")

    builder.add_conditional_edges(
        "requirement",
        _requirement_router,
        {
            "asking_pause": "asking_pause",
            "confirmation_pause": "confirmation_pause",
            "architecture": "architecture",
            "requirement": "requirement",
        },
    )

    builder.add_edge("asking_pause", "requirement")
    builder.add_edge("confirmation_pause", "requirement")

    builder.add_conditional_edges(
        "architecture",
        _architecture_router,
        {
            "architecture_pause": "architecture_pause",
            "confirmation_pause": "confirmation_pause",
            "iac": "iac",
        },
    )

    builder.add_edge("architecture_pause", "architecture")
    builder.add_edge("iac", "review")

    builder.add_conditional_edges(
        "review",
        approval_router,
        {"deployment": "deployment", "cancelled": "cancelled"},
    )

    builder.add_edge("deployment", "deployment_decision")

    builder.add_conditional_edges(
        "deployment_decision",
        _deployment_decision_router,
        {
            "deployment": "deployment",
            "destroy_confirm": "destroy_confirm",
            "end": END,
        },
    )

    # Destroy gate: destroy_confirm → destroy_router → destroy | destroy_blocked
    builder.add_conditional_edges(
        "destroy_confirm",
        destroy_router,
        {"destroy": "destroy", "blocked": "destroy_blocked"},
    )

    builder.add_edge("destroy", "deployment_decision")
    builder.add_edge("destroy_blocked", END)
    builder.add_edge("cancelled", END)

    checkpointer = MemorySaver()
    return builder.compile(
        checkpointer=checkpointer,
        interrupt_before=[
            "asking_pause",
            "confirmation_pause",
            "architecture_pause",
            "review",
            "deployment_decision",
        ],
    )
