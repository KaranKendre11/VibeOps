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
        input_tokens=100,
        output_tokens=50,
    )
    return llm


def test_initial_always_enters_asking_phase() -> None:
    """Conversational flow always starts with ASKING regardless of prompt specificity."""
    llm = _llm("Looks like fine-tuning. Want me to proceed with A100 defaults, or any changes?")
    state = GraphState(user_prompt="fine-tune Llama 3 8B on A100, 16 vCPU, 64 GB, 200 GB disk")
    result = requirement_agent(state, {"configurable": {"llm_client": llm}})
    assert result.requirement_phase == RequirementPhase.ASKING


def test_initial_stores_first_llm_message() -> None:
    msg = "Looks like fine-tuning on an A100. Confirm or adjust?"
    llm = _llm(msg)
    state = GraphState(user_prompt="fine-tune Llama 3 8B")
    result = requirement_agent(state, {"configurable": {"llm_client": llm}})
    assert len(result.conversation) == 1
    assert result.conversation[0].role == TurnRole.AGENT
    assert result.conversation[0].content == msg


def test_initial_makes_extraction_plus_conversational_call() -> None:
    """Chunk 1: initial turn now does structured extraction + conversational reply."""
    llm = _llm("Any preference on region?")
    state = GraphState(user_prompt="concrete T4 VM prompt")
    requirement_agent(state, {"configurable": {"llm_client": llm}})
    assert llm.chat_completion.call_count == 2


def test_initial_does_not_set_partial_requirement() -> None:
    """Extraction happens only at RESUMING_CONFIRMATION, not during initial."""
    llm = _llm("What's your workload?")
    state = GraphState(user_prompt="I need a VM")
    result = requirement_agent(state, {"configurable": {"llm_client": llm}})
    assert result.partial_requirement is None
