"""Unit tests for remote Terraform state backend wiring (issue #3).

Covers the backend-config generation (``vibeops.terraform.backend``), the ``terraform init``
wiring in the runner, and the IaC agent hooking the two together. The terraform subprocess is
always mocked — no real GCS bucket or terraform binary is required.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibeops.config import AppConfig
from vibeops.terraform.backend import (
    BACKEND_TF_FILENAME,
    BackendConfig,
    configure_backend,
    make_state_prefix,
)
from vibeops.terraform.runner import init


class TestMakeStatePrefix:
    def test_includes_base_and_project(self) -> None:
        prefix = make_state_prefix("vibeops", project_id="my-proj", unique="abc123")
        assert prefix == "vibeops/my-proj/abc123"

    def test_omits_project_when_absent(self) -> None:
        assert make_state_prefix("vibeops", unique="abc123") == "vibeops/abc123"

    def test_generated_unique_is_hex_and_differs(self) -> None:
        a = make_state_prefix("vibeops", project_id="p")
        b = make_state_prefix("vibeops", project_id="p")
        assert a != b  # uuid4 per call
        assert a.startswith("vibeops/p/")

    def test_sanitizes_unsafe_characters(self) -> None:
        prefix = make_state_prefix("Vibe Ops", project_id="My Proj!", unique="a/b c")
        # lowercased; spaces and specials collapse to '-' (slashes are not path separators here)
        assert prefix == "vibe-ops/my-proj/a-b-c"


class TestBackendConfig:
    def test_init_args_format(self) -> None:
        cfg = BackendConfig(bucket="my-bucket", prefix="vibeops/p/abc")
        assert cfg.init_args() == [
            "-backend-config=bucket=my-bucket",
            "-backend-config=prefix=vibeops/p/abc",
        ]

    def test_location(self) -> None:
        cfg = BackendConfig(bucket="my-bucket", prefix="vibeops/p/abc")
        assert cfg.location == "gs://my-bucket/vibeops/p/abc"


class TestConfigureBackend:
    def test_writes_backend_tf_and_returns_config_when_bucket_set(self, tmp_path: Path) -> None:
        cfg = AppConfig(tf_state_bucket="state-bucket", tf_state_prefix="vibeops")
        backend = configure_backend(tmp_path, project_id="my-proj", config=cfg)

        assert backend is not None
        assert backend.bucket == "state-bucket"
        assert backend.prefix.startswith("vibeops/my-proj/")

        backend_file = tmp_path / BACKEND_TF_FILENAME
        assert backend_file.is_file()
        content = backend_file.read_text(encoding="utf-8")
        assert 'backend "gcs"' in content

    def test_reuses_explicit_prefix(self, tmp_path: Path) -> None:
        cfg = AppConfig(tf_state_bucket="state-bucket")
        backend = configure_backend(tmp_path, prefix="vibeops/reattach/xyz", config=cfg)
        assert backend is not None
        assert backend.prefix == "vibeops/reattach/xyz"

    def test_returns_none_and_writes_nothing_when_bucket_unset(self, tmp_path: Path) -> None:
        cfg = AppConfig(tf_state_bucket=None)
        backend = configure_backend(tmp_path, config=cfg)
        assert backend is None
        assert not (tmp_path / BACKEND_TF_FILENAME).exists()

    def test_logs_warning_when_bucket_unset(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        cfg = AppConfig(tf_state_bucket=None)
        with caplog.at_level(logging.WARNING, logger="vibeops.terraform.backend"):
            configure_backend(tmp_path, config=cfg)
        assert any("VIBEOPS_TF_STATE_BUCKET" in r.message for r in caplog.records)

    def test_reads_bucket_from_environment(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("VIBEOPS_TF_STATE_BUCKET", "env-bucket")
        backend = configure_backend(tmp_path, project_id="p")  # no explicit config -> AppConfig()
        assert backend is not None
        assert backend.bucket == "env-bucket"


def _completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


class TestInitBackendWiring:
    def test_backend_config_flags_passed_to_terraform_init(self, tmp_path: Path) -> None:
        backend = BackendConfig(bucket="b", prefix="vibeops/p/abc")
        with (
            patch("vibeops.terraform.runner._find_terraform", return_value="terraform"),
            patch("subprocess.run", return_value=_completed()) as mock_run,
        ):
            init(tmp_path, backend_config=backend.init_args())
        args = mock_run.call_args[0][0]
        assert "-backend-config=bucket=b" in args
        assert "-backend-config=prefix=vibeops/p/abc" in args

    def test_no_backend_config_flags_by_default(self, tmp_path: Path) -> None:
        with (
            patch("vibeops.terraform.runner._find_terraform", return_value="terraform"),
            patch("subprocess.run", return_value=_completed()) as mock_run,
        ):
            init(tmp_path)
        args = mock_run.call_args[0][0]
        assert not any(str(a).startswith("-backend-config") for a in args)
