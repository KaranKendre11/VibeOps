from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

from vibeops.terraform.runner import destroy


def _make_proc(lines: list[str], returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.stdout = io.StringIO("\n".join(lines) + "\n")
    proc.returncode = returncode
    proc.wait.return_value = returncode
    return proc


def test_destroy_calls_on_log(tmp_path: Path) -> None:
    lines = ["Destroying...", "Destroy complete! Resources: 1 destroyed."]
    logged: list[str] = []

    with patch("vibeops.terraform.runner.subprocess.Popen", return_value=_make_proc(lines)):
        destroy(tmp_path, on_log=logged.append)

    assert logged == lines


def test_destroy_result_full_log(tmp_path: Path) -> None:
    lines = ["Destroying...", "Destroy complete! Resources: 2 destroyed."]

    with patch("vibeops.terraform.runner.subprocess.Popen", return_value=_make_proc(lines)):
        result = destroy(tmp_path, on_log=lambda _: None)

    assert "Destroying" in result.full_log


def test_destroy_parses_resources_destroyed(tmp_path: Path) -> None:
    lines = ["Destroy complete! Resources: 2 destroyed."]

    with patch("vibeops.terraform.runner.subprocess.Popen", return_value=_make_proc(lines)):
        result = destroy(tmp_path, on_log=lambda _: None)

    assert result.resources_destroyed == 2


def test_destroy_command_is_correct(tmp_path: Path) -> None:
    with patch("vibeops.terraform.runner.subprocess.Popen", return_value=_make_proc([])) as mock_popen:
        destroy(tmp_path, on_log=lambda _: None)

    cmd = mock_popen.call_args[0][0]
    assert "destroy" in cmd
    assert "-auto-approve" in cmd
    assert "-no-color" in cmd
