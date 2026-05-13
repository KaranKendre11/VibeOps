from __future__ import annotations

from vibeops.agents.requirement_defaults import get_defaults
from vibeops.models.requirement import WorkloadIntent
from vibeops.models.spec import GpuType


def test_inference_small_defaults() -> None:
    d = get_defaults(WorkloadIntent.INFERENCE_SMALL)
    assert d["gpu_type"] == GpuType.T4
    assert d["preemptible"] is True
    assert int(str(d["cpu_floor"])) <= 8


def test_fine_tuning_defaults() -> None:
    d = get_defaults(WorkloadIntent.FINE_TUNING)
    assert d["gpu_type"] == GpuType.A100_40
    assert d["preemptible"] is False
    assert int(str(d["disk_size_gb"])) >= 200


def test_training_defaults() -> None:
    d = get_defaults(WorkloadIntent.TRAINING)
    assert d["gpu_type"] == GpuType.A100_40
    assert int(str(d["cpu_floor"])) >= 16
    assert int(str(d["memory_floor"])) >= 64


def test_inference_large_defaults() -> None:
    d = get_defaults(WorkloadIntent.INFERENCE_LARGE)
    assert d["gpu_type"] == GpuType.L4
    assert d["preemptible"] is False


def test_unknown_defaults_to_t4() -> None:
    d = get_defaults(WorkloadIntent.UNKNOWN)
    assert d["gpu_type"] == GpuType.T4


def test_none_intent_defaults_to_unknown() -> None:
    d = get_defaults(None)
    assert d["gpu_type"] == GpuType.T4


def test_all_intents_have_all_required_keys() -> None:
    required = {"gpu_type", "gpu_count", "cpu_floor", "memory_floor", "os_family", "disk_size_gb", "preemptible", "region_preference"}
    for intent in WorkloadIntent:
        d = get_defaults(intent)
        assert required <= set(d.keys()), f"{intent} missing keys"
