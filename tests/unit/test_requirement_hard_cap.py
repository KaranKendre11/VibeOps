from __future__ import annotations

from unittest.mock import MagicMock

from vibeops.agents.requirement import requirement_agent
from vibeops.core.llm import LLMClient
from vibeops.models.conversation import ConversationTurn, RequirementPhase, TurnRole
from vibeops.models.state import GraphState


def _asking_state() -> GraphState:
    return GraphState(
        user_prompt="I need a VM",
        requirement_phase=RequirementPhase.RESUMING_ASKING,
        conversation=[
            ConversationTurn(role=TurnRole.AGENT, content="What GPU do you need?"),
            ConversationTurn(role=TurnRole.USER, content="T4"),
        ],
    )


def test_resuming_asking_is_noop_phase() -> None:
    """RESUMING_ASKING is handled in chat.py via streaming; graph node is a no-op."""
    llm = MagicMock(spec=LLMClient)
    result = requirement_agent(_asking_state(), {"configurable": {"llm_client": llm}})
    assert result.requirement_phase == RequirementPhase.RESUMING_ASKING
    llm.chat_completion.assert_not_called()


def test_awaiting_confirmation_is_noop_phase() -> None:
    """AWAITING_CONFIRMATION is handled in chat.py; graph node is a no-op."""
    llm = MagicMock(spec=LLMClient)
    state = GraphState(
        user_prompt="I need a VM",
        requirement_phase=RequirementPhase.AWAITING_CONFIRMATION,
    )
    result = requirement_agent(state, {"configurable": {"llm_client": llm}})
    assert result.requirement_phase == RequirementPhase.AWAITING_CONFIRMATION
    llm.chat_completion.assert_not_called()


def test_asking_phase_is_noop() -> None:
    llm = MagicMock(spec=LLMClient)
    state = GraphState(
        user_prompt="I need a VM",
        requirement_phase=RequirementPhase.ASKING,
    )
    result = requirement_agent(state, {"configurable": {"llm_client": llm}})
    assert result.requirement_phase == RequirementPhase.ASKING
    llm.chat_completion.assert_not_called()
