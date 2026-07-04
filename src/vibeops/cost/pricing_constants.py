"""Maintained GCP price table — a hand-verified snapshot of GCP's published prices.

These constants are the fallback cost source when Infracost is not configured;
nothing here queries the GCP Cloud Billing Catalog API at runtime.

Prices last verified: 2026-05-11 against GCP pricing calculator
(https://cloud.google.com/products/calculator).

All prices are USD per hour for on-demand unless noted.
Preemptible price = on-demand * PREEMPTIBLE_DISCOUNT.
"""
from __future__ import annotations

# Preemptible VMs are priced at ~30% of on-demand (Google's published default).
# Verify against https://cloud.google.com/compute/vm-instance-pricing before M3 merge.
PREEMPTIBLE_DISCOUNT: float = 0.30

# GPU on-demand hourly prices (USD).  Source: GCP GPU pricing page 2026-05-11.
GPU_HOURLY_USD: dict[str, float] = {
    "nvidia-tesla-t4": 0.35,
    "nvidia-l4": 0.70,
    "nvidia-tesla-a100": 2.93,  # A100 40GB
}

# n1 machine family: per-vCPU and per-GB-RAM hourly on-demand rates.
N1_CPU_HOURLY_USD: float = 0.031611
N1_RAM_GB_HOURLY_USD: float = 0.004237

# g2 machine family (L4 host): per-vCPU and per-GB-RAM.
G2_CPU_HOURLY_USD: float = 0.044680
G2_RAM_GB_HOURLY_USD: float = 0.005654

# a2 machine family (A100 host): fixed per-accelerator pricing included in machine type.
A2_CPU_HOURLY_USD: float = 0.031611  # fallback; a2 pricing is usually machine-type-level

# Persistent disk: SSD (pd-ssd) USD per GB per month → convert to hourly
PD_SSD_GB_MONTHLY_USD: float = 0.17
PD_STANDARD_GB_MONTHLY_USD: float = 0.04

HOURS_PER_MONTH: float = 730.0

PRICES_AS_OF: str = "2026-05-11"
