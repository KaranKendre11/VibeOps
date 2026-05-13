from __future__ import annotations

import re

from pydantic import BaseModel


class ParsedError(BaseModel):
    code: str
    summary: str
    suggestion: str | None
    raw_stderr: str


_PATTERNS: list[tuple[str, str, str, str | None]] = [
    # (code, regex, summary_template, suggestion)
    (
        "terraform_not_found",
        r"terraform binary not found|terraform.*not found in PATH|No such file.*terraform",
        "terraform CLI is not installed or not in PATH",
        "Install terraform: https://developer.hashicorp.com/terraform/install  "
        "(Windows: winget install Hashicorp.Terraform). Then restart the app.",
    ),
    (
        "registry_unreachable",
        r"could not connect to registry\.terraform\.io|failed to request discovery document|forcibly closed by the remote host|could not retrieve.*provider",
        "Cannot reach registry.terraform.io — network or firewall issue",
        "Check VPN/firewall: registry.terraform.io:443 must be reachable. "
        "Antivirus SSL inspection can also break this connection. "
        "Try running `terraform init` in a terminal to diagnose.",
    ),
    (
        "quota_exceeded",
        r"Quota '([^']+)' exceeded",
        "Insufficient quota: {match}",
        "Request a higher quota at https://console.cloud.google.com/iam-admin/quotas",
    ),
    (
        "permission_denied",
        r"Required '([^']+)' permission",
        "Missing IAM permission: {match}",
        "Grant the required IAM role to your service account in the GCP console.",
    ),
    (
        "api_not_enabled",
        r"API has not been used in project",
        "A required GCP API is not enabled",
        "Enable the API at https://console.cloud.google.com/apis/library",
    ),
    (
        "insufficient_resources",
        r"does not have enough resources available|resource type:compute",
        "Zone has insufficient capacity for this VM type",
        "Click 'Try a different zone' to re-run zone discovery excluding this zone.",
    ),
    (
        "zone_unavailable",
        r"does not exist in zone",
        "Requested zone is unavailable or does not exist",
        "Choose a different zone in the architecture picker.",
    ),
    (
        "resource_not_found",
        r"Error 400.*(?:was not found|invalid)",
        "Resource not found or invalid configuration",
        None,
    ),
]


def parse_error(stderr: str) -> ParsedError:
    for code, pattern, summary_template, suggestion in _PATTERNS:
        m = re.search(pattern, stderr, re.IGNORECASE)
        if m:
            groups = m.groups()
            match_str = groups[0] if groups else ""
            summary = summary_template.format(match=match_str)
            return ParsedError(code=code, summary=summary, suggestion=suggestion, raw_stderr=stderr)

    return ParsedError(
        code="unknown",
        summary="See full error below",
        suggestion=None,
        raw_stderr=stderr,
    )
