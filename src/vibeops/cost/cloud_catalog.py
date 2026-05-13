from __future__ import annotations

import logging
from datetime import UTC, datetime

from vibeops.core.gcp_context import GcpContext
from vibeops.cost.pricing_constants import (
    GPU_HOURLY_USD,
    HOURS_PER_MONTH,
    N1_CPU_HOURLY_USD,
    N1_RAM_GB_HOURLY_USD,
    PD_SSD_GB_MONTHLY_USD,
    PREEMPTIBLE_DISCOUNT,
    PRICES_AS_OF,
)
from vibeops.models.iac import CostEstimate, CostLineItem
from vibeops.models.spec import DeploymentSpec

logger = logging.getLogger(__name__)

_MACHINE_FAMILY_CPU_RATES: dict[str, float] = {
    "n1": N1_CPU_HOURLY_USD,
    "g2": 0.044680,
    "a2": 0.031611,
}
_MACHINE_FAMILY_RAM_RATES: dict[str, float] = {
    "n1": N1_RAM_GB_HOURLY_USD,
    "g2": 0.005654,
    "a2": 0.004237,
}


def _machine_family(machine_type: str) -> str:
    return machine_type.split("-")[0]


def _parse_machine_resources(machine_type: str, ctx: GcpContext) -> tuple[int, float]:
    """Return (vcpus, memory_gb) for the machine type via GCP Compute API."""
    try:
        from google.cloud import compute_v1

        client = compute_v1.MachineTypesClient(credentials=ctx.credentials)
        zone = "us-central1-a"  # fallback zone for lookup; price is the same across zones
        mt = client.get(project=ctx.project_id, zone=zone, machine_type=machine_type)
        return mt.guest_cpus, round(mt.memory_mb / 1024, 1)
    except Exception as exc:
        logger.warning("Machine type lookup failed for %s: %s", machine_type, exc)
        parts = machine_type.split("-")
        try:
            vcpus = int(parts[-1])
        except ValueError:
            vcpus = 4
        return vcpus, vcpus * 3.75  # n1 standard ratio


def estimate_from_catalog(spec: DeploymentSpec, ctx: GcpContext) -> CostEstimate:
    """Estimate cost from GCP pricing constants + machine type lookup."""
    machine_type = spec.compute.machine_type
    family = _machine_family(machine_type)

    vcpus, mem_gb = _parse_machine_resources(machine_type, ctx)

    cpu_rate = _MACHINE_FAMILY_CPU_RATES.get(family, N1_CPU_HOURLY_USD)
    ram_rate = _MACHINE_FAMILY_RAM_RATES.get(family, N1_RAM_GB_HOURLY_USD)

    compute_hourly = vcpus * cpu_rate + mem_gb * ram_rate
    gpu_hourly_unit = GPU_HOURLY_USD.get(spec.compute.gpu_type.value, 0.0)
    gpu_hourly = gpu_hourly_unit * spec.compute.gpu_count
    disk_hourly = (spec.storage.disk_size_gb * PD_SSD_GB_MONTHLY_USD) / HOURS_PER_MONTH

    total_hourly = compute_hourly + gpu_hourly + disk_hourly
    if spec.compute.preemptible:
        total_hourly *= PREEMPTIBLE_DISCOUNT

    preemptible = spec.compute.preemptible
    compute_h = compute_hourly * (PREEMPTIBLE_DISCOUNT if preemptible else 1.0)
    gpu_h = gpu_hourly * (PREEMPTIBLE_DISCOUNT if preemptible else 1.0)

    notes: list[str] = []
    if preemptible:
        notes.append(
            f"Preemptible discount applied: {int(PREEMPTIBLE_DISCOUNT * 100)}% of on-demand"
        )
    notes.append(f"Prices from pricing_constants.py (verified {PRICES_AS_OF})")

    breakdown = [
        CostLineItem(
            description=f"{machine_type} compute ({vcpus} vCPU, {mem_gb} GB RAM)",
            hourly_usd=compute_h,
            monthly_usd=compute_h * HOURS_PER_MONTH,
        ),
        CostLineItem(
            description=f"{spec.compute.gpu_count}x {spec.compute.gpu_type.value}",
            hourly_usd=gpu_h,
            monthly_usd=gpu_h * HOURS_PER_MONTH,
        ),
        CostLineItem(
            description=f"Boot disk {spec.storage.disk_size_gb} GB SSD",
            hourly_usd=disk_hourly,
            monthly_usd=disk_hourly * HOURS_PER_MONTH,
        ),
    ]

    return CostEstimate(
        hourly_usd=total_hourly,
        monthly_usd=total_hourly * HOURS_PER_MONTH,
        source="cloud_catalog",
        confidence="medium",
        breakdown=breakdown,
        notes=notes,
        estimated_at=datetime.now(UTC),
    )
