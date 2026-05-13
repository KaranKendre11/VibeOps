from __future__ import annotations

import json
from unittest.mock import MagicMock

import openai

from vibeops.agents.requirement import requirement_agent
from vibeops.core.llm import LLMClient
from vibeops.models.conversation import ConversationTurn, RequirementPhase, TurnRole
from vibeops.models.results import ChatResult
from vibeops.models.state import FlowStage, GraphState


def test_llm_timeout_on_initial_falls_back_gracefully() -> None:
    """Timeout on first message uses hardcoded fallback; enters ASKING, no crash."""
    llm = MagicMock(spec=LLMClient)
    llm.chat_completion.side_effect = openai.APITimeoutError(request=MagicMock())
    state = GraphState(user_prompt="vague prompt")

    result = requirement_agent(state, {"configurable": {"llm_client": llm}})

    assert result.requirement_phase == RequirementPhase.ASKING
    assert result.error is None
    assert len(result.conversation) == 1
    assert result.conversation[0].role == TurnRole.AGENT


def test_llm_timeout_on_initial_does_not_retry() -> None:
    """Both LLM calls (extraction + conversational reply) are attempted once each.

    Neither is retried on timeout — the extraction falls back to an empty
    partial; the conversational reply falls back to a hardcoded question.
    """
    llm = MagicMock(spec=LLMClient)
    llm.chat_completion.side_effect = openai.APITimeoutError(request=MagicMock())
    state = GraphState(user_prompt="vague prompt")

    requirement_agent(state, {"configurable": {"llm_client": llm}})

    # Chunk 1 added a second LLM call (intent extraction); neither call retries
    assert llm.chat_completion.call_count == 2


def test_llm_timeout_on_resuming_confirmation_falls_back_to_defaults() -> None:
    """Timeout during extraction falls back to defaults and still produces a draft."""
    llm = MagicMock(spec=LLMClient)
    llm.chat_completion.side_effect = openai.APITimeoutError(request=MagicMock())
    state = GraphState(
        user_prompt="vague",
        requirement_phase=RequirementPhase.RESUMING_CONFIRMATION,
        conversation=[
            ConversationTurn(role=TurnRole.AGENT, content="T4 VM defaults OK?"),
            ConversationTurn(role=TurnRole.USER, content="yes"),
        ],
    )

    result = requirement_agent(state, {"configurable": {"llm_client": llm}})

    assert result.stage == FlowStage.ARCHITECTURE
    assert result.requirement_draft is not None
    assert result.error is None
