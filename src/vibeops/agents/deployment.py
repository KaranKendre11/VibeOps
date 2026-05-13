from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from langchain_core.runnables import RunnableConfig

from vibeops.models.deployment import DeploymentOutcome, DeploymentPhase
from vibeops.models.spec import DeploymentSpec
from vibeops.models.state import FlowStage, GraphState
from vibeops.terraform import runner
from vibeops.terraform.error_parser import parse_error
from vibeops.terraform.errors import TerraformApplyError, TerraformDestroyError, TerraformPlanError


def _write_tfvars(work_dir: Path, spec: DeploymentSpec) -> None:
    """Write vibeops.auto.tfvars so terraform plan/apply receive required variable values."""
    (work_dir / "vibeops.auto.tfvars").write_text(
        f'project_id = "{spec.project_id}"\n',
        encoding="utf-8",
    )


def _write_credentials(work_dir: Path, gcp_ctx: Any) -> None:
    """Write sa_credentials.json so GOOGLE_APPLICATION_CREDENTIALS is set by _tf_env."""
    (work_dir / "sa_credentials.json").write_text(
        json.dumps(gcp_ctx.service_account_info),
        encoding="utf-8",
    )


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

    gcp_ctx: Any = (config.get("configurable") or {}).get("gcp_context") if config else None

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

    try:
        result = runner.apply(work_dir, on_log=apply_logs.append)
    except TerraformApplyError as exc:
        outcome = (
            DeploymentOutcome.PARTIAL_FAIL if exc.partial_state else DeploymentOutcome.FULL_FAIL
        )
        parsed = parse_error(exc.stderr)
        return state.model_copy(
            update={
                "deployment_phase": DeploymentPhase.FAILED,
                "deployment_outcome": outcome,
                "deployment_error": parsed.summary,
                "deployment_logs": base_logs + apply_logs + exc.stderr.splitlines(),
                "created_resources": exc.created_resources,
                "retry_requested": False,
            }
        )

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

    gcp_ctx: Any = (config.get("configurable") or {}).get("gcp_context") if config else None

    if state.deployment_spec is not None:
        _write_tfvars(work_dir, state.deployment_spec)
    if gcp_ctx is not None:
        _write_credentials(work_dir, gcp_ctx)

    destroy_logs: list[str] = []

    try:
        result = runner.destroy(work_dir, on_log=destroy_logs.append)
    except TerraformDestroyError as exc:
        parsed = parse_error(exc.stderr)
        return state.model_copy(
            update={
                "deployment_phase": DeploymentPhase.FAILED,
                "deployment_outcome": DeploymentOutcome.DESTROY_FAILED,
                "deployment_error": parsed.summary,
                "deployment_logs": list(state.deployment_logs) + destroy_logs + exc.stderr.splitlines(),
                "created_resources": exc.created_resources,
            }
        )

    return state.model_copy(
        update={
            "deployment_phase": DeploymentPhase.DESTROYED,
            "deployment_outcome": DeploymentOutcome.DESTROYED,
            "deployment_logs": list(state.deployment_logs) + destroy_logs + result.full_log.splitlines(),
            "created_resources": [],
            "destroy_confirmed": False,   # re-close gate after destroy completes
            "destroy_requested": False,
        }
    )
