from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from vibeops.terraform.runner import validate


def _validate_json(valid: bool, errors: list[tuple[str, str]]) -> str:
    diagnostics = [
        {"severity": "error", "summary": s, "detail": d} for s, d in errors
    ]
    return json.dumps({"valid": valid, "diagnostics": diagnostics})


def test_syntax_error_captured_in_result(tmp_path: Path) -> None:
    out = _validate_json(
        valid=False,
        errors=[("Invalid block definition", "A block definition must have block content delimited by '{' and '}'")],
    )
    with patch("subprocess.run", return_value=_mock(returncode=1, stdout=out)):
        result = validate(tmp_path)
    assert result.ok is False
    assert any("Invalid block definition" in e for e in result.errors)


def test_multiple_errors_all_captured(tmp_path: Path) -> None:
    out = _validate_json(
        valid=False,
        errors=[
            ("Error 1", "Detail 1"),
            ("Error 2", "Detail 2"),
        ],
    )
    with patch("subprocess.run", return_value=_mock(returncode=1, stdout=out)):
        result = validate(tmp_path)
    assert len(result.errors) == 2


def test_zero_quota_returns_valid_true_when_hcl_ok(tmp_path: Path) -> None:
    """validate only checks HCL structure — quota errors happen at plan time."""
    out = _validate_json(valid=True, errors=[])
    with patch("subprocess.run", return_value=_mock(returncode=0, stdout=out)):
        result = validate(tmp_path)
    assert result.ok is True


def _mock(returncode: int, stdout: str) -> object:
    import unittest.mock
    proc = unittest.mock.MagicMock(spec=subprocess.CompletedProcess)
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = ""
    return proc
