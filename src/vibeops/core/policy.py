from __future__ import annotations

from pathlib import Path
from typing import Any

import hcl2

from vibeops.models.iac import AllowlistResult, Violation

ALLOWED_RESOURCE_TYPES: frozenset[str] = frozenset(
    {
        "google_compute_instance",
        "google_compute_disk",
        "google_compute_attached_disk",
        "google_compute_firewall",
    }
)

ALLOWED_DATA_SOURCES: frozenset[str] = frozenset(
    {
        "google_compute_network",
        "google_compute_subnetwork",
        "google_compute_image",
    }
)

# The only Terraform files a user is allowed to edit on the review screen. These are exactly the
# files the IaC agent generates (see vibeops.terraform.render). Treated as a strict whitelist so an
# edit can never create a new file, escape the work dir, or smuggle in a non-.tf payload.
EDITABLE_FILENAMES: frozenset[str] = frozenset({"main.tf", "variables.tf", "outputs.tf"})


def is_safe_edit_filename(filename: str) -> bool:
    r"""Return True only for a known, plain, editable Terraform file.

    Whitelist-based on purpose: because membership in ``EDITABLE_FILENAMES`` is required, this
    inherently rejects path separators (``/`` or ``\``), ``..`` traversal, absolute paths and any
    non-``.tf`` name — none of those can ever be a member.
    """
    return filename in EDITABLE_FILENAMES


def _strip_quotes(s: str) -> str:
    """hcl2 wraps identifier strings in double-quotes; strip them."""
    return s.strip('"')


def check_resource_allowlist(hcl_path: Path) -> AllowlistResult:
    """Parse HCL at the path and return any resource-type violations.

    Data-source blocks are checked against ALLOWED_DATA_SOURCES.
    Resource blocks are checked against ALLOWED_RESOURCE_TYPES.
    Line numbers are best-effort (0 when unavailable).
    """
    text = hcl_path.read_text(encoding="utf-8").strip()
    if not text:
        return AllowlistResult(ok=True)

    with hcl_path.open(encoding="utf-8") as fh:
        parsed: dict[str, Any] = hcl2.load(fh)

    violations: list[Violation] = []

    # python-hcl2 returns resource/data as lists of single-key dicts
    for block in parsed.get("resource", []):
        for raw_type in block:
            resource_type = _strip_quotes(raw_type)
            if resource_type not in ALLOWED_RESOURCE_TYPES:
                violations.append(Violation(resource_type=resource_type, line_number=0))

    for block in parsed.get("data", []):
        for raw_type in block:
            data_type = _strip_quotes(raw_type)
            if data_type not in ALLOWED_DATA_SOURCES:
                violations.append(Violation(resource_type=data_type, line_number=0))

    return AllowlistResult(ok=len(violations) == 0, violations=violations)


def check_dir_allowlist(tf_dir: Path) -> AllowlistResult:
    """Run the allowlist over EVERY ``*.tf`` file in ``tf_dir`` and aggregate violations.

    A single-file check on ``main.tf`` is not enough: a disallowed resource can hide in
    ``outputs.tf`` (or any other ``*.tf``). This validates the whole working directory so the
    allowlist can't be bypassed by putting the resource in another file. Files are visited in
    sorted order for deterministic output. Non-``.tf`` files (``*.tfvars``, credentials, state,
    the provider lock) are ignored. Unparseable HCL propagates as an exception — callers that must
    fail closed should treat that as unsafe.
    """
    violations: list[Violation] = []
    for path in sorted(tf_dir.glob("*.tf")):
        violations.extend(check_resource_allowlist(path).violations)
    return AllowlistResult(ok=len(violations) == 0, violations=violations)
