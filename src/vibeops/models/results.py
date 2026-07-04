from __future__ import annotations

from pydantic import BaseModel, Field


class ValidationResult(BaseModel):
    ok: bool = Field(..., description="True if validation succeeded.")
    message: str = Field(..., description="Human-readable status or error description.")
    fingerprint: str | None = Field(default=None)


class ProjectListResult(BaseModel):
    project_ids: list[str] = Field(default_factory=list)


class ZoneAvailability(BaseModel):
    zone: str
    region: str
    gpu_available: bool
    quota_total: int
    quota_used: int

    @property
    def quota_remaining(self) -> int:
        return self.quota_total - self.quota_used


class ZonesWithAcceleratorResult(BaseModel):
    gpu_type: str
    zones: list[ZoneAvailability]


class MachineType(BaseModel):
    name: str
    cpus: int
    memory_gb: float
    gpu_compatible: bool


class MachineTypesResult(BaseModel):
    zone: str
    machine_types: list[MachineType]


class OsImage(BaseModel):
    family: str
    project: str
    description: str


class OsImagesResult(BaseModel):
    images: list[OsImage]


class QuotaResult(BaseModel):
    region: str
    gpu_type: str
    limit: int
    usage: int

    @property
    def remaining(self) -> int:
        return self.limit - self.usage


class Network(BaseModel):
    name: str
    self_link: str
    auto_create_subnetworks: bool


class NetworksResult(BaseModel):
    networks: list[Network]


class ChatResult(BaseModel):
    content: str
    input_tokens: int
    output_tokens: int


class RunningInstance(BaseModel):
    name: str
    zone: str
    machine_type: str
    status: str
    internal_ip: str = ""
    external_ip: str = ""
    creation_timestamp: str = ""
    labels: dict[str, str] = Field(default_factory=dict)
    gpu_summary: str = ""


class InstancesResult(BaseModel):
    instances: list[RunningInstance] = Field(default_factory=list)
