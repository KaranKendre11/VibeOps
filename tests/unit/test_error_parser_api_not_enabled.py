from __future__ import annotations

from vibeops.terraform.error_parser import parse_error

_API_STDERR = """\
Error: Error when reading or editing Instance: googleapi: Error 403: \
API has not been used in project 123456789 before or it is disabled. \
Enable it at https://console.developers.google.com/apis/api/compute.googleapis.com/overview
"""


def test_api_not_enabled_code() -> None:
    result = parse_error(_API_STDERR)
    assert result.code == "api_not_enabled"


def test_api_not_enabled_summary() -> None:
    result = parse_error(_API_STDERR)
    assert "api" in result.summary.lower() or "enabled" in result.summary.lower()


def test_api_not_enabled_has_suggestion() -> None:
    result = parse_error(_API_STDERR)
    assert result.suggestion is not None
    assert "enable" in result.suggestion.lower() or "console" in result.suggestion.lower()


def test_api_not_enabled_raw_stderr_preserved() -> None:
    result = parse_error(_API_STDERR)
    assert result.raw_stderr == _API_STDERR
