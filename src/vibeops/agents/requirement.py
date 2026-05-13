from __future__ import annotations

import json
import logging
from typing import Any, Optional

from langchain_core.runnables import RunnableConfig

from vibeops.agents.requirement_defaults import get_defaults
from vibeops.agents.requirement_prompts import (
    CONVERSATIONAL_SYSTEM_PROMPT,
    INTENT_EXTRACTION_PROMPT,
    REQUIREMENT_EXTRACTION_PROMPT,
    SCOPE_DECLINE_MESSAGE,
    is_out_of_scope,
)
from vibeops.core.llm import LLMClient
from vibeops.models.conversation import ConversationTurn, RequirementPhase, TurnRole
from vibeops.models.requirement import (
    CpuClass,
    MemoryClass,
    OsFamily,
    PartialRequirement,
    PartialRequirementExtended,
    RegionPreference,
    RequirementDraft,
    WorkloadIntent,
)
from vibeops.models.spec import GpuType
from vibeops.models.state import FlowStage, GraphState

logger = logging.getLogger(__name__)

_MAX_USER_INPUT_CHARS = 1000

_GPU_DISPLAY = {
    "nvidia-tesla-t4": "T4",
    "nvidia-l4": "L4",
    "nvidia-tesla-a100": "A100 40GB",
}


def requirement_agent(state: GraphState, config: Optional[RunnableConfig] = None) -> GraphState:
    """LLM-driven conversational requirement gatherer.

    Conversational turns are streamed in chat.py; this node only runs on
    INITIAL (first message) and RESUMING_CONFIRMATION (extract + finalize).
    Falls back to stub when no LLMClient is available.
    """
    llm: LLMClient | None = None
    if config:
        configurable: dict[str, Any] = config.get("configurable") or {}
        llm = configurable.get("llm_client")

    phase = state.requirement_phase

    if llm is None:
        if phase == RequirementPhase.RESUMING_CONFIRMATION:
            return _finalize_draft(state)
        return _stub_fallback(state)

    if phase == RequirementPhase.INITIAL:
        return _handle_initial(state, llm)
    if phase == RequirementPhase.RESUMING_CONFIRMATION:
        return _handle_resuming_confirmation(state, llm)
    # ASKING / AWAITING_CONFIRMATION are handled by chat.py streaming
    return state


# ---------------------------------------------------------------------------
# Intent extraction (Chunk 1) — runs on the first prompt
# ---------------------------------------------------------------------------


def extract_intent(prompt: str, llm: LLMClient) -> tuple[PartialRequirementExtended, bool, str]:
    """Run structured-output extraction on the user's first message.

    Returns (partial, out_of_scope, reason). On any error, returns an empty
    partial with out_of_scope=False so the conversation can proceed normally.
    """
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": INTENT_EXTRACTION_PROMPT},
        {"role": "user", "content": prompt[:_MAX_USER_INPUT_CHARS]},
    ]
    try:
        result = llm.chat_completion(
            messages,
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        data: dict[str, Any] = json.loads(result.content)
    except Exception as exc:  # noqa: BLE001
        logger.warning("intent extraction failed: %s", exc)
        return PartialRequirementExtended(), False, ""

    if data.get("out_of_scope"):
        return PartialRequirementExtended(), True, str(data.get("reason", ""))

    partial = _parse_extended(data)
    return partial, False, ""


def _summarize_known_fields(p: PartialRequirementExtended) -> str:
    """Build a short ' Already known: ...' bullet list for the LLM system prompt."""
    bits: list[str] = []
    if p.workload_intent:
        bits.append(f"- workload purpose: {p.workload_intent.value}")
    if p.gpu_type:
        gpu = _GPU_DISPLAY.get(p.gpu_type.value, p.gpu_type.name)
        cnt = p.gpu_count or 1
        bits.append(f"- GPU: {cnt}× {gpu}")
    if p.cpu_floor:
        bits.append(f"- min vCPU: {p.cpu_floor.value}")
    if p.memory_floor:
        bits.append(f"- min RAM: {p.memory_floor.value} GB")
    if p.os_family:
        bits.append(f"- OS family: {p.os_family.value}")
    if p.disk_size_gb:
        bits.append(f"- disk size: {p.disk_size_gb} GB")
    if p.preemptible is not None:
        bits.append(f"- preemptible: {p.preemptible}")
    if p.region_preference and p.region_preference != RegionPreference.NONE:
        bits.append(f"- region: {p.region_preference.value}")
    if p.purpose:
        bits.append(f"- purpose: {p.purpose}")
    if p.open_ports:
        bits.append(f"- open ports: {', '.join(str(x) for x in p.open_ports)}")
    if p.public_ip is not None:
        bits.append(f"- public IP: {p.public_ip}")
    if p.container_image:
        bits.append(f"- run container: {p.container_image}")
    if p.software_packages:
        bits.append(f"- preinstall: {', '.join(p.software_packages)}")
    if p.startup_script:
        bits.append("- startup script: provided")

    if not bits:
        return ""
    return "\n\n# Already extracted from the user's first message\n" + "\n".join(bits)


def build_conversation_messages(
    conversation: list[ConversationTurn], user_reply: str
) -> list[dict[str, Any]]:
    """Build OpenAI messages list for streaming the next conversational turn."""
    # Pull the cached extracted intent (set by _handle_initial) so the LLM
    # never asks about fields the user already specified.
    system_extra = ""
    # The extraction is carried on the first agent turn's metadata-style content; here we
    # just use the empty version — the chat.py-side streamer doesn't have access to state,
    # so we keep this simple and let the system prompt's rules handle it.
    system = CONVERSATIONAL_SYSTEM_PROMPT + system_extra

    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for turn in conversation:
        role = "user" if turn.role == TurnRole.USER else "assistant"
        messages.append({"role": role, "content": turn.content})
    messages.append({"role": "user", "content": user_reply[:_MAX_USER_INPUT_CHARS]})
    return messages


def build_conversation_messages_with_context(
    conversation: list[ConversationTurn],
    user_reply: str,
    extracted: PartialRequirementExtended | None,
) -> list[dict[str, Any]]:
    """Same as build_conversation_messages, but injects the extracted-intent context.

    Use this in chat.py when state.extracted_intent is available so the LLM
    has the full picture and skips re-asking known fields.
    """
    system_extra = _summarize_known_fields(extracted) if extracted else ""
    system = CONVERSATIONAL_SYSTEM_PROMPT + system_extra

    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for turn in conversation:
        role = "user" if turn.role == TurnRole.USER else "assistant"
        messages.append({"role": role, "content": turn.content})
    messages.append({"role": "user", "content": user_reply[:_MAX_USER_INPUT_CHARS]})
    return messages


def _stub_fallback(state: GraphState) -> GraphState:
    draft = RequirementDraft(
        intent="gpu_vm",
        workload_intent=WorkloadIntent.INFERENCE_SMALL,
        gpu_type=GpuType.T4,
        gpu_count=1,
        cpu_floor=CpuClass.C8,
        memory_floor=MemoryClass.M32,
        os_family=OsFamily.DEEP_LEARNING,
        disk_size_gb=100,
        preemptible=False,
        region_preference=RegionPreference.NONE,
    )
    return state.model_copy(
        update={
            "requirement_draft": draft,
            "stage": FlowStage.ARCHITECTURE,
            "requirement_phase": RequirementPhase.RESUMING_CONFIRMATION,
            "chat_history": state.chat_history
            + [
                {
                    "role": "agent",
                    "agent": "requirement",
                    "content": "Drafted a T4 VM requirement (stub).",
                }
            ],
        }
    )


def _handle_initial(state: GraphState, llm: LLMClient) -> GraphState:
    if is_out_of_scope(state.user_prompt):
        return state.model_copy(
            update={
                "stage": FlowStage.DONE,
                "error": SCOPE_DECLINE_MESSAGE,
                "chat_history": state.chat_history
                + [
                    {
                        "role": "agent",
                        "agent": "requirement",
                        "content": SCOPE_DECLINE_MESSAGE,
                    }
                ],
            }
        )

    # Step 1: structured extraction (Chunk 1)
    extracted, out_of_scope, reason = extract_intent(state.user_prompt, llm)
    if out_of_scope:
        msg = f"{SCOPE_DECLINE_MESSAGE} ({reason})" if reason else SCOPE_DECLINE_MESSAGE
        return state.model_copy(
            update={
                "stage": FlowStage.DONE,
                "error": msg,
                "chat_history": state.chat_history
                + [{"role": "agent", "agent": "requirement", "content": msg}],
            }
        )

    # Step 2: ask the conversational LLM the very first follow-up (or summary if everything filled)
    system_with_context = CONVERSATIONAL_SYSTEM_PROMPT + _summarize_known_fields(extracted)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_with_context},
        {"role": "user", "content": state.user_prompt[:_MAX_USER_INPUT_CHARS]},
    ]
    try:
        result = llm.chat_completion(messages, temperature=0.7)
        first_msg = result.content
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM initial message failed: %s", exc)
        first_msg = "What are you planning to do on this VM?"

    turn = ConversationTurn(role=TurnRole.AGENT, content=first_msg)
    return state.model_copy(
        update={
            "conversation": [turn],
            "requirement_phase": RequirementPhase.ASKING,
            "extracted_intent": extracted,
        }
    )


def _handle_resuming_confirmation(state: GraphState, llm: LLMClient) -> GraphState:
    partial = _extract_from_conversation(state.conversation, llm)
    return _finalize_draft(state.model_copy(update={"partial_requirement": partial}))


def _extract_from_conversation(
    conversation: list[ConversationTurn], llm: LLMClient
) -> PartialRequirement:
    conv_text = "\n".join(
        f"{'User' if t.role == TurnRole.USER else 'Assistant'}: {t.content}"
        for t in conversation
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": REQUIREMENT_EXTRACTION_PROMPT},
        {"role": "user", "content": conv_text[:4000]},
    ]
    try:
        result = llm.chat_completion(
            messages, response_format={"type": "json_object"}, temperature=0.0
        )
        data: dict[str, Any] = json.loads(result.content)
        return _parse_partial(data, PartialRequirement())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Conversation extraction failed: %s", exc)
        return PartialRequirement()


def _extract_full_from_conversation(
    conversation: list[ConversationTurn], llm: LLMClient
) -> PartialRequirementExtended:
    """Extract the extended partial (with ports/script/container/etc.) at end of chat."""
    conv_text = "\n".join(
        f"{'User' if t.role == TurnRole.USER else 'Assistant'}: {t.content}"
        for t in conversation
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": REQUIREMENT_EXTRACTION_PROMPT},
        {"role": "user", "content": conv_text[:4000]},
    ]
    try:
        result = llm.chat_completion(
            messages, response_format={"type": "json_object"}, temperature=0.0
        )
        data: dict[str, Any] = json.loads(result.content)
        return _parse_extended(data)
    except Exception as exc:  # noqa: BLE001
        logger.warning("extended extraction failed: %s", exc)
        return PartialRequirementExtended()


def _finalize_draft(state: GraphState) -> GraphState:
    partial = state.partial_requirement or PartialRequirement()
    extracted = state.extracted_intent or PartialRequirementExtended()
    filled = _apply_defaults(partial)
    try:
        draft = RequirementDraft(
            intent="gpu_vm",
            workload_intent=filled.workload_intent or WorkloadIntent.UNKNOWN,
            gpu_type=filled.gpu_type or GpuType.T4,
            gpu_count=filled.gpu_count or 1,
            cpu_floor=filled.cpu_floor or CpuClass.C8,
            memory_floor=filled.memory_floor or MemoryClass.M32,
            os_family=filled.os_family or OsFamily.DEEP_LEARNING,
            disk_size_gb=filled.disk_size_gb or 100,
            preemptible=filled.preemptible if filled.preemptible is not None else False,
            region_preference=filled.region_preference or RegionPreference.NONE,
            # Extended fields — merge from extracted_intent (which has the richer data)
            # plus the partial_requirement that the user may have confirmed in chat
            purpose=extracted.purpose or "",
            open_ports=extracted.open_ports or [],
            public_ip=extracted.public_ip if extracted.public_ip is not None else True,
            startup_script=extracted.startup_script or "",
            software_packages=extracted.software_packages or [],
            container_image=extracted.container_image or "",
            ssh_public_key=extracted.ssh_public_key or "",
            labels={},
        )
    except (ValueError, KeyError) as exc:
        return state.model_copy(
            update={
                "error": f"Invalid workload configuration: {exc}",
                "requirement_phase": RequirementPhase.AWAITING_CONFIRMATION,
            }
        )
    gpu_display = _GPU_DISPLAY.get(draft.gpu_type.value, draft.gpu_type.name)
    extras: list[str] = []
    if draft.open_ports:
        extras.append(f"ports {', '.join(str(p) for p in draft.open_ports)} open")
    if draft.container_image:
        extras.append(f"container {draft.container_image}")
    extras_str = (" · " + ", ".join(extras)) if extras else ""
    return state.model_copy(
        update={
            "requirement_draft": draft,
            "confirmation_response": None,
            "stage": FlowStage.ARCHITECTURE,
            "requirement_phase": RequirementPhase.RESUMING_CONFIRMATION,
            "chat_history": state.chat_history
            + [
                {
                    "role": "agent",
                    "agent": "requirement",
                    "content": (
                        f"Confirmed: {draft.gpu_count}× {gpu_display}, "
                        f"{draft.cpu_floor.value} vCPU, {draft.memory_floor.value} GB RAM"
                        f"{extras_str}."
                    ),
                }
            ],
        }
    )


def _parse_partial(data: dict[str, Any], fallback: PartialRequirement) -> PartialRequirement:
    def _safe_enum(cls: type, val: object, default: object) -> object:
        try:
            return cls(val)
        except (ValueError, KeyError):
            return default

    gpu_type = _safe_enum(GpuType, data.get("gpu_type"), fallback.gpu_type)
    cpu_floor = _safe_enum(CpuClass, str(data.get("cpu_floor") or ""), fallback.cpu_floor)
    memory_floor = _safe_enum(
        MemoryClass, str(data.get("memory_floor") or ""), fallback.memory_floor
    )
    os_family = _safe_enum(OsFamily, data.get("os_family"), fallback.os_family)
    region_pref = _safe_enum(
        RegionPreference, data.get("region_preference"), fallback.region_preference
    )
    workload_intent = _safe_enum(
        WorkloadIntent, data.get("workload_intent"), fallback.workload_intent
    )

    gpu_count_raw = data.get("gpu_count")
    gpu_count: int | None = int(gpu_count_raw) if gpu_count_raw is not None else fallback.gpu_count
    disk_raw = data.get("disk_size_gb")
    disk_size: int | None = int(disk_raw) if disk_raw is not None else fallback.disk_size_gb
    preemptible_raw = data.get("preemptible")
    preemptible: bool | None = (
        bool(preemptible_raw) if preemptible_raw is not None else fallback.preemptible
    )

    return PartialRequirement(
        workload_intent=workload_intent,  # type: ignore[arg-type]
        gpu_type=gpu_type,  # type: ignore[arg-type]
        gpu_count=gpu_count,
        cpu_floor=cpu_floor,  # type: ignore[arg-type]
        memory_floor=memory_floor,  # type: ignore[arg-type]
        os_family=os_family,  # type: ignore[arg-type]
        disk_size_gb=disk_size,
        preemptible=preemptible,
        region_preference=region_pref,  # type: ignore[arg-type]
    )


def _parse_extended(data: dict[str, Any]) -> PartialRequirementExtended:
    """Parse the JSON output of the intent extraction LLM into a typed model.

    Tolerant of nulls, unknown enum values, and type mismatches.
    """
    def _safe_enum(cls: type, val: object) -> object | None:
        if val is None or val == "null":
            return None
        try:
            return cls(val)
        except (ValueError, KeyError):
            return None

    def _safe_int(val: object) -> int | None:
        if val is None or val == "null":
            return None
        try:
            return int(val)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            return None

    def _safe_bool(val: object) -> bool | None:
        if val is None or val == "null":
            return None
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            if val.lower() in ("true", "yes", "1"):
                return True
            if val.lower() in ("false", "no", "0"):
                return False
        return None

    def _safe_str(val: object) -> str | None:
        if val is None or val == "null":
            return None
        s = str(val).strip()
        return s or None

    def _safe_int_list(val: object) -> list[int] | None:
        if val is None or val == "null":
            return None
        if not isinstance(val, list):
            return None
        out: list[int] = []
        for x in val:
            try:
                p = int(x)
                if 1 <= p <= 65535:
                    out.append(p)
            except (ValueError, TypeError):
                continue
        return out or None

    def _safe_str_list(val: object) -> list[str] | None:
        if val is None or val == "null":
            return None
        if not isinstance(val, list):
            return None
        out = [str(x).strip() for x in val if str(x).strip()]
        return out or None

    return PartialRequirementExtended(
        workload_intent=_safe_enum(WorkloadIntent, data.get("workload_intent")),  # type: ignore[arg-type]
        gpu_type=_safe_enum(GpuType, data.get("gpu_type")),  # type: ignore[arg-type]
        gpu_count=_safe_int(data.get("gpu_count")),
        cpu_floor=_safe_enum(CpuClass, str(data.get("cpu_floor") or "")),  # type: ignore[arg-type]
        memory_floor=_safe_enum(MemoryClass, str(data.get("memory_floor") or "")),  # type: ignore[arg-type]
        os_family=_safe_enum(OsFamily, data.get("os_family")),  # type: ignore[arg-type]
        disk_size_gb=_safe_int(data.get("disk_size_gb")),
        preemptible=_safe_bool(data.get("preemptible")),
        region_preference=_safe_enum(RegionPreference, data.get("region_preference")),  # type: ignore[arg-type]
        purpose=_safe_str(data.get("purpose")),
        open_ports=_safe_int_list(data.get("open_ports")),
        public_ip=_safe_bool(data.get("public_ip")),
        startup_script=_safe_str(data.get("startup_script")),
        software_packages=_safe_str_list(data.get("software_packages")),
        container_image=_safe_str(data.get("container_image")),
        ssh_public_key=_safe_str(data.get("ssh_public_key")),
    )


def _apply_defaults(partial: PartialRequirement) -> PartialRequirement:
    intent = partial.workload_intent
    defaults = get_defaults(intent)
    updates: dict[str, Any] = {}
    if partial.gpu_type is None:
        updates["gpu_type"] = defaults["gpu_type"]
    if partial.gpu_count is None:
        updates["gpu_count"] = defaults["gpu_count"]
    if partial.cpu_floor is None:
        updates["cpu_floor"] = defaults["cpu_floor"]
    if partial.memory_floor is None:
        updates["memory_floor"] = defaults["memory_floor"]
    if partial.os_family is None:
        updates["os_family"] = defaults["os_family"]
    if partial.disk_size_gb is None:
        updates["disk_size_gb"] = defaults["disk_size_gb"]
    if partial.preemptible is None:
        updates["preemptible"] = defaults["preemptible"]
    if partial.region_preference is None:
        updates["region_preference"] = defaults["region_preference"]
    return partial.model_copy(update=updates)
