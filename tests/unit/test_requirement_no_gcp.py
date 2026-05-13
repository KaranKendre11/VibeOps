from __future__ import annotations

import json
from unittest.mock import MagicMock

from vibeops.agents.requirement import requirement_agent
from vibeops.core.llm import LLMClient
from vibeops.models.conversation import ConversationTurn, RequirementPhase, TurnRole
from vibeops.models.requirement import PartialRequirement, WorkloadIntent
from vibeops.models.results import ChatResult
from vibeops.models.state import GraphState


class _RaisingGcpContext:
    """A fake GcpContext that explodes on any attribute access."""

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"Requirement Agent accessed GcpContext.{name}")


def _llm_with_response(question: str | None = None) -> LLMClient:
    llm = MagicMock(spec=LLMClient)
    llm.chat_completion.return_value = ChatResult(
        content=json.dumps({
            "workload_intent": "inference_small",
            "workload_intent_confidence": "high",
            "gpu_type": "nvidia-tesla-t4",
            "gpu_type_confidence": "high",
            "gpu_count": 1,
            "gpu_count_confidence": "high",
            "cpu_floor": "8",
            "cpu_floor_confidence": "high",
            "memory_floor": "32",
            "memory_floor_confidence": "high",
            "os_family": "deeplearning-platform-release",
            "os_family_confidence": "high",
            "disk_size_gb": 100,
            "disk_size_gb_confidence": "high",
            "preemptible": False,
            "preemptible_confidence": "high",
            "region_preference": "none",
            "region_preference_confidence": "high",
            "next_question": question,
            "scope_ok": True,
        }),
        input_tokens=80,
        output_tokens=40,
    )
    return llm


def test_initial_phase_never_touches_gcp() -> None:
    gcp = _RaisingGcpContext()
    llm = _llm_with_response()
    config = {"configurable": {"llm_client": llm, "gcp_context": gcp}}
    state = GraphState(user_prompt="T4 VM for inference")
    # Must not raise
    requirement_agent(state, config)


def test_resuming_asking_never_touches_gcp() -> None:
    gcp = _RaisingGcpContext()
    llm = _llm_with_response()
    config = {"configurable": {"llm_client": llm, "gcp_context": gcp}}
    state = GraphState(
        user_prompt="vague prompt",
        requirement_phase=RequirementPhase.RESUMING_ASKING,
        requirement_turns=1,
        conversation=[
            ConversationTurn(role=TurnRole.AGENT, content="What kind of workload?"),
            ConversationTurn(role=TurnRole.USER, content="inference"),
        ],
        partial_requirement=PartialRequirement(workload_intent=WorkloadIntent.INFERENCE_SMALL),
    )
    requirement_agent(state, config)


def test_resuming_confirmation_never_touches_gcp() -> None:
    gcp = _RaisingGcpContext()
    config = {"configurable": {"llm_client": MagicMock(spec=LLMClient), "gcp_context": gcp}}
    state = GraphState(
        user_prompt="T4 VM",
        requirement_phase=RequirementPhase.RESUMING_CONFIRMATION,
        confirmation_response={
            "workload_intent": "inference_small",
            "gpu_type": "nvidia-tesla-t4",
            "gpu_count": 1,
            "cpu_floor": "8",
            "memory_floor": "32",
            "os_family": "deeplearning-platform-release",
            "disk_size_gb": 100,
            "preemptible": False,
            "region_preference": "none",
        },
    )
    requirement_agent(state, config)
