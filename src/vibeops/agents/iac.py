from __future__ import annotations

import io
import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Optional

import hcl2
from langchain_core.runnables import RunnableConfig

from vibeops.agents.iac_prompts import FRAGMENT_RETRY_PROMPT, FRAGMENT_SYSTEM_PROMPT
from vibeops.core.llm import LLMClient
from vibeops.core.policy import check_resource_allowlist
from vibeops.models.iac import CostEstimate
from vibeops.models.state import FlowStage, GraphState
from vibeops.terraform.render import render_templates
from vibeops.terraform.runner import TerraformInitError, TerraformValidateError, init, validate

logger = logging.getLogger(__name__)

# Cost-cap from setup (USD / month).  Will be read from state/session in a future milestone.
_DEFAULT_COST_CAP_USD = 500.0

# Stub HCL — used when no LLM config is present (keeps M1/M2 tests passing).
_STUB_MAIN_TF = """\
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_compute_instance" "gpu_vm" {
  name         = var.instance_name
  machine_type = var.machine_type
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = "deeplearning-platform-release/tf2-latest-gpu"
      size  = var.disk_size_gb
    }
  }

  network_interface {
    network = var.network
    access_config {}
  }

  guest_accelerator {
    type  = var.gpu_type
    count = var.gpu_count
  }

  scheduling {
    on_host_maintenance = "TERMINATE"
    preemptible         = var.preemptible
  }
}
"""

_STUB_VARIABLES_TF = """\
variable "project_id"     { type = string }
variable "region"         { type = string  default = "us-central1" }
variable "zone"           { type = string  default = "us-central1-a" }
variable "instance_name"  { type = string  default = "vibeops-gpu-vm" }
variable "machine_type"   { type = string  default = "n1-standard-4" }
variable "disk_size_gb"   { type = number  default = 100 }
variable "gpu_type"       { type = string  default = "nvidia-tesla-t4" }
variable "gpu_count"      { type = number  default = 1 }
variable "network"        { type = string  default = "default" }
variable "preemptible"    { type = bool    default = false }
"""

_STUB_OUTPUTS_TF = """\
output "instance_name" {
  value = google_compute_instance.gpu_vm.name
}
output "external_ip" {
  value = google_compute_instance.gpu_vm.network_interface[0].access_config[0].nat_ip
}
"""


def iac_agent(state: GraphState, config: Optional[RunnableConfig] = None) -> GraphState:
    """Orchestrate render → validate → estimate → present.

    Falls back to a static stub when no LLMClient is in config (M1/M2 test compat).
    """
    llm: LLMClient | None = None
    gcp_ctx: Any | None = None
    if config:
        configurable: dict[str, Any] = config.get("configurable") or {}
        llm = configurable.get("llm_client")
        gcp_ctx = configurable.get("gcp_context")

    if llm is None or state.deployment_spec is None:
        return _stub_fallback(state)

    return _real_pipeline(state, llm, gcp_ctx)


# ---------------------------------------------------------------------------
# Stub path
# ---------------------------------------------------------------------------


def _stub_fallback(state: GraphState) -> GraphState:
    return state.model_copy(
        update={
            "terraform_files": {
                "main.tf": _STUB_MAIN_TF,
                "variables.tf": _STUB_VARIABLES_TF,
                "outputs.tf": _STUB_OUTPUTS_TF,
            },
            "terraform_files_original": {
                "main.tf": _STUB_MAIN_TF,
                "variables.tf": _STUB_VARIABLES_TF,
                "outputs.tf": _STUB_OUTPUTS_TF,
            },
            "cost_estimate_usd": 0.0,
            "stage": FlowStage.AWAITING_APPROVAL,
            "chat_history": state.chat_history
            + [
                {
                    "role": "agent",
                    "agent": "iac",
                    "content": (
                        "Generated Terraform for n1-standard-4 + T4. Cost estimate: $0.00 (stub)."
                    ),
                }
            ],
        }
    )


# ---------------------------------------------------------------------------
# Real pipeline
# ---------------------------------------------------------------------------


def _real_pipeline(state: GraphState, llm: LLMClient, gcp_ctx: Any | None) -> GraphState:
    spec = state.deployment_spec
    assert spec is not None  # guarded by caller

    # Step 1 + 2: optional LLM fragment generation
    fragment = ""
    if spec.compute.custom_startup_script_request:
        fragment = _generate_fragment(spec.compute.custom_startup_script_request, llm)

    # Step 3: render templates into a temp dir
    tmp_dir = Path(tempfile.mkdtemp(prefix="vibeops_iac_"))
    try:
        rendered = render_templates(spec, tmp_dir, fragment=fragment)
    except Exception as exc:
        logger.error("Template rendering failed: %s", exc)
        return _error_state(state, f"Template rendering failed: {exc}")

    tf_files_original = dict(rendered)

    # Step 4: terraform init + validate
    validation_errors: list[str] = []
    try:
        init(tmp_dir)
        result = validate(tmp_dir)
        if not result.ok:
            validation_errors = result.errors
    except (TerraformInitError, TerraformValidateError) as exc:
        validation_errors = [str(exc)]
    except Exception as exc:
        validation_errors = [f"Terraform runner error: {exc}"]

    # Step 5: allowlist check (only when validation passed — HCL must be parseable)
    if not validation_errors:
        main_tf_path = tmp_dir / "main.tf"
        allowlist_result = check_resource_allowlist(main_tf_path)
        if not allowlist_result.ok:
            bad = [v.resource_type for v in allowlist_result.violations]
            logger.error("Allowlist violation in generated Terraform: %s", bad)
            validation_errors = [
                f"Generated resource type not in allowlist: {', '.join(bad)}"
            ]

    # Step 6: cost estimation
    cost_estimate: CostEstimate | None = None
    try:
        from vibeops.cost import estimate as cost_estimate_fn

        cost_estimate = cost_estimate_fn(tmp_dir, spec, gcp_ctx)
    except Exception as exc:
        logger.warning("Cost estimation failed: %s", exc)

    # Step 7: cost-cap check
    cost_cap_exceeded = False
    if cost_estimate is not None:
        cost_cap_exceeded = cost_estimate.monthly_usd > _DEFAULT_COST_CAP_USD

    # Step 8: build chat message
    if validation_errors:
        msg = f"Terraform generated but validation failed: {validation_errors[0]}"
    elif cost_estimate is not None:
        msg = (
            f"Generated Terraform. Estimated cost: "
            f"${cost_estimate.hourly_usd:.4f}/hr "
            f"(${cost_estimate.monthly_usd:.2f}/mo, source={cost_estimate.source})."
        )
    else:
        msg = "Generated Terraform. Cost estimation unavailable."

    return state.model_copy(
        update={
            "terraform_files": rendered,
            "terraform_files_original": tf_files_original,
            "terraform_dir": str(tmp_dir),
            "cost_estimate": cost_estimate,
            "cost_estimate_usd": cost_estimate.monthly_usd if cost_estimate else None,
            "cost_cap_exceeded": cost_cap_exceeded,
            "cost_estimate_stale": False,
            "validation_errors": validation_errors,
            "stage": FlowStage.AWAITING_APPROVAL,
            "chat_history": state.chat_history
            + [{"role": "agent", "agent": "iac", "content": msg}],
        }
    )


def _error_state(state: GraphState, error: str) -> GraphState:
    return state.model_copy(
        update={
            "validation_errors": [error],
            "stage": FlowStage.AWAITING_APPROVAL,
            "chat_history": state.chat_history
            + [{"role": "agent", "agent": "iac", "content": f"IaC error: {error}"}],
        }
    )


# ---------------------------------------------------------------------------
# Fragment generation
# ---------------------------------------------------------------------------


def _generate_fragment(request: str, llm: LLMClient) -> str:
    """Call LLM with quality='high' to generate a HCL metadata block.

    Retries once on parse failure; falls back to empty string on double failure.
    """
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": FRAGMENT_SYSTEM_PROMPT},
        {"role": "user", "content": f"Startup script request: {request}"},
    ]
    fragment, err = _call_fragment_llm(messages, llm)
    if err is None:
        return fragment

    # Retry with error in prompt
    retry_messages = messages + [
        {"role": "assistant", "content": json.dumps({"metadata_block": fragment})},
        {"role": "user", "content": FRAGMENT_RETRY_PROMPT.format(error=err)},
    ]
    fragment, err2 = _call_fragment_llm(retry_messages, llm)
    if err2 is None:
        return fragment

    logger.warning(
        "Fragment generation failed twice (request=%r); using empty fragment. "
        "Last error: %s",
        request[:100],
        err2,
    )
    return ""


def _call_fragment_llm(
    messages: list[dict[str, Any]], llm: LLMClient
) -> tuple[str, str | None]:
    """Return (fragment_str, error_str). error_str is None on success."""
    try:
        result = llm.chat_completion(
            messages,
            response_format={"type": "json_object"},
            quality="high",
        )
        data: dict[str, Any] = json.loads(result.content)
        fragment: str = str(data.get("metadata_block") or "")
        if not fragment:
            return "", None
        # Validate the fragment parses as HCL by wrapping it in a dummy resource
        _validate_fragment_hcl(fragment)
        return fragment, None
    except json.JSONDecodeError as exc:
        return "", f"JSON parse error: {exc}"
    except Exception as exc:
        return "", str(exc)


def _validate_fragment_hcl(fragment: str) -> None:
    """Raise if fragment is not parseable when embedded in a resource block."""
    test_hcl = f'resource "google_compute_instance" "test" {{\n{fragment}\n}}\n'
    hcl2.load(io.StringIO(test_hcl))
