from __future__ import annotations

import io
import signal
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibeops.terraform.errors import TerraformApplyError
from vibeops.terraform.runner import apply


def test_cancel_requested_sends_sigint(tmp_path: Path) -> None:
    """When cancel_event is set mid-stream, proc.send_signal(SIGINT) is called."""
    cancel_event = threading.Event()

    lines = ["line 1", "line 2", "line 3"]
    call_count = 0

    proc = MagicMock()
    proc.returncode = -2  # simulate killed

    def fake_readline() -> str:
        nonlocal call_count
        if call_count < len(lines):
            val = lines[call_count] + "\n"
            call_count += 1
            if call_count == 2:
                cancel_event.set()
            return val
        return ""

    proc.stdout.readline = fake_readline
    proc.wait.return_value = -2

    with patch("vibeops.terraform.runner.subprocess.Popen", return_value=proc):
        with patch("vibeops.terraform.runner.parse_state_resources", return_value=[]):
            with pytest.raises(TerraformApplyError):
                apply(tmp_path, on_log=lambda _: None, cancel_event=cancel_event)

    proc.send_signal.assert_called_with(signal.SIGINT)
