from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional

from langchain_core.runnables import RunnableConfig

from vibeops.core.gcp_context import GcpContext
from vibeops.core.policy import check_dir_allowlist
from vibeops.models.deployment import DeploymentOutcome, DeploymentPhase, StateResource
from vibeops.models.spec import DeploymentSpec
from vibeops.models.state import FlowStage, GraphState
from vibeops.terraform import runner
from vibeops.terraform.error_parser import parse_error
from vibeops.terraform.errors import TerraformApplyError, TerraformDestroyError, TerraformPlanError
from vibeops.tools.compute import check_machine_availability

# Parsed-error codes (see terraform.error_parser) that mean the chosen zone can't serve the VM
# right now. When terraform apply fails with one of these we record the zone in excluded_zones so
# a re-discovery skips it.
_ZONE_LEVEL_ERROR_CODES = frozenset({"insufficient_resources", "zone_unavailable"})


def _make_on_log(
    local: list[str], sink: Callable[[str], None] | None
) -> Callable[[str], None]:
    """Return an on_log callback that appends to ``local`` and also forwards to ``sink`` (if given).

    Lets the API stream live terraform output by passing a queue-push ``on_log`` via graph config,
    while preserving in-state log accumulation. Falls back to plain append when ``sink`` is None.
    """
    if sink is None:
        return local.append

    def _log(line: str) -> None:
        local.append(line)
        sink(line)

    return _log


_DEMO_INSTANCE_NAME = "vibeops-demo-gpu-vm"


def _demo_apply(state: GraphState, sink: Callable[[str], None] | None) -> GraphState:
    """Simulate a successful terraform apply for demo mode — no real cloud, deterministic.

    Streams canned log lines (so the live-log UI works) and records a fake instance so the
    end-to-end demo walkthrough (deploy → VM inventory) is complete without credentials.
    """
    spec = state.deployment_spec
    zone = spec.compute.zone if spec else "us-central1-a"
    lines = [
        "Initializing the backend...",
        "Terraform will perform the following actions:",
        "  + google_compute_instance.gpu_vm will be created",
        "google_compute_instance.gpu_vm: Creating...",
        f"google_compute_instance.gpu_vm: Creation complete after 42s [name={_DEMO_INSTANCE_NAME}]",
        "Apply complete! Resources: 1 added, 0 changed, 0 destroyed.",
    ]
    if sink is not None:
        for line in lines:
            sink(line)
    return state.model_copy(
        update={
            "deployment_phase": DeploymentPhase.SUCCEEDED,
            "deployment_outcome": DeploymentOutcome.SUCCEEDED,
            "deployment_logs": list(state.deployment_logs) + lines,
            "created_resources": [
                StateResource(type="google_compute_instance", name=_DEMO_INSTANCE_NAME, zone=zone)
            ],
            "deployment_error": None,
            "retry_requested": False,
            "stage": FlowStage.DEPLOYMENT,
        }
    )


def _demo_destroy(state: GraphState, sink: Callable[[str], None] | None) -> GraphState:
    """Simulate a successful terraform destroy for demo mode."""
    lines = [
        "google_compute_instance.gpu_vm: Destroying...",
        "google_compute_instance.gpu_vm: Destruction complete after 11s",
        "Destroy complete! Resources: 1 destroyed.",
    ]
    if sink is not None:
        for line in lines:
            sink(line)
    return state.model_copy(
        update={
            "deployment_phase": DeploymentPhase.DESTROYED,
            "deployment_outcome": DeploymentOutcome.DESTROYED,
            "deployment_logs": list(state.deployment_logs) + lines,
            "created_resources": [],
            "destroy_confirmed": False,
            "destroy_requested": False,
        }
    )


def _write_tfvars(work_dir: Path, spec: DeploymentSpec) -> None:
    """Write vibeops.auto.tfvars so terraform plan/apply receive required variable values."""
    (work_dir / "vibeops.auto.tfvars").write_text(
        f'project_id = "{spec.project_id}"\n',
        encoding="utf-8",
    )


def _write_credentials(work_dir: Path, gcp_ctx: Any) -> None:
    """Write sa_credentials.json so GOOGLE_APPLICATION_CREDENTIALS is set by _tf_env."""
    runner.write_sa_credentials(work_dir, gcp_ctx.service_account_info)


def deployment_agent(
    state: GraphState,
    config: Optional[RunnableConfig] = None,
) -> GraphState:
    """Orchestrate terraform plan → apply.

    No LLM access — pure subprocess orchestration.
    Handles retry: when retry_requested=True, resets logs and re-runs.
    """
    work_dir = Path(state.terraform_dir) if state.terraform_dir else None
    if work_dir is None:
        return state.model_copy(
            update={
                "deployment_phase": DeploymentPhase.FAILED,
                "deployment_outcome": DeploymentOutcome.PLAN_FAILED,
                "deployment_error": "No terraform directory available.",
            }
        )

    configurable = (config.get("configurable") or {}) if config else {}
    gcp_ctx: Any = configurable.get("gcp_context")

    # Demo mode never touches a real cloud — it SIMULATES a successful apply (streamed canned
    # logs + a fake instance) so the end-to-end walkthrough works without credentials.
    if configurable.get("demo_mode"):
        return _demo_apply(state, configurable.get("on_log"))

    # Fail closed: re-run the resource allowlist over the on-disk *.tf files immediately before
    # deploying. The review-time check can be bypassed if the files are tampered with afterwards,
    # so this is the last line of defence — a disallowed (or unparseable) resource blocks apply.
    try:
        allowlist_result = check_dir_allowlist(work_dir)
    except Exception as exc:
        return state.model_copy(
            update={
                "deployment_phase": DeploymentPhase.FAILED,
                "deployment_outcome": DeploymentOutcome.PLAN_FAILED,
                "deployment_error": f"Deploy blocked: could not verify resource allowlist ({exc}).",
                "retry_requested": False,
            }
        )
    if not allowlist_result.ok:
        bad = sorted({v.resource_type for v in allowlist_result.violations})
        return state.model_copy(
            update={
                "deployment_phase": DeploymentPhase.FAILED,
                "deployment_outcome": DeploymentOutcome.PLAN_FAILED,
                "deployment_error": (
                    f"Deploy blocked: resource type(s) not in allowlist: {', '.join(bad)}."
                ),
                "retry_requested": False,
            }
        )

    # Re-validate that the selected machine type + GPU are still available and within quota in
    # the chosen zone. Capacity and quota can shift between architecture selection and deploy, so
    # we catch it here with an actionable message instead of surfacing a raw ``terraform apply``
    # failure. Best-effort: an inconclusive check (e.g. the availability API can't be reached)
    # must not block a valid deploy — terraform stays the backstop — so we only fail on a
    # definitive "unavailable" verdict, and record the zone so a re-discovery can skip it.
    # The live probe needs a real GcpContext (credentials + session cache); guard on the concrete
    # type so callers that inject a stand-in context (tests, or any future non-GCP context) skip
    # the network probe instead of erroring against it.
    spec = state.deployment_spec
    if spec is not None and type(gcp_ctx) is GcpContext:
        compute_spec = spec.compute
        try:
            availability = check_machine_availability(
                gcp_ctx,
                machine_type=compute_spec.machine_type,
                zone=compute_spec.zone,
                gpu_type=compute_spec.gpu_type.value,
                gpu_count=compute_spec.gpu_count,
            )
        except Exception:  # noqa: BLE001 — an inconclusive check must not block a valid deploy
            availability = None
        if availability is not None and not availability.available:
            zone = compute_spec.zone
            excluded = list(state.excluded_zones)
            if zone not in excluded:
                excluded.append(zone)
            return state.model_copy(
                update={
                    "deployment_phase": DeploymentPhase.FAILED,
                    "deployment_outcome": DeploymentOutcome.PLAN_FAILED,
                    "deployment_error": (
                        f"Deploy blocked: {compute_spec.machine_type} in {zone} is no longer "
                        f"deployable ({availability.reason}). Zone {zone} has been excluded — "
                        "go back to architecture to pick another candidate, or retry to "
                        "re-discover available zones."
                    ),
                    "excluded_zones": excluded,
                    "retry_requested": False,
                }
            )

    # Reset on retry
    base_logs: list[str] = [] if state.retry_requested else list(state.deployment_logs)

    if state.deployment_spec is not None:
        _write_tfvars(work_dir, state.deployment_spec)
    if gcp_ctx is not None:
        _write_credentials(work_dir, gcp_ctx)

    # Phase: PLANNING
    try:
        runner.plan(work_dir)
    except TerraformPlanError as exc:
        parsed = parse_error(exc.stderr)
        return state.model_copy(
            update={
                "deployment_phase": DeploymentPhase.FAILED,
                "deployment_outcome": DeploymentOutcome.PLAN_FAILED,
                "deployment_error": parsed.summary,
                "deployment_logs": base_logs + [exc.stderr],
                "retry_requested": False,
            }
        )

    # Phase: APPLYING
    apply_logs: list[str] = []
    on_log = _make_on_log(apply_logs, configurable.get("on_log"))

    try:
        result = runner.apply(work_dir, on_log=on_log)
    except TerraformApplyError as exc:
        outcome = (
            DeploymentOutcome.PARTIAL_FAIL if exc.partial_state else DeploymentOutcome.FULL_FAIL
        )
        parsed = parse_error(exc.stderr)
        apply_update: dict[str, Any] = {
            "deployment_phase": DeploymentPhase.FAILED,
            "deployment_outcome": outcome,
            "deployment_error": parsed.summary,
            "deployment_logs": base_logs + apply_logs + exc.stderr.splitlines(),
            "created_resources": exc.created_resources,
            "retry_requested": False,
        }
        # A zone-level capacity/availability failure means the chosen zone can't serve this VM
        # right now — record it so a re-discovery skips it (mirrors the pre-apply availability
        # gate, and matches the parser's "re-run zone discovery excluding this zone" hint).
        if parsed.code in _ZONE_LEVEL_ERROR_CODES and state.deployment_spec is not None:
            failed_zone = state.deployment_spec.compute.zone
            if failed_zone not in state.excluded_zones:
                apply_update["excluded_zones"] = list(state.excluded_zones) + [failed_zone]
        return state.model_copy(update=apply_update)

    created = runner.parse_state_resources(work_dir)
    all_logs = base_logs + apply_logs + result.full_log.splitlines()

    return state.model_copy(
        update={
            "deployment_phase": DeploymentPhase.SUCCEEDED,
            "deployment_outcome": DeploymentOutcome.SUCCEEDED,
            "deployment_logs": all_logs,
            "created_resources": created,
            "deployment_error": None,
            "retry_requested": False,
            "stage": FlowStage.DEPLOYMENT,
        }
    )


def destroy_agent(
    state: GraphState,
    config: Optional[RunnableConfig] = None,
) -> GraphState:
    """Run terraform destroy.

    No LLM access — pure subprocess orchestration.
    Should only be called when state.destroy_confirmed is True (enforced by graph edge).
    """
    work_dir = Path(state.terraform_dir) if state.terraform_dir else None
    if work_dir is None:
        return state.model_copy(
            update={
                "deployment_phase": DeploymentPhase.FAILED,
                "deployment_outcome": DeploymentOutcome.DESTROY_FAILED,
                "deployment_error": "No terraform directory available.",
            }
        )

    configurable = (config.get("configurable") or {}) if config else {}
    gcp_ctx: Any = configurable.get("gcp_context")

    # Demo mode: simulate a successful teardown (no real cloud).
    if configurable.get("demo_mode"):
        return _demo_destroy(state, configurable.get("on_log"))

    if state.deployment_spec is not None:
        _write_tfvars(work_dir, state.deployment_spec)
    if gcp_ctx is not None:
        _write_credentials(work_dir, gcp_ctx)

    destroy_logs: list[str] = []
    on_log = _make_on_log(destroy_logs, configurable.get("on_log"))

    try:
        result = runner.destroy(work_dir, on_log=on_log)
    except TerraformDestroyError as exc:
        parsed = parse_error(exc.stderr)
        return state.model_copy(
            update={
                "deployment_phase": DeploymentPhase.FAILED,
                "deployment_outcome": DeploymentOutcome.DESTROY_FAILED,
                "deployment_error": parsed.summary,
                "deployment_logs": (
                    list(state.deployment_logs) + destroy_logs + exc.stderr.splitlines()
                ),
                "created_resources": exc.created_resources,
            }
        )

    return state.model_copy(
        update={
            "deployment_phase": DeploymentPhase.DESTROYED,
            "deployment_outcome": DeploymentOutcome.DESTROYED,
            "deployment_logs": (
                list(state.deployment_logs) + destroy_logs + result.full_log.splitlines()
            ),
            "created_resources": [],
            "destroy_confirmed": False,   # re-close gate after destroy completes
            "destroy_requested": False,
        }
    )
