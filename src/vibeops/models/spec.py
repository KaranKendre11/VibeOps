from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class GpuType(StrEnum):
    T4 = "nvidia-tesla-t4"
    L4 = "nvidia-l4"
    A100_40 = "nvidia-tesla-a100"


class ComputeSpec(BaseModel):
    machine_type: str
    zone: str
    gpu_type: GpuType
    gpu_count: int = Field(ge=1, le=16)
    preemptible: bool
    custom_startup_script_request: str | None = None


class StorageSpec(BaseModel):
    disk_size_gb: int = Field(ge=10, le=2000)
    os_image_family: str
    os_image_project: str


class NetworkSpec(BaseModel):
    network_name: str
    create_external_ip: bool = True
    open_ports: list[int] = Field(default_factory=list)


class AppSpec(BaseModel):
    """Optional application-layer config that's wired into the VM at boot."""
    startup_script: str = ""
    software_packages: list[str] = Field(default_factory=list)
    container_image: str = ""
    ssh_public_key: str = ""
    labels: dict[str, str] = Field(default_factory=dict)
    purpose: str = ""


class DeploymentSpec(BaseModel):
    compute: ComputeSpec
    storage: StorageSpec
    network: NetworkSpec
    project_id: str
    app: AppSpec = Field(default_factory=AppSpec)
