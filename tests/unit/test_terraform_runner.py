from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibeops.terraform.runner import (
    TerraformInitError,
    TerraformValidateError,
    init,
    validate,
)


def _completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


class TestInit:
    def test_calls_terraform_init_with_correct_args(self, tmp_path: Path) -> None:
        with (
            patch("vibeops.terraform.runner._find_terraform", return_value="terraform"),
            patch("subprocess.run", return_value=_completed()) as mock_run,
        ):
            init(tmp_path)
        args = mock_run.call_args[0][0]
        assert args[0] == "terraform"
        assert "init" in args
        assert "-no-color" in args

    def test_passes_cwd(self, tmp_path: Path) -> None:
        with patch("subprocess.run", return_value=_completed()) as mock_run:
            init(tmp_path)
        assert mock_run.call_args.kwargs.get("cwd") == tmp_path or \
               mock_run.call_args[1].get("cwd") == tmp_path

    def test_passes_timeout(self, tmp_path: Path) -> None:
        with patch("subprocess.run", return_value=_completed()) as mock_run:
            init(tmp_path, timeout=45)
        kwargs = mock_run.call_args[1] if mock_run.call_args[1] else {}
        assert kwargs.get("timeout") == 45

    def test_nonzero_exit_raises_init_error(self, tmp_path: Path) -> None:
        with patch("subprocess.run", return_value=_completed(returncode=1, stderr="Error")):
            with pytest.raises(TerraformInitError, match="Error"):
                init(tmp_path)

    def test_timeout_raises_init_error(self, tmp_path: Path) -> None:
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("terraform", 60)):
            with pytest.raises(TerraformInitError, match="timed out"):
                init(tmp_path)

    def test_binary_not_found_raises_init_error(self, tmp_path: Path) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            with pytest.raises(TerraformInitError, match="not found"):
                init(tmp_path)

    def test_success_returns_none(self, tmp_path: Path) -> None:
        with patch("subprocess.run", return_value=_completed()):
            result = init(tmp_path)
        assert result is None


class TestValidate:
    def _valid_json(self) -> str:
        return json.dumps({"valid": True, "diagnostics": []})

    def _invalid_json(self, summary: str, detail: str) -> str:
        return json.dumps(
            {
                "valid": False,
                "diagnostics": [
                    {"severity": "error", "summary": summary, "detail": detail}
                ],
            }
        )

    def test_calls_validate_with_correct_args(self, tmp_path: Path) -> None:
        with patch("subprocess.run", return_value=_completed(stdout=self._valid_json())) as mock:
            validate(tmp_path)
        args = mock.call_args[0][0]
        assert "validate" in args
        assert "-no-color" in args
        assert "-json" in args

    def test_passes_timeout(self, tmp_path: Path) -> None:
        with patch("subprocess.run", return_value=_completed(stdout=self._valid_json())) as mock:
            validate(tmp_path, timeout=15)
        kwargs = mock.call_args[1] if mock.call_args[1] else {}
        assert kwargs.get("timeout") == 15

    def test_valid_hcl_returns_ok_true(self, tmp_path: Path) -> None:
        with patch("subprocess.run", return_value=_completed(stdout=self._valid_json())):
            result = validate(tmp_path)
        assert result.ok is True
        assert result.errors == []

    def test_invalid_hcl_returns_ok_false_with_errors(self, tmp_path: Path) -> None:
        out = self._invalid_json("Missing required argument", "The argument 'name' is required")
        with patch("subprocess.run", return_value=_completed(returncode=1, stdout=out)):
            result = validate(tmp_path)
        assert result.ok is False
        assert len(result.errors) == 1
        assert "Missing required argument" in result.errors[0]

    def test_timeout_raises_validate_error(self, tmp_path: Path) -> None:
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("terraform", 30)):
            with pytest.raises(TerraformValidateError, match="timed out"):
                validate(tmp_path)

    def test_binary_not_found_raises_validate_error(self, tmp_path: Path) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            with pytest.raises(TerraformValidateError, match="not found"):
                validate(tmp_path)

    def test_non_json_stdout_raises_validate_error(self, tmp_path: Path) -> None:
        with patch("subprocess.run", return_value=_completed(stdout="not json", returncode=1)):
            with pytest.raises(TerraformValidateError):
                validate(tmp_path)
