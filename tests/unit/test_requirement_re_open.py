from __future__ import annotations

from unittest.mock import MagicMock

from vibeops.agents.requirement import requirement_agent
from vibeops.core.llm import LLMClient
from vibeops.models.conversation import ConversationTurn, RequirementPhase, TurnRole
from vibeops.models.state import GraphState


def test_re_opened_phase_is_noop() -> None:
    """RE_OPENED is obsolete in the conversational flow; graph node returns state unchanged."""
    llm = MagicMock(spec=LLMClient)
    state = GraphState(
        user_prompt="Actually I want a different region",
        requirement_phase=RequirementPhase.RE_OPENED,
        conversation=[
            ConversationTurn(role=TurnRole.AGENT, content="What GPU?"),
            ConversationTurn(role=TurnRole.USER, content="T4"),
        ],
    )
    result = requirement_agent(state, {"configurable": {"llm_client": llm}})
    assert result.requirement_phase == RequirementPhase.RE_OPENED
    llm.chat_completion.assert_not_called()
