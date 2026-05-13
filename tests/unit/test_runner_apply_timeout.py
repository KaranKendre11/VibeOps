from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from vibeops.terraform.errors import TerraformApplyError
from vibeops.terraform.runner import apply


def _make_hanging_proc() -> MagicMock:
    proc = MagicMock()
    proc.stdout.__iter__ = MagicMock(return_value=iter([]))
    proc.stdout.readline = MagicMock(return_value="")
    proc.wait.side_effect = subprocess.TimeoutExpired(cmd="terraform", timeout=1)
    proc.returncode = None
    return proc


def test_apply_timeout_raises_error(tmp_path: Path) -> None:
    with patch("vibeops.terraform.runner.subprocess.Popen", return_value=_make_hanging_proc()):
        with patch("vibeops.terraform.runner.parse_state_resources", return_value=[]):
            with pytest.raises(TerraformApplyError, match="timed out"):
                apply(tmp_path, on_log=lambda _: None, timeout=1)


def test_apply_timeout_sends_sigterm(tmp_path: Path) -> None:
    proc = _make_hanging_proc()
    with patch("vibeops.terraform.runner.subprocess.Popen", return_value=proc):
        with patch("vibeops.terraform.runner.parse_state_resources", return_value=[]):
            with pytest.raises(TerraformApplyError):
                apply(tmp_path, on_log=lambda _: None, timeout=1)

    proc.terminate.assert_called()
