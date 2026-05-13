from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibeops.models.deployment import StateResource
from vibeops.terraform.errors import TerraformDestroyError
from vibeops.terraform.runner import destroy


def _make_proc(lines: list[str], returncode: int) -> MagicMock:
    proc = MagicMock()
    proc.stdout = io.StringIO("\n".join(lines) + "\n")
    proc.returncode = returncode
    proc.wait.return_value = returncode
    return proc


def test_destroy_raises_on_nonzero(tmp_path: Path) -> None:
    lines = ["Destroying...", "Error: resource has dependents"]
    with patch("vibeops.terraform.runner.subprocess.Popen", return_value=_make_proc(lines, 1)):
        with patch("vibeops.terraform.runner.parse_state_resources", return_value=[]):
            with pytest.raises(TerraformDestroyError) as exc_info:
                destroy(tmp_path, on_log=lambda _: None)

    assert "dependents" in exc_info.value.stderr


def test_destroy_error_carries_remaining_resources(tmp_path: Path) -> None:
    remaining = [StateResource(type="google_compute_instance", name="vm")]
    with patch("vibeops.terraform.runner.subprocess.Popen", return_value=_make_proc(["Error"], 1)):
        with patch("vibeops.terraform.runner.parse_state_resources", return_value=remaining):
            with pytest.raises(TerraformDestroyError) as exc_info:
                destroy(tmp_path, on_log=lambda _: None)

    assert len(exc_info.value.created_resources) == 1
