from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibeops.terraform.errors import TerraformPlanError
from vibeops.terraform.runner import plan


def _make_proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


def test_plan_calls_correct_command(tmp_path: Path) -> None:
    with (
        patch("vibeops.terraform.runner._find_terraform", return_value="terraform"),
        patch("vibeops.terraform.runner.subprocess.run", return_value=_make_proc()) as mock_run,
    ):
        plan(tmp_path)
    cmd = mock_run.call_args[0][0]
    assert cmd[:2] == ["terraform", "plan"]
    assert "-no-color" in cmd
    assert any(a.startswith("-out=") and a.endswith("tfplan") for a in cmd)
    assert "-input=false" in cmd


def test_plan_uses_correct_cwd(tmp_path: Path) -> None:
    with patch("vibeops.terraform.runner.subprocess.run", return_value=_make_proc()) as mock_run:
        plan(tmp_path)
    assert mock_run.call_args[1]["cwd"] == tmp_path


def test_plan_returns_result_on_success(tmp_path: Path) -> None:
    stdout = "Plan: 2 to add, 0 to change, 0 to destroy."
    with patch("vibeops.terraform.runner.subprocess.run", return_value=_make_proc(stdout=stdout)):
        result = plan(tmp_path)
    assert result.add_count == 2
    assert result.plan_file == str(tmp_path / "tfplan")


def test_plan_raises_on_nonzero(tmp_path: Path) -> None:
    with patch(
        "vibeops.terraform.runner.subprocess.run",
        return_value=_make_proc(returncode=1, stderr="Error: quota"),
    ):
        with pytest.raises(TerraformPlanError) as exc_info:
            plan(tmp_path)
    assert "quota" in exc_info.value.stderr


def test_plan_raises_on_timeout(tmp_path: Path) -> None:
    with patch(
        "vibeops.terraform.runner.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="terraform", timeout=60),
    ):
        with pytest.raises(TerraformPlanError):
            plan(tmp_path)


def test_plan_raises_on_missing_binary(tmp_path: Path) -> None:
    with patch(
        "vibeops.terraform.runner.subprocess.run",
        side_effect=FileNotFoundError("terraform not found"),
    ):
        with pytest.raises(TerraformPlanError):
            plan(tmp_path)
