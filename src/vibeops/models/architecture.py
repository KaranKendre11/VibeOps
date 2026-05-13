from __future__ import annotations

from pydantic import BaseModel

from vibeops.models.requirement import RequirementDraft
from vibeops.models.results import Network


class ArchitectureCandidate(BaseModel):
    zone: str
    region: str
    machine_type: str
    cpus: int
    memory_gb: float
    quota_total: int
    quota_remaining: int
    rationale: str


class ArchitectureOptions(BaseModel):
    candidates: list[ArchitectureCandidate]
    networks: list[Network]
    requirement: RequirementDraft
