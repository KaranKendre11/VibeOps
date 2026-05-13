from __future__ import annotations

PRICES_AS_OF = "2025-01"

GPT_4O_MINI_INPUT_PER_1K: float = 0.00015
GPT_4O_MINI_OUTPUT_PER_1K: float = 0.00060

GPT_4O_INPUT_PER_1K: float = 0.00250
GPT_4O_OUTPUT_PER_1K: float = 0.01000

_HOURLY_PRICES: dict[str, float] = {
    "n1-standard-4": 0.19,
    "n1-standard-8": 0.38,
    "n1-standard-16": 0.76,
    "a2-highgpu-1g": 3.67,
    "g2-standard-4": 0.70,
    "g2-standard-8": 1.40,
}

_GPU_ADDON_HOURLY: dict[str, float] = {
    "nvidia-tesla-t4": 0.35,
    "nvidia-l4": 0.70,
    "nvidia-tesla-a100": 2.93,
}

PREEMPTIBLE_FACTOR = 0.3
MONTHLY_HOURS = 730.0


def estimate_hourly(machine_type: str, gpu_type: str, gpu_count: int, preemptible: bool) -> float:
    base = _HOURLY_PRICES.get(machine_type, 0.38)
    gpu_addon = _GPU_ADDON_HOURLY.get(gpu_type, 0.35) * gpu_count
    total = base + gpu_addon
    if preemptible:
        total *= PREEMPTIBLE_FACTOR
    return round(total, 4)
