from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibeops.cost.infracost import run_infracost


def _proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    p = MagicMock(spec=subprocess.CompletedProcess)
    p.returncode = returncode
    p.stdout = stdout
    p.stderr = stderr
    return p


def _infracost_json(
    hourly: float = 1.0,
    monthly: float = 730.0,
    resources: list[dict[str, object]] | None = None,
    skipped: list[object] | None = None,
) -> str:
    return json.dumps(
        {
            "summary": {"totalHourlyCost": str(hourly), "totalMonthlyCost": str(monthly)},
            "projects": [
                {
                    "breakdown": {
                        "resources": resources or [],
                        "skippedResources": skipped or [],
                    }
                }
            ],
        }
    )


class TestRunInfracost:
    def test_success_returns_estimate(self, tmp_path: Path) -> None:
        out = _infracost_json(hourly=0.5, monthly=365.0)
        with patch("subprocess.run", return_value=_proc(stdout=out)):
            result = run_infracost(tmp_path)
        assert result is not None
        assert result.source == "infracost"
        assert result.hourly_usd == pytest.approx(0.5)
        assert result.monthly_usd == pytest.approx(365.0)

    def test_source_is_infracost(self, tmp_path: Path) -> None:
        with patch("subprocess.run", return_value=_proc(stdout=_infracost_json())):
            result = run_infracost(tmp_path)
        assert result is not None
        assert result.source == "infracost"

    def test_confidence_high_when_no_skipped(self, tmp_path: Path) -> None:
        with patch("subprocess.run", return_value=_proc(stdout=_infracost_json())):
            result = run_infracost(tmp_path)
        assert result is not None
        assert result.confidence == "high"

    def test_confidence_medium_when_skipped_resources(self, tmp_path: Path) -> None:
        out = _infracost_json(skipped=[{"name": "skipped-resource"}])
        with patch("subprocess.run", return_value=_proc(stdout=out)):
            result = run_infracost(tmp_path)
        assert result is not None
        assert result.confidence == "medium"
        assert any("skipped" in n for n in result.notes)

    def test_breakdown_populated(self, tmp_path: Path) -> None:
        resources = [{"name": "google_compute_instance.gpu_vm", "hourlyCost": "0.4", "monthlyCost": "292.0"}]
        out = _infracost_json(resources=resources)
        with patch("subprocess.run", return_value=_proc(stdout=out)):
            result = run_infracost(tmp_path)
        assert result is not None
        assert len(result.breakdown) == 1
        assert "google_compute_instance" in result.breakdown[0].description

    def test_timeout_returns_none(self, tmp_path: Path) -> None:
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("infracost", 30)):
            result = run_infracost(tmp_path)
        assert result is None

    def test_binary_not_found_returns_none(self, tmp_path: Path) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = run_infracost(tmp_path)
        assert result is None

    def test_nonzero_exit_returns_none(self, tmp_path: Path) -> None:
        with patch("subprocess.run", return_value=_proc(returncode=1, stderr="Error")):
            result = run_infracost(tmp_path)
        assert result is None

    def test_parse_error_returns_none(self, tmp_path: Path) -> None:
        with patch("subprocess.run", return_value=_proc(stdout="not json")):
            result = run_infracost(tmp_path)
        assert result is None
