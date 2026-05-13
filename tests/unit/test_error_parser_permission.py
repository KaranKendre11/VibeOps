from __future__ import annotations

from vibeops.terraform.error_parser import parse_error


_PERMISSION_STDERR = """\
Error: Request had insufficient authentication scopes.
  Required 'compute.instances.create' permission for 'projects/my-project'.
  on main.tf line 5, in resource "google_compute_instance" "main":
"""


def test_permission_denied_code() -> None:
    result = parse_error(_PERMISSION_STDERR)
    assert result.code == "permission_denied"


def test_permission_denied_summary() -> None:
    result = parse_error(_PERMISSION_STDERR)
    assert "permission" in result.summary.lower() or "iam" in result.summary.lower()


def test_permission_denied_has_suggestion() -> None:
    result = parse_error(_PERMISSION_STDERR)
    assert result.suggestion is not None


def test_permission_denied_raw_stderr_preserved() -> None:
    result = parse_error(_PERMISSION_STDERR)
    assert result.raw_stderr == _PERMISSION_STDERR
