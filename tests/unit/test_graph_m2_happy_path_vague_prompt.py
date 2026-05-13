from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

from vibeops.core.gcp_context import GcpContext
from vibeops.core.llm import LLMClient
from vibeops.graph.orchestrator import build_graph
from vibeops.models.conversation import ConversationTurn, RequirementPhase, TurnRole
from vibeops.models.results import ChatResult
from vibeops.models.state import GraphState


def _first_message() -> ChatResult:
    return ChatResult(
        content="What kind of GPU workload are you planning to run?",
        input_tokens=60,
        output_tokens=20,
    )


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
        input_tokens=80,
        output_tokens=40,
    )


def _ctx() -> GcpContext:
    ctx = MagicMock(spec=GcpContext)
    ctx.project_id = "test-project"
    ctx.credentials = MagicMock()
    ctx.get_cached.return_value = None
    ctx.set_cached.return_value = None
    return ctx


def test_vague_prompt_hits_asking_pause() -> None:
    llm = MagicMock(spec=LLMClient)
    llm.chat_completion.return_value = _first_message()
    ctx = _ctx()

    graph = build_graph()
    thread: dict[str, Any] = {"configurable": {"thread_id": "vague-test", "llm_client": llm, "gcp_context": ctx}}
    initial = GraphState(user_prompt="I want to do AI stuff")

    graph.invoke(initial.model_dump(), thread)
    snapshot = dict(graph.get_state(thread).values)
    state = GraphState.model_validate(snapshot)

    assert state.requirement_phase == RequirementPhase.ASKING
    assert len(state.conversation) == 1
    assert state.conversation[0].role == TurnRole.AGENT


def test_vague_prompt_conversation_leads_to_architecture() -> None:
    """Simulate multi-turn conversation ending with RESUMING_CONFIRMATION → architecture."""
    llm = MagicMock(spec=LLMClient)
    llm.chat_completion.side_effect = [_first_message(), _extraction_result()]
    ctx = _ctx()

    graph = build_graph()
    thread: dict[str, Any] = {"configurable": {"thread_id": "vague-confirm", "llm_client": llm, "gcp_context": ctx}}
    initial = GraphState(user_prompt="I want to do AI stuff")

    # First invoke → ASKING pause
    graph.invoke(initial.model_dump(), thread)
    snapshot = dict(graph.get_state(thread).values)
    state = GraphState.model_validate(snapshot)
    assert state.requirement_phase == RequirementPhase.ASKING

    # Simulate user replying and confirming → update to RESUMING_CONFIRMATION
    existing = [t.model_dump() for t in state.conversation]
    existing.append(ConversationTurn(role=TurnRole.USER, content="inference on T4").model_dump())
    graph.update_state(
        thread,
        {
            "conversation": existing,
            "requirement_phase": RequirementPhase.RESUMING_CONFIRMATION.value,
        },
    )
    graph.invoke(None, thread)

    snapshot = dict(graph.get_state(thread).values)
    state = GraphState.model_validate(snapshot)

    # After extraction+finalization → stage advances past REQUIREMENT
    assert state.stage != GraphState.model_fields["stage"].default  # not initial REQUIREMENT
