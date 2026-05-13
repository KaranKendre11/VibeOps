from __future__ import annotations

from unittest.mock import MagicMock

from vibeops.agents.requirement import build_conversation_messages, requirement_agent
from vibeops.core.llm import LLMClient
from vibeops.models.conversation import ConversationTurn, RequirementPhase, TurnRole
from vibeops.models.results import ChatResult
from vibeops.models.state import GraphState


def _llm_with_message(message: str) -> LLMClient:
    llm = MagicMock(spec=LLMClient)
    llm.chat_completion.return_value = ChatResult(
        content=message,
        input_tokens=50,
        output_tokens=30,
    )
    return llm


def test_initial_enters_asking_phase() -> None:
    llm = _llm_with_message("What kind of GPU workload are you running?")
    state = GraphState(user_prompt="I need a VM")
    result = requirement_agent(state, {"configurable": {"llm_client": llm}})
    assert result.requirement_phase == RequirementPhase.ASKING


def test_initial_stores_llm_response_in_conversation() -> None:
    llm = _llm_with_message("What kind of GPU workload are you running?")
    state = GraphState(user_prompt="I need a VM")
    result = requirement_agent(state, {"configurable": {"llm_client": llm}})
    assert len(result.conversation) == 1
    assert result.conversation[0].role == TurnRole.AGENT
    assert result.conversation[0].content == "What kind of GPU workload are you running?"


def test_initial_makes_two_llm_calls() -> None:
    """Chunk 1 added structured intent extraction before the conversational reply.

    Initial turn now makes 2 LLM calls: one for intent JSON extraction,
    one for the first conversational follow-up question. Both are bounded —
    we never spin a loop on the initial.
    """
    llm = _llm_with_message("Tell me about your workload.")
    state = GraphState(user_prompt="I want to do AI stuff")
    requirement_agent(state, {"configurable": {"llm_client": llm}})
    assert llm.chat_completion.call_count == 2


def test_build_conversation_messages_includes_system_prompt() -> None:
    from vibeops.agents.requirement_prompts import CONVERSATIONAL_SYSTEM_PROMPT

    conv = [ConversationTurn(role=TurnRole.AGENT, content="What workload?")]
    messages = build_conversation_messages(conv, "inference")
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == CONVERSATIONAL_SYSTEM_PROMPT


def test_build_conversation_messages_maps_agent_to_assistant() -> None:
    conv = [
        ConversationTurn(role=TurnRole.AGENT, content="What GPU?"),
        ConversationTurn(role=TurnRole.USER, content="T4"),
    ]
    messages = build_conversation_messages(conv, "1 GPU please")
    roles = [m["role"] for m in messages]
    assert roles == ["system", "assistant", "user", "user"]


def test_build_conversation_messages_appends_user_reply() -> None:
    conv: list[ConversationTurn] = []
    messages = build_conversation_messages(conv, "fine-tune Llama 3")
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "fine-tune Llama 3"


def test_build_conversation_messages_truncates_long_reply() -> None:
    long_reply = "x" * 2000
    conv: list[ConversationTurn] = []
    messages = build_conversation_messages(conv, long_reply)
    assert len(messages[-1]["content"]) == 1000
