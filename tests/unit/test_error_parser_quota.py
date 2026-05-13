from __future__ import annotations

from vibeops.terraform.error_parser import parse_error


_QUOTA_STDERR = """\
Error: googleapi: Error 403: Quota 'NVIDIA_T4_GPUS' exceeded. Limit: 1.0 in region us-central1.
  on main.tf line 12, in resource "google_compute_instance" "main":
  12: resource "google_compute_instance" "main" {
"""


def test_quota_exceeded_code() -> None:
    result = parse_error(_QUOTA_STDERR)
    assert result.code == "quota_exceeded"


def test_quota_exceeded_summary_mentions_quota() -> None:
    result = parse_error(_QUOTA_STDERR)
    assert "quota" in result.summary.lower() or "NVIDIA_T4_GPUS" in result.summary


def test_quota_exceeded_has_suggestion() -> None:
    result = parse_error(_QUOTA_STDERR)
    assert result.suggestion is not None
    assert "quota" in result.suggestion.lower() or "console" in result.suggestion.lower()


def test_quota_exceeded_raw_stderr_preserved() -> None:
    result = parse_error(_QUOTA_STDERR)
    assert result.raw_stderr == _QUOTA_STDERR
