from __future__ import annotations

import json
import logging
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from vibeops.models.iac import CostEstimate, CostLineItem

logger = logging.getLogger(__name__)

_TIMEOUT = 30


def run_infracost(tf_dir: Path) -> CostEstimate | None:
    """Shell out to infracost and parse the result.

    Returns None on any failure so the caller can fall back to the GCP price table.
    """
    try:
        proc = subprocess.run(
            [
                "infracost",
                "breakdown",
                "--path",
                str(tf_dir),
                "--format",
                "json",
                "--no-color",
            ],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        logger.warning("infracost timed out after %ds", _TIMEOUT)
        return None
    except FileNotFoundError:
        logger.info("infracost binary not found; using price-table fallback")
        return None

    if proc.returncode != 0:
        logger.warning("infracost exited %d: %s", proc.returncode, proc.stderr[:200])
        return None

    try:
        return _parse(proc.stdout)
    except Exception as exc:
        logger.warning("infracost parse error: %s", exc)
        return None


def _parse(raw_json: str) -> CostEstimate:
    data: dict[str, object] = json.loads(raw_json)

    summary: dict[str, object] = data.get("summary", {})  # type: ignore[assignment]
    hourly = float(summary.get("totalHourlyCost") or 0.0)  # type: ignore[arg-type]
    monthly = float(summary.get("totalMonthlyCost") or 0.0)  # type: ignore[arg-type]

    projects: list[dict[str, object]] = data.get("projects", [])  # type: ignore[assignment]
    breakdown: list[CostLineItem] = []
    notes: list[str] = []
    has_skipped = False

    for project in projects:
        bd: dict[str, object] = project.get("breakdown") or {}  # type: ignore[assignment]
        resources: list[dict[str, object]] = bd.get("resources") or []  # type: ignore[assignment]
        for res in resources:
            name = str(res.get("name", "unknown"))
            r_hourly = float(res.get("hourlyCost") or 0.0)  # type: ignore[arg-type]
            r_monthly = float(res.get("monthlyCost") or 0.0)  # type: ignore[arg-type]
            breakdown.append(
                CostLineItem(description=name, hourly_usd=r_hourly, monthly_usd=r_monthly)
            )

        skipped: list[object] = bd.get("skippedResources") or []  # type: ignore[assignment]
        if skipped:
            has_skipped = True
            notes.append(f"{len(skipped)} resource(s) skipped by infracost (coverage gap)")

    confidence: str = "medium" if has_skipped else "high"

    return CostEstimate(
        hourly_usd=hourly,
        monthly_usd=monthly,
        source="infracost",
        confidence=confidence,  # type: ignore[arg-type]
        breakdown=breakdown,
        notes=notes,
        estimated_at=datetime.now(UTC),
    )
