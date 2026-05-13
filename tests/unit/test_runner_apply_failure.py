from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibeops.terraform.errors import TerraformApplyError
from vibeops.terraform.runner import apply


def _make_proc(lines: list[str], returncode: int) -> MagicMock:
    proc = MagicMock()
    proc.stdout = io.StringIO("\n".join(lines) + "\n")
    proc.returncode = returncode
    proc.wait.return_value = returncode
    return proc


def test_apply_raises_on_nonzero(tmp_path: Path) -> None:
    lines = ["Creating...", "Error: quota exceeded"]
    with patch("vibeops.terraform.runner.subprocess.Popen", return_value=_make_proc(lines, returncode=1)):
        with patch("vibeops.terraform.runner.parse_state_resources", return_value=[]):
            with pytest.raises(TerraformApplyError) as exc_info:
                apply(tmp_path, on_log=lambda _: None)

    assert "quota exceeded" in exc_info.value.stderr


def test_apply_error_has_partial_state_false_when_no_resources(tmp_path: Path) -> None:
    with patch("vibeops.terraform.runner.subprocess.Popen", return_value=_make_proc(["Error: fail"], 1)):
        with patch("vibeops.terraform.runner.parse_state_resources", return_value=[]):
            with pytest.raises(TerraformApplyError) as exc_info:
                apply(tmp_path, on_log=lambda _: None)

    assert exc_info.value.partial_state is False


def test_apply_error_has_partial_state_true_when_resources_exist(tmp_path: Path) -> None:
    from vibeops.models.deployment import StateResource

    resource = StateResource(type="google_compute_instance", name="vm")
    with patch("vibeops.terraform.runner.subprocess.Popen", return_value=_make_proc(["Error"], 1)):
        with patch("vibeops.terraform.runner.parse_state_resources", return_value=[resource]):
            with pytest.raises(TerraformApplyError) as exc_info:
                apply(tmp_path, on_log=lambda _: None)

    assert exc_info.value.partial_state is True
    assert len(exc_info.value.created_resources) == 1


def test_apply_error_full_log_preserved(tmp_path: Path) -> None:
    lines = ["line1", "line2", "Error: fail"]
    with patch("vibeops.terraform.runner.subprocess.Popen", return_value=_make_proc(lines, 1)):
        with patch("vibeops.terraform.runner.parse_state_resources", return_value=[]):
            with pytest.raises(TerraformApplyError) as exc_info:
                apply(tmp_path, on_log=lambda _: None)

    assert "line1" in exc_info.value.stderr
