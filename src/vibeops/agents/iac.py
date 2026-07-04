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
from vibeops.cost.pricing_constants import (
    GPU_HOURLY_USD,
    HOURS_PER_MONTH,
    N1_CPU_HOURLY_USD,
    N1_RAM_GB_HOURLY_USD,
    PD_SSD_GB_MONTHLY_USD,
    PREEMPTIBLE_DISCOUNT,
)
from vibeops.models.iac import CostEstimate, CostLineItem
from vibeops.models.spec import DeploymentSpec
from vibeops.models.state import FlowStage, GraphState
from vibeops.terraform.backend import configure_backend
from vibeops.terraform.render import render_templates
from vibeops.terraform.runner import (
    TerraformInitError,
    TerraformValidateError,
    init,
    validate,
    write_sa_credentials,
)

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
    In demo mode (no credentials) it renders real Terraform from the spec and attaches a
    representative offline cost, but never runs terraform.
    """
    llm: LLMClient | None = None
    gcp_ctx: Any | None = None
    demo_mode = False
    if config:
        configurable: dict[str, Any] = config.get("configurable") or {}
        llm = configurable.get("llm_client")
        gcp_ctx = configurable.get("gcp_context")
        demo_mode = bool(configurable.get("demo_mode"))

    # Demo mode ALWAYS uses the offline demo pipeline — never a real LLM/GCP call, even if a
    # client leaked into the session from a prior authenticated flow (Reconfigure -> demo).
    if demo_mode and state.deployment_spec is not None:
        return _demo_pipeline(state)

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
# Demo path (no credentials): real Terraform, representative cost, never applies
# ---------------------------------------------------------------------------


def _demo_pipeline(state: GraphState) -> GraphState:
    """Render real Terraform from the spec + attach a representative offline cost.

    Used only in demo mode. No terraform init/validate/apply and no GCP calls.
    """
    spec = state.deployment_spec
    assert spec is not None  # guarded by caller

    tmp_dir = Path(tempfile.mkdtemp(prefix="vibeops_demo_"))
    try:
        rendered = render_templates(spec, tmp_dir)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Demo render failed (%s); using static stub.", exc)
        return _stub_fallback(state)

    cost = _demo_cost_estimate(spec)
    msg = (
        f"Generated Terraform for {spec.compute.machine_type} + "
        f"{spec.compute.gpu_count}× {spec.compute.gpu_type.value}. "
        f"Representative cost: ${cost.monthly_usd:.2f}/mo (demo — deploy disabled)."
    )
    return state.model_copy(
        update={
            "terraform_files": rendered,
            "terraform_files_original": dict(rendered),
            "terraform_dir": str(tmp_dir),
            "cost_estimate": cost,
            "cost_estimate_usd": cost.monthly_usd,
            "cost_estimate_stale": False,
            "stage": FlowStage.AWAITING_APPROVAL,
            "chat_history": state.chat_history
            + [{"role": "agent", "agent": "iac", "content": msg}],
        }
    )


def _demo_cost_estimate(spec: DeploymentSpec) -> CostEstimate:
    """Fully-offline representative cost from pricing constants (no infracost/GCP)."""
    gpu_hourly = GPU_HOURLY_USD.get(spec.compute.gpu_type.value, 0.35) * spec.compute.gpu_count

    # Best-effort vCPU count from the machine-type suffix (e.g. n1-standard-4 -> 4).
    vcpus = 4
    suffix = spec.compute.machine_type.rsplit("-", 1)
    if len(suffix) == 2 and suffix[1].isdigit():
        vcpus = int(suffix[1])
    ram_gb = vcpus * 3.75  # n1-standard vCPU:RAM ratio
    machine_hourly = vcpus * N1_CPU_HOURLY_USD + ram_gb * N1_RAM_GB_HOURLY_USD

    disk_monthly = spec.storage.disk_size_gb * PD_SSD_GB_MONTHLY_USD
    disk_hourly = disk_monthly / HOURS_PER_MONTH

    if spec.compute.preemptible:
        gpu_hourly *= PREEMPTIBLE_DISCOUNT
        machine_hourly *= PREEMPTIBLE_DISCOUNT

    hourly = gpu_hourly + machine_hourly + disk_hourly
    return CostEstimate(
        hourly_usd=round(hourly, 4),
        monthly_usd=round(hourly * HOURS_PER_MONTH, 2),
        source="cloud_catalog",
        confidence="low",
        breakdown=[
            CostLineItem(
                description=f"{spec.compute.gpu_count}× {spec.compute.gpu_type.value}",
                hourly_usd=round(gpu_hourly, 4),
                monthly_usd=round(gpu_hourly * HOURS_PER_MONTH, 2),
            ),
            CostLineItem(
                description=f"{spec.compute.machine_type} (~{vcpus} vCPU)",
                hourly_usd=round(machine_hourly, 4),
                monthly_usd=round(machine_hourly * HOURS_PER_MONTH, 2),
            ),
            CostLineItem(
                description=f"{spec.storage.disk_size_gb} GB SSD disk",
                hourly_usd=round(disk_hourly, 4),
                monthly_usd=round(disk_monthly, 2),
            ),
        ],
        notes=["Representative estimate — demo mode (no live GCP pricing)."],
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

    # Step 4: configure remote state backend (issue #3), then terraform init + validate.
    # When VIBEOPS_TF_STATE_BUCKET is set, configure_backend writes backend.tf and returns the
    # GCS location; we also drop the service-account key so `init` can authenticate to the bucket
    # (and `destroy` later operates on the persisted state). When unset, backend is None -> local
    # ephemeral state and configure_backend logs a warning.
    backend = configure_backend(tmp_dir, project_id=spec.project_id)
    if backend is not None and gcp_ctx is not None:
        write_sa_credentials(tmp_dir, gcp_ctx.service_account_info)
    elif backend is not None:
        logger.warning(
            "Remote Terraform state backend is configured but no GCP credentials are "
            "available; `terraform init` may fail to authenticate to the state bucket."
        )

    validation_errors: list[str] = []
    try:
        init(tmp_dir, backend_config=backend.init_args() if backend else None)
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
            "terraform_state_prefix": backend.prefix if backend else None,
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
