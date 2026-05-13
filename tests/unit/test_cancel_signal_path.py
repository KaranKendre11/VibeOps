from __future__ import annotations

import io
import signal
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibeops.terraform.runner import apply
from vibeops.terraform.errors import TerraformApplyError


def test_cancel_event_triggers_sigint(tmp_path: Path) -> None:
    cancel_event = threading.Event()
    lines_seen = []

    proc = MagicMock()
    call_count = 0

    def fake_readline() -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "Starting apply...\n"
        if call_count == 2:
            cancel_event.set()
            return "Creating resources...\n"
        return ""

    proc.stdout.readline = fake_readline
    proc.wait.return_value = -2
    proc.returncode = -2

    with patch("vibeops.terraform.runner.subprocess.Popen", return_value=proc):
        with patch("vibeops.terraform.runner.parse_state_resources", return_value=[]):
            with pytest.raises(TerraformApplyError):
                apply(tmp_path, on_log=lines_seen.append, cancel_event=cancel_event)

    proc.send_signal.assert_called_with(signal.SIGINT)


def test_no_cancel_no_sigint(tmp_path: Path) -> None:
    proc = MagicMock()
    proc.stdout = io.StringIO("Apply complete! Resources: 1 added, 0 changed, 0 destroyed.\n")
    proc.wait.return_value = 0
    proc.returncode = 0

    with patch("vibeops.terraform.runner.subprocess.Popen", return_value=proc):
        apply(tmp_path, on_log=lambda _: None)

    proc.send_signal.assert_not_called()
