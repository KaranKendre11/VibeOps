from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from vibeops.models.architecture import ArchitectureOptions
from vibeops.models.conversation import ConversationTurn, RequirementPhase
from vibeops.models.deployment import DeploymentOutcome, DeploymentPhase, StateResource
from vibeops.models.iac import CostEstimate
from vibeops.models.requirement import (
    PartialRequirement,
    PartialRequirementExtended,
    RequirementDraft,
)
from vibeops.models.spec import DeploymentSpec


class FlowStage(StrEnum):
    REQUIREMENT = "requirement"
    ARCHITECTURE = "architecture"
    AWAITING_ARCHITECTURE = "awaiting_architecture"
    IAC = "iac"
    AWAITING_APPROVAL = "awaiting_approval"
    DEPLOYMENT = "deployment"
    DONE = "done"
    CANCELLED = "cancelled"


class GraphState(BaseModel):
    """Shared state passed between LangGraph nodes. Must be JSON-serializable."""

    user_prompt: str = Field(..., description="The original user prompt.")
    chat_history: list[dict[str, str]] = Field(default_factory=list)

    # Requirement Agent — conversation
    requirement_phase: RequirementPhase = Field(default=RequirementPhase.INITIAL)
    conversation: list[ConversationTurn] = Field(default_factory=list)
    requirement_turns: int = Field(default=0, description="Number of agent questions asked.")
    partial_requirement: PartialRequirement | None = Field(default=None)
    forced_finish: bool = Field(default=False, description="True when turn cap hit.")
    confirmation_response: dict[str, Any] | None = Field(
        default=None, description="Raw widget values from the workload card."
    )
    requirement_draft: RequirementDraft | None = Field(
        default=None, description="Final validated requirement after confirmation card."
    )
    extracted_intent: PartialRequirementExtended | None = Field(
        default=None,
        description="Output of the Chunk 1 intent-extraction LLM call. "
        "Holds whatever the user explicitly said in their first prompt, so the "
        "conversation LLM can skip re-asking known fields.",
    )

    # Architecture Agent
    architecture_options: ArchitectureOptions | None = Field(default=None)
    architecture_response: dict[str, Any] | None = Field(
        default=None, description="User's pick from the architecture card."
    )
    back_to_requirements: bool = Field(
        default=False, description="Signal from architecture card to return to confirmation."
    )

    # IaC / Deployment
    deployment_spec: DeploymentSpec | None = Field(
        default=None, description="Finalized spec produced by Architecture agent."
    )
    terraform_files: dict[str, str] = Field(default_factory=dict)
    terraform_files_original: dict[str, str] = Field(default_factory=dict)
    terraform_dir: str | None = Field(default=None)
    terraform_state_prefix: str | None = Field(
        default=None,
        description="GCS object prefix keying this deployment's remote Terraform state "
        "(issue #3). None when no remote backend is configured (ephemeral local state).",
    )
    cost_estimate_usd: float | None = Field(default=None)
    cost_estimate: CostEstimate | None = Field(default=None)
    cost_cap_exceeded: bool = Field(default=False)
    cost_cap_override: bool = Field(default=False)
    cost_estimate_stale: bool = Field(default=False)
    validation_errors: list[str] = Field(default_factory=list)

    # Approval
    approved: bool = Field(default=False)

    stage: FlowStage = Field(default=FlowStage.REQUIREMENT)
    error: str | None = Field(default=None)

    # Deployment Agent (M4)
    deployment_phase: DeploymentPhase = Field(default=DeploymentPhase.IDLE)
    deployment_logs: list[str] = Field(default_factory=list)
    deployment_outcome: DeploymentOutcome | None = Field(default=None)
    created_resources: list[StateResource] = Field(default_factory=list)
    deployment_error: str | None = Field(default=None)

    # Deployment action flags (set by UI, read by orchestrator routers)
    destroy_confirmed: bool = Field(default=False)
    destroy_requested: bool = Field(default=False)
    retry_requested: bool = Field(default=False)
    leave_as_is_requested: bool = Field(default=False)
    cancel_requested: bool = Field(default=False)

    # Zones excluded from architecture discovery (e.g. after insufficient-capacity failure)
    excluded_zones: list[str] = Field(default_factory=list)
