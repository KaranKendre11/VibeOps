from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from vibeops.terraform.runner import parse_state_resources

_SHOW_OUTPUT = json.dumps({
    "values": {
        "root_module": {
            "resources": [
                {
                    "type": "google_compute_instance",
                    "name": "main",
                    "provider_name": "registry.terraform.io/hashicorp/google",
                    "values": {"zone": "us-central1-a"},
                },
                {
                    "type": "google_compute_disk",
                    "name": "boot",
                    "provider_name": "registry.terraform.io/hashicorp/google",
                    "values": {"zone": "us-central1-a"},
                },
            ]
        }
    }
})


def _make_proc(stdout: str, returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.stdout = stdout
    proc.returncode = returncode
    return proc


def test_parse_state_returns_two_resources(tmp_path: Path) -> None:
    with patch("vibeops.terraform.runner.subprocess.run", return_value=_make_proc(_SHOW_OUTPUT)):
        resources = parse_state_resources(tmp_path)

    assert len(resources) == 2
    assert resources[0].type == "google_compute_instance"
    assert resources[0].name == "main"
    assert resources[0].zone == "us-central1-a"


def test_parse_state_empty_when_no_state(tmp_path: Path) -> None:
    with patch(
        "vibeops.terraform.runner.subprocess.run",
        return_value=_make_proc("", returncode=1),
    ):
        resources = parse_state_resources(tmp_path)

    assert resources == []


def test_parse_state_empty_on_missing_state_file(tmp_path: Path) -> None:
    with patch(
        "vibeops.terraform.runner.subprocess.run",
        side_effect=FileNotFoundError("terraform not found"),
    ):
        resources = parse_state_resources(tmp_path)

    assert resources == []


def test_parse_state_empty_on_invalid_json(tmp_path: Path) -> None:
    with patch("vibeops.terraform.runner.subprocess.run", return_value=_make_proc("not-json")):
        resources = parse_state_resources(tmp_path)

    assert resources == []
