from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class TurnRole(StrEnum):
    AGENT = "agent"
    USER = "user"


class ConversationTurn(BaseModel):
    role: TurnRole
    content: str


class RequirementPhase(StrEnum):
    INITIAL = "initial"
    ASKING = "asking"
    RESUMING_ASKING = "resuming_asking"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    RESUMING_CONFIRMATION = "resuming_confirmation"
    RE_OPENED = "re_opened"
