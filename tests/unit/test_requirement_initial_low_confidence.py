from __future__ import annotations

from unittest.mock import MagicMock

from vibeops.agents.requirement import requirement_agent
from vibeops.core.llm import LLMClient
from vibeops.models.conversation import RequirementPhase, TurnRole
from vibeops.models.results import ChatResult
from vibeops.models.state import GraphState


def _llm(message: str) -> LLMClient:
    llm = MagicMock(spec=LLMClient)
    llm.chat_completion.return_value = ChatResult(
        content=message,
        input_tokens=80,
        output_tokens=30,
    )
    return llm


def test_initial_enters_asking_phase() -> None:
    llm = _llm("What kind of workload do you need the GPU for?")
    state = GraphState(user_prompt="I want to do AI stuff")
    result = requirement_agent(state, {"configurable": {"llm_client": llm}})
    assert result.requirement_phase == RequirementPhase.ASKING


def test_initial_generates_exactly_one_agent_turn() -> None:
    llm = _llm("What kind of workload?")
    state = GraphState(user_prompt="I want to do AI stuff")
    result = requirement_agent(state, {"configurable": {"llm_client": llm}})
    agent_turns = [t for t in result.conversation if t.role == TurnRole.AGENT]
    assert len(agent_turns) == 1


def test_initial_conversation_content_matches_llm_output() -> None:
    question = "What kind of workload?"
    llm = _llm(question)
    state = GraphState(user_prompt="I want to do AI stuff")
    result = requirement_agent(state, {"configurable": {"llm_client": llm}})
    assert result.conversation[0].content == question
