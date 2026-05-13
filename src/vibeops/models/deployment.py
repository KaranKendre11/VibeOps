from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class DeploymentPhase(StrEnum):
    IDLE = "idle"
    PLANNING = "planning"
    APPLYING = "applying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    AWAITING_DESTROY_CONFIRM = "awaiting_destroy_confirm"
    DESTROYING = "destroying"
    DESTROYED = "destroyed"
    CANCELLED = "cancelled"


class DeploymentOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    PLAN_FAILED = "plan_failed"
    FULL_FAIL = "full_fail"
    PARTIAL_FAIL = "partial_fail"
    DESTROYED = "destroyed"
    DESTROY_FAILED = "destroy_failed"


class StateResource(BaseModel):
    type: str
    name: str
    zone: str | None = None
    provider: str | None = None


class PlanResult(BaseModel):
    plan_file: str
    add_count: int = 0
    change_count: int = 0
    destroy_count: int = 0


class ApplyResult(BaseModel):
    full_log: str
    resources_created: int = 0


class DestroyResult(BaseModel):
    full_log: str
    resources_destroyed: int = 0
