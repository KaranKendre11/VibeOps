from __future__ import annotations

from unittest.mock import MagicMock

from vibeops.agents.requirement import requirement_agent
from vibeops.core.llm import LLMClient
from vibeops.models.state import GraphState


def _state(prompt: str) -> GraphState:
    return GraphState(user_prompt=prompt)


def _config(llm: LLMClient) -> dict[str, object]:
    return {"configurable": {"llm_client": llm}}


def test_out_of_scope_database_declines_with_zero_llm_calls() -> None:
    llm = MagicMock(spec=LLMClient)
    result = requirement_agent(_state("set up a postgres database"), _config(llm))
    llm.chat_completion.assert_not_called()
    assert result.error is not None
    # Decline message updated in Chunk 3 — friendlier phrasing
    assert "VibeOps currently supports single GPU VMs only" in result.error


def test_out_of_scope_k8s_declines() -> None:
    llm = MagicMock(spec=LLMClient)
    result = requirement_agent(_state("deploy a kubernetes cluster"), _config(llm))
    llm.chat_completion.assert_not_called()
    assert result.error is not None


def test_out_of_scope_bucket_declines() -> None:
    llm = MagicMock(spec=LLMClient)
    result = requirement_agent(_state("create a gcs bucket for my data"), _config(llm))
    llm.chat_completion.assert_not_called()
    assert result.error is not None


def test_in_scope_gpu_vm_proceeds_to_llm() -> None:
    llm = MagicMock(spec=LLMClient)
    # Return a high-confidence response to go straight to AWAITING_CONFIRMATION
    import json

    from vibeops.models.results import ChatResult
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
            "next_question": None,
            "scope_ok": True,
        }),
        input_tokens=100,
        output_tokens=50,
    )
    result = requirement_agent(_state("T4 GPU VM"), _config(llm))
    # Chunk 1: initial turn now makes 2 calls — intent extraction + conversational reply
    assert llm.chat_completion.call_count == 2
    assert result.error is None
