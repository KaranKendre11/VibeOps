"""UI-agnostic requirement-conversation logic: affirmative detection + turn evaluation.

Extracted from ``vibeops.ui.chat`` so the FastAPI chat endpoint and unit tests can use it without
Streamlit.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vibeops.models.conversation import ConversationTurn, TurnRole

_AFFIRMATIVE_TOKENS = (
    "yes", "yeah", "yep", "yup", "y", "sure", "ok", "okay", "k",
    "go", "ship", "ship it", "deploy", "do it", "proceed", "confirm",
    "looks good", "lgtm", "perfect", "great", "fine", "correct", "right",
    "sounds good", "good", "all good", "send it", "let's go", "lets go",
)


def is_affirmative(text: str) -> bool:
    """True when the user message looks like a confirmation.

    Conservative — short messages containing an affirmative token count. Long messages don't
    (even if they contain "yes"), because those usually carry additional change requests.
    """
    t = text.strip().lower()
    if not t:
        return False
    t = t.rstrip(".!?,;:")
    if t in _AFFIRMATIVE_TOKENS:
        return True
    if len(t) <= 20:
        first_word = t.split()[0] if t.split() else ""
        if first_word in _AFFIRMATIVE_TOKENS:
            return True
    return False


@dataclass
class TurnResult:
    proceed: bool
    cleaned_response: str
    new_conversation: list[dict[str, Any]]


def evaluate_turn(conversation: list[ConversationTurn], reply: str, response: str) -> TurnResult:
    """Decide whether the requirement conversation should proceed, and build the updated
    conversation list. Mirrors ``ui.chat._render_asking``'s post-stream logic.

    Code-side safety: even if the LLM emits ``[[PROCEED]]`` alongside the summary on the first
    turn (a known failure mode), only honor it when the user's latest message actually looks like
    a confirmation — so the flow never jumps past the summary without explicit consent.
    """
    proceed_token_present = "[[PROCEED]]" in response
    looks_like_confirmation = is_affirmative(reply)
    proceed = proceed_token_present and looks_like_confirmation

    clean = response.replace("[[PROCEED]]", "").strip()
    if proceed_token_present and not looks_like_confirmation:
        clean = clean or "Does this look good? Reply 'yes' to deploy or tell me what to change."

    new_conv: list[dict[str, Any]] = [t.model_dump() for t in conversation]
    new_conv.append(ConversationTurn(role=TurnRole.USER, content=reply[:1000]).model_dump())
    new_conv.append(ConversationTurn(role=TurnRole.AGENT, content=clean).model_dump())
    return TurnResult(proceed=proceed, cleaned_response=clean, new_conversation=new_conv)
