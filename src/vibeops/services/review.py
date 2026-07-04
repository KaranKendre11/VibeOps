"""UI-agnostic review-screen logic: validate/allowlist Terraform edits and re-estimate cost.

Extracted from ``vibeops.ui.review`` so the FastAPI layer and unit tests can use it without
Streamlit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vibeops.core.gcp_context import GcpContext
from vibeops.core.policy import (
    ALLOWED_RESOURCE_TYPES,
    EDITABLE_FILENAMES,
    check_dir_allowlist,
    is_safe_edit_filename,
)
from vibeops.cost import estimate as cost_estimate_fn
from vibeops.models.state import GraphState
from vibeops.terraform.runner import TerraformValidateError, validate


def apply_user_edit(
    state: GraphState,
    filename: str,
    new_content: str,
) -> tuple[GraphState, str | None]:
    """Validate + allowlist-check a user's HCL edit; return (updated_state, error).

    On any failure the original file content is restored on disk and an error string is returned.
    """
    if state.terraform_dir is None:
        return state, "No Terraform working directory — cannot validate edit."

    # Reject anything but the known editable files BEFORE touching disk. Blocks path traversal
    # (e.g. ``../../etc/passwd``), writing outside the work dir, and creating new/non-.tf files.
    if not is_safe_edit_filename(filename):
        allowed_files = ", ".join(sorted(EDITABLE_FILENAMES))
        return state, f"Illegal filename '{filename}'. Editable files: {allowed_files}."

    tf_dir = Path(state.terraform_dir)
    tf_file = tf_dir / filename
    original_content = state.terraform_files.get(filename, "")

    tf_file.write_text(new_content, encoding="utf-8")

    try:
        result = validate(tf_dir)
    except (TerraformValidateError, Exception) as exc:
        tf_file.write_text(original_content, encoding="utf-8")
        return state, f"Validation error: {exc}"

    if not result.ok:
        tf_file.write_text(original_content, encoding="utf-8")
        return state, f"Validation failed: {'; '.join(result.errors)}"

    # Allowlist the ENTIRE work dir, not just main.tf — a disallowed resource added via outputs.tf
    # (or any other *.tf) must not slip through.
    allowlist_result = check_dir_allowlist(tf_dir)
    if not allowlist_result.ok:
        bad = [v.resource_type for v in allowlist_result.violations]
        allowed = sorted(ALLOWED_RESOURCE_TYPES)
        tf_file.write_text(original_content, encoding="utf-8")
        return state, (
            f"Resource type not in allowlist: {', '.join(bad)}. Allowed: {', '.join(allowed)}."
        )

    new_files = {**state.terraform_files, filename: new_content}
    return (
        state.model_copy(update={"terraform_files": new_files, "cost_estimate_stale": True}),
        None,
    )


def reestimate_cost(
    state: GraphState, gcp_ctx: GcpContext | None, cap: float
) -> dict[str, Any] | None:
    """Re-run cost estimation for the current terraform dir + spec.

    Returns a ``GraphState``-update dict, or ``None`` when prerequisites are missing. Raises on
    estimation failure so callers can decide how to surface it.
    """
    if state.terraform_dir is None or state.deployment_spec is None:
        return None
    new_estimate = cost_estimate_fn(Path(state.terraform_dir), state.deployment_spec, gcp_ctx)
    return {
        "cost_estimate": new_estimate.model_dump(),
        "cost_estimate_stale": False,
        "cost_cap_exceeded": new_estimate.monthly_usd > cap,
    }
