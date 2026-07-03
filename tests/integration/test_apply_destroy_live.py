"""Live apply+destroy integration test.

Skipped unless VIBEOPS_LIVE_TESTS=1 AND VIBEOPS_EXPENSIVE_TESTS=1.

Requires:
  - OPENAI_API_KEY (for IaC agent)
  - GOOGLE_APPLICATION_CREDENTIALS or GCP_SA_JSON + GCP_PROJECT_ID
  - `terraform` CLI in PATH (with google provider cached or network access)

WARNING: This test creates and destroys REAL GCP resources. Billing will occur.
It must be explicitly opted-in and human-reviewed before running.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from vibeops.models.spec import ComputeSpec, DeploymentSpec, GpuType, NetworkSpec, StorageSpec


def _preemptible_spec() -> DeploymentSpec:
    return DeploymentSpec(
        compute=ComputeSpec(
            machine_type="n1-standard-4",
            zone="us-central1-a",
            gpu_type=GpuType.T4,
            gpu_count=1,
            preemptible=True,
        ),
        storage=StorageSpec(
            disk_size_gb=50,
            os_image_family="common-cu121",
            os_image_project="deeplearning-platform-release",
        ),
        network=NetworkSpec(network_name="default"),
        project_id=os.environ.get("GCP_PROJECT_ID", ""),
    )


@pytest.mark.live
@pytest.mark.expensive
def test_apply_then_destroy_live(tmp_path: Path) -> None:
    """Creates a real preemptible T4 VM and immediately destroys it.

    Must be run manually with VIBEOPS_LIVE_TESTS=1 VIBEOPS_EXPENSIVE_TESTS=1.
    Requires a GCP project with T4 quota in us-central1-a and billing enabled.
    """
    if not os.environ.get("VIBEOPS_LIVE_TESTS"):
        pytest.skip("VIBEOPS_LIVE_TESTS not set")
    if not os.environ.get("VIBEOPS_EXPENSIVE_TESTS"):
        pytest.skip("VIBEOPS_EXPENSIVE_TESTS not set")

    api_key = os.environ.get("OPENAI_API_KEY")
    project_id = os.environ.get("GCP_PROJECT_ID")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")
    if not project_id:
        pytest.skip("GCP_PROJECT_ID not set")

    from vibeops.agents.deployment import deployment_agent, destroy_agent
    from vibeops.agents.iac import _real_pipeline
    from vibeops.core.llm import LLMClient
    from vibeops.models.deployment import DeploymentOutcome, DeploymentPhase
    from vibeops.models.state import FlowStage, GraphState
    from vibeops.terraform.runner import init

    llm = LLMClient(api_key=api_key)
    spec = _preemptible_spec()
    state = GraphState(user_prompt="deploy T4 VM for live test", deployment_spec=spec)

    # IaC: render + validate
    iac_result = _real_pipeline(state, llm, gcp_ctx=None)
    assert iac_result.terraform_dir is not None, "IaC pipeline must set terraform_dir"
    assert iac_result.stage == FlowStage.AWAITING_APPROVAL

    # Init terraform in the IaC-prepared dir
    work_dir = Path(iac_result.terraform_dir)
    init(work_dir)

    # Deployment: plan + apply (real GCP)
    deploy_state = iac_result.model_copy(update={"approved": True})

    deploy_result = deployment_agent(deploy_state)
    assert deploy_result.deployment_phase == DeploymentPhase.SUCCEEDED, (
        f"Apply failed: {deploy_result.deployment_error}\n"
        f"Logs: {chr(10).join(deploy_result.deployment_logs[-20:])}"
    )
    assert deploy_result.deployment_outcome == DeploymentOutcome.SUCCEEDED

    print(f"\nCreated resources: {[r.name for r in deploy_result.created_resources]}")
    print("Waiting 5s before destroy...")
    time.sleep(5)

    # Destroy: immediate teardown
    destroy_state = deploy_result.model_copy(update={"destroy_confirmed": True})
    destroy_result = destroy_agent(destroy_state)

    assert destroy_result.deployment_phase == DeploymentPhase.DESTROYED, (
        f"Destroy failed: {destroy_result.deployment_error}\n"
        f"Resources still running: {[r.name for r in destroy_result.created_resources]}\n"
        "MANUAL CLEANUP REQUIRED."
    )
    assert destroy_result.deployment_outcome == DeploymentOutcome.DESTROYED
    assert destroy_result.created_resources == [], (
        "Resources still in state after destroy — billing may continue. MANUAL CLEANUP REQUIRED."
    )

    print("Live apply+destroy test PASSED. No resources remain.")
