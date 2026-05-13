from __future__ import annotations

import json
from unittest.mock import MagicMock

from vibeops.agents.requirement import requirement_agent
from vibeops.core.llm import LLMClient
from vibeops.models.conversation import ConversationTurn, RequirementPhase, TurnRole
from vibeops.models.requirement import RequirementDraft
from vibeops.models.results import ChatResult
from vibeops.models.state import FlowStage, GraphState


def _conversation_with_agreement() -> list[ConversationTurn]:
    return [
        ConversationTurn(role=TurnRole.AGENT, content="T4, 8 vCPU, 32 GB. Confirmed?"),
        ConversationTurn(role=TurnRole.USER, content="yes, go ahead"),
    ]


def _extraction_result() -> ChatResult:
    return ChatResult(
        content=json.dumps({
            "workload_intent": "inference_small",
            "gpu_type": "nvidia-tesla-t4",
            "gpu_count": 1,
            "cpu_floor": "8",
            "memory_floor": "32",
            "os_family": "deeplearning-platform-release",
            "disk_size_gb": 100,
            "preemptible": False,
            "region_preference": "none",
        }),
        input_tokens=100,
        output_tokens=80,
    )


def test_resuming_confirmation_produces_requirement_draft() -> None:
    llm = MagicMock(spec=LLMClient)
    llm.chat_completion.return_value = _extraction_result()
    state = GraphState(
        user_prompt="T4 VM",
        requirement_phase=RequirementPhase.RESUMING_CONFIRMATION,
        conversation=_conversation_with_agreement(),
    )
    result = requirement_agent(state, {"configurable": {"llm_client": llm}})
    assert result.requirement_draft is not None
    assert isinstance(result.requirement_draft, RequirementDraft)
    assert result.stage == FlowStage.ARCHITECTURE


def test_resuming_confirmation_clears_confirmation_response() -> None:
    llm = MagicMock(spec=LLMClient)
    llm.chat_completion.return_value = _extraction_result()
    state = GraphState(
        user_prompt="T4 VM",
        requirement_phase=RequirementPhase.RESUMING_CONFIRMATION,
        conversation=_conversation_with_agreement(),
    )
    result = requirement_agent(state, {"configurable": {"llm_client": llm}})
    assert result.confirmation_response is None


def test_resuming_confirmation_updates_chat_history() -> None:
    llm = MagicMock(spec=LLMClient)
    llm.chat_completion.return_value = _extraction_result()
    state = GraphState(
        user_prompt="T4 VM",
        requirement_phase=RequirementPhase.RESUMING_CONFIRMATION,
        conversation=_conversation_with_agreement(),
    )
    result = requirement_agent(state, {"configurable": {"llm_client": llm}})
    agents = [e["agent"] for e in result.chat_history if "agent" in e]
    assert "requirement" in agents


def test_resuming_confirmation_without_llm_uses_defaults() -> None:
    """No-LLM path (stub) produces a valid draft with default values."""
    state = GraphState(
        user_prompt="T4 VM",
        requirement_phase=RequirementPhase.RESUMING_CONFIRMATION,
        conversation=_conversation_with_agreement(),
    )
    result = requirement_agent(state)
    assert result.requirement_draft is not None
    assert result.stage == FlowStage.ARCHITECTURE


def test_extraction_fallback_on_bad_llm_response_uses_defaults() -> None:
    """If extraction LLM returns garbage, falls back to defaults without crashing."""
    llm = MagicMock(spec=LLMClient)
    llm.chat_completion.return_value = ChatResult(
        content="not json at all", input_tokens=10, output_tokens=5
    )
    state = GraphState(
        user_prompt="T4 VM",
        requirement_phase=RequirementPhase.RESUMING_CONFIRMATION,
        conversation=_conversation_with_agreement(),
    )
    result = requirement_agent(state, {"configurable": {"llm_client": llm}})
    assert result.requirement_draft is not None
    assert result.stage == FlowStage.ARCHITECTURE
