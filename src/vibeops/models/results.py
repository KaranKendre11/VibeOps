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
    # Estimated on-demand (or preemptible) monthly cost in USD; None when it can't be estimated.
    monthly_cost_usd: float | None = None


class InstancesResult(BaseModel):
    instances: list[RunningInstance] = Field(default_factory=list)


class Disk(BaseModel):
    name: str
    zone: str
    size_gb: int
    type: str = ""  # short disk type, e.g. "pd-ssd", "pd-balanced", "pd-standard"
    status: str = ""
    users: list[str] = Field(default_factory=list)  # short names of attached instances
    creation_timestamp: str = ""
    monthly_cost_usd: float | None = None


class DisksResult(BaseModel):
    disks: list[Disk] = Field(default_factory=list)


class CustomImage(BaseModel):
    name: str
    disk_size_gb: int
    family: str = ""
    status: str = ""
    creation_timestamp: str = ""
    # Images are billed on stored bytes; left None (usage-based, not a flat monthly rate).
    monthly_cost_usd: float | None = None


class CustomImagesResult(BaseModel):
    images: list[CustomImage] = Field(default_factory=list)
