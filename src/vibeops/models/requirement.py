from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from vibeops.models.spec import GpuType


class CpuClass(StrEnum):
    C4 = "4"
    C8 = "8"
    C16 = "16"
    C32 = "32"


class MemoryClass(StrEnum):
    M16 = "16"
    M32 = "32"
    M64 = "64"
    M128 = "128"


class OsFamily(StrEnum):
    DEEP_LEARNING = "deeplearning-platform-release"
    UBUNTU_LTS = "ubuntu-lts"
    DEBIAN = "debian"


class RegionPreference(StrEnum):
    NONE = "none"
    AMERICAS = "americas"
    EUROPE = "europe"
    ASIA = "asia"


class WorkloadIntent(StrEnum):
    INFERENCE_SMALL = "inference_small"
    INFERENCE_LARGE = "inference_large"
    FINE_TUNING = "fine_tuning"
    TRAINING = "training"
    OTHER = "other"
    UNKNOWN = "unknown"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PartialRequirement(BaseModel):
    workload_intent: WorkloadIntent | None = None
    workload_intent_confidence: Confidence = Confidence.LOW
    gpu_type: GpuType | None = None
    gpu_type_confidence: Confidence = Confidence.LOW
    gpu_count: int | None = None
    gpu_count_confidence: Confidence = Confidence.LOW
    cpu_floor: CpuClass | None = None
    cpu_floor_confidence: Confidence = Confidence.LOW
    memory_floor: MemoryClass | None = None
    memory_floor_confidence: Confidence = Confidence.LOW
    os_family: OsFamily | None = None
    os_family_confidence: Confidence = Confidence.LOW
    disk_size_gb: int | None = None
    disk_size_gb_confidence: Confidence = Confidence.LOW
    preemptible: bool | None = None
    preemptible_confidence: Confidence = Confidence.LOW
    region_preference: RegionPreference | None = None
    region_preference_confidence: Confidence = Confidence.LOW


class RequirementDraft(BaseModel):
    intent: Literal["gpu_vm"] = "gpu_vm"
    workload_intent: WorkloadIntent
    gpu_type: GpuType
    gpu_count: int = Field(ge=1, le=16)
    cpu_floor: CpuClass
    memory_floor: MemoryClass
    os_family: OsFamily
    disk_size_gb: int = Field(ge=10, le=2000)
    preemptible: bool
    region_preference: RegionPreference

    # ── Optional deployment features ──────────────────────────────────────
    # All optional — only set when the user explicitly asks (in prompt or chat)
    # or when intent-inference is high-confidence (e.g. "Jupyter" → port 8888).
    purpose: str = ""  # free-form goal, e.g. "host a Llama inference API"
    open_ports: list[int] = Field(default_factory=list)  # TCP ports to expose
    public_ip: bool = True  # external IP; auto-true when open_ports non-empty
    startup_script: str = ""  # shell script run on first boot
    software_packages: list[str] = Field(default_factory=list)  # apt packages to preinstall
    container_image: str = ""  # docker image to run on COS at boot
    ssh_public_key: str = ""  # user's pubkey for SSH access
    labels: dict[str, str] = Field(default_factory=dict)  # GCP labels


class PartialRequirementExtended(BaseModel):
    """Output of the intent-extraction LLM call (Chunk 1).

    All fields optional — only the ones the user clearly specified are set.
    """
    workload_intent: WorkloadIntent | None = None
    gpu_type: GpuType | None = None
    gpu_count: int | None = None
    cpu_floor: CpuClass | None = None
    memory_floor: MemoryClass | None = None
    os_family: OsFamily | None = None
    disk_size_gb: int | None = None
    preemptible: bool | None = None
    region_preference: RegionPreference | None = None
    purpose: str | None = None
    open_ports: list[int] | None = None
    public_ip: bool | None = None
    startup_script: str | None = None
    software_packages: list[str] | None = None
    container_image: str | None = None
    ssh_public_key: str | None = None
