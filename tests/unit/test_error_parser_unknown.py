from __future__ import annotations

from vibeops.terraform.error_parser import parse_error

_UNKNOWN_STDERR = """\
Error: some totally unrecognised terraform error that doesn't match any pattern.
Details: xyzzy blorp quux.
"""

_ZONE_STDERR = """\
Error: Error creating instance: googleapi: Error 400: Invalid value for field \
'resource.zone': 'us-central1-z'. Zone does not exist in zone 'us-central1-z', invalid
"""

_RESOURCE_NOT_FOUND_STDERR = """\
Error: Error 400: The resource 'projects/proj/zones/us-central1-a/diskTypes/pd-ssd2' was not found
"""


def test_unknown_error_code() -> None:
    result = parse_error(_UNKNOWN_STDERR)
    assert result.code == "unknown"


def test_unknown_error_suggestion_is_none() -> None:
    result = parse_error(_UNKNOWN_STDERR)
    assert result.suggestion is None


def test_unknown_error_summary_fallback() -> None:
    result = parse_error(_UNKNOWN_STDERR)
    assert "below" in result.summary.lower() or "error" in result.summary.lower()


def test_unknown_does_not_raise() -> None:
    parse_error("")
    parse_error("   ")
    parse_error("no error here at all")


def test_zone_not_exist_code() -> None:
    result = parse_error(_ZONE_STDERR)
    assert result.code == "zone_unavailable"


def test_resource_not_found_code() -> None:
    result = parse_error(_RESOURCE_NOT_FOUND_STDERR)
    assert result.code == "resource_not_found"
