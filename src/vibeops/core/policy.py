from __future__ import annotations

from pathlib import Path
from typing import Any

import hcl2

from vibeops.models.iac import AllowlistResult, Violation

ALLOWED_RESOURCE_TYPES: frozenset[str] = frozenset(
    {
        "google_compute_instance",
        "google_compute_disk",
        "google_compute_attached_disk",
        "google_compute_firewall",
    }
)

ALLOWED_DATA_SOURCES: frozenset[str] = frozenset(
    {
        "google_compute_network",
        "google_compute_subnetwork",
        "google_compute_image",
    }
)


def _strip_quotes(s: str) -> str:
    """hcl2 wraps identifier strings in double-quotes; strip them."""
    return s.strip('"')


def check_resource_allowlist(hcl_path: Path) -> AllowlistResult:
    """Parse HCL at the path and return any resource-type violations.

    Data-source blocks are checked against ALLOWED_DATA_SOURCES.
    Resource blocks are checked against ALLOWED_RESOURCE_TYPES.
    Line numbers are best-effort (0 when unavailable).
    """
    text = hcl_path.read_text(encoding="utf-8").strip()
    if not text:
        return AllowlistResult(ok=True)

    with hcl_path.open(encoding="utf-8") as fh:
        parsed: dict[str, Any] = hcl2.load(fh)

    violations: list[Violation] = []

    # python-hcl2 returns resource/data as lists of single-key dicts
    for block in parsed.get("resource", []):
        for raw_type in block:
            resource_type = _strip_quotes(raw_type)
            if resource_type not in ALLOWED_RESOURCE_TYPES:
                violations.append(Violation(resource_type=resource_type, line_number=0))

    for block in parsed.get("data", []):
        for raw_type in block:
            data_type = _strip_quotes(raw_type)
            if data_type not in ALLOWED_DATA_SOURCES:
                violations.append(Violation(resource_type=data_type, line_number=0))

    return AllowlistResult(ok=len(violations) == 0, violations=violations)
