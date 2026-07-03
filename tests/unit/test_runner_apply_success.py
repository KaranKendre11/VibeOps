from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

from vibeops.terraform.runner import apply


def _make_streaming_proc(lines: list[str], returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.stdout = io.StringIO("\n".join(lines) + ("\n" if lines else ""))
    proc.returncode = returncode
    proc.wait.return_value = returncode
    proc.poll.return_value = returncode
    return proc


def test_apply_calls_on_log_for_each_line(tmp_path: Path) -> None:
    lines = ["line one", "line two", "Apply complete! Resources: 1 added, 0 changed, 0 destroyed."]
    logged: list[str] = []

    with patch("vibeops.terraform.runner.subprocess.Popen", return_value=_make_streaming_proc(lines)):
        apply(tmp_path, on_log=logged.append)

    assert logged == lines


def test_apply_result_full_log(tmp_path: Path) -> None:
    lines = ["a", "b", "Apply complete! Resources: 2 added, 0 changed, 0 destroyed."]

    with patch("vibeops.terraform.runner.subprocess.Popen", return_value=_make_streaming_proc(lines)):
        result = apply(tmp_path, on_log=lambda _: None)

    assert "a" in result.full_log
    assert "b" in result.full_log


def test_apply_parses_resources_created(tmp_path: Path) -> None:
    lines = ["Apply complete! Resources: 3 added, 0 changed, 0 destroyed."]

    with patch("vibeops.terraform.runner.subprocess.Popen", return_value=_make_streaming_proc(lines)):
        result = apply(tmp_path, on_log=lambda _: None)

    assert result.resources_created == 3


def test_apply_command_includes_plan_file(tmp_path: Path) -> None:
    with patch("vibeops.terraform.runner.subprocess.Popen", return_value=_make_streaming_proc([])) as mock_popen:
        apply(tmp_path, on_log=lambda _: None)

    cmd = mock_popen.call_args[0][0]
    assert "terraform" in cmd[0]
    assert "apply" in cmd
    assert "-auto-approve" in cmd
    assert "tfplan" in " ".join(cmd)
