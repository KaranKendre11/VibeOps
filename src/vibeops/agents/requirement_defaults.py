from __future__ import annotations

from vibeops.models.requirement import (
    CpuClass,
    MemoryClass,
    OsFamily,
    RegionPreference,
    WorkloadIntent,
)
from vibeops.models.spec import GpuType

_DEFAULTS: dict[WorkloadIntent, dict[str, object]] = {
    WorkloadIntent.INFERENCE_SMALL: {
        "gpu_type": GpuType.T4,
        "gpu_count": 1,
        "cpu_floor": CpuClass.C4,
        "memory_floor": MemoryClass.M16,
        "os_family": OsFamily.DEEP_LEARNING,
        "disk_size_gb": 100,
        "preemptible": True,
        "region_preference": RegionPreference.NONE,
    },
    WorkloadIntent.INFERENCE_LARGE: {
        "gpu_type": GpuType.L4,
        "gpu_count": 1,
        "cpu_floor": CpuClass.C8,
        "memory_floor": MemoryClass.M32,
        "os_family": OsFamily.DEEP_LEARNING,
        "disk_size_gb": 100,
        "preemptible": False,
        "region_preference": RegionPreference.NONE,
    },
    WorkloadIntent.FINE_TUNING: {
        "gpu_type": GpuType.A100_40,
        "gpu_count": 1,
        "cpu_floor": CpuClass.C16,
        "memory_floor": MemoryClass.M64,
        "os_family": OsFamily.DEEP_LEARNING,
        "disk_size_gb": 200,
        "preemptible": False,
        "region_preference": RegionPreference.NONE,
    },
    WorkloadIntent.TRAINING: {
        "gpu_type": GpuType.A100_40,
        "gpu_count": 1,
        "cpu_floor": CpuClass.C32,
        "memory_floor": MemoryClass.M128,
        "os_family": OsFamily.DEEP_LEARNING,
        "disk_size_gb": 500,
        "preemptible": False,
        "region_preference": RegionPreference.NONE,
    },
    WorkloadIntent.OTHER: {
        "gpu_type": GpuType.T4,
        "gpu_count": 1,
        "cpu_floor": CpuClass.C8,
        "memory_floor": MemoryClass.M32,
        "os_family": OsFamily.DEEP_LEARNING,
        "disk_size_gb": 100,
        "preemptible": False,
        "region_preference": RegionPreference.NONE,
    },
    WorkloadIntent.UNKNOWN: {
        "gpu_type": GpuType.T4,
        "gpu_count": 1,
        "cpu_floor": CpuClass.C8,
        "memory_floor": MemoryClass.M32,
        "os_family": OsFamily.DEEP_LEARNING,
        "disk_size_gb": 100,
        "preemptible": False,
        "region_preference": RegionPreference.NONE,
    },
}


def get_defaults(intent: WorkloadIntent | None) -> dict[str, object]:
    resolved = intent if intent is not None else WorkloadIntent.UNKNOWN
    return dict(_DEFAULTS.get(resolved, _DEFAULTS[WorkloadIntent.UNKNOWN]))
