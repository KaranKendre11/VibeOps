"""Live IaC integration tests.

Skipped unless VIBEOPS_LIVE_TESTS=1.  Require:
  - OPENAI_API_KEY env var
  - GOOGLE_APPLICATION_CREDENTIALS or GCP_SA_JSON env var + GCP_PROJECT_ID
  - `terraform` CLI in PATH
  - `infracost` CLI in PATH (optional; test degrades gracefully without it)
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from vibeops.models.spec import ComputeSpec, DeploymentSpec, GpuType, NetworkSpec, StorageSpec


def _spec() -> DeploymentSpec:
    return DeploymentSpec(
        compute=ComputeSpec(
            machine_type="n1-standard-4",
            zone="us-central1-a",
            gpu_type=GpuType.T4,
            gpu_count=1,
            preemptible=True,
        ),
        storage=StorageSpec(
            disk_size_gb=100,
            os_image_family="common-cu121",
            os_image_project="deeplearning-platform-release",
        ),
        network=NetworkSpec(network_name="default"),
        project_id=os.environ.get("GCP_PROJECT_ID", "placeholder-project"),
    )


@pytest.mark.live
def test_iac_live_no_fragment(tmp_path: Path) -> None:
    """Real LLM + terraform validate + infracost (or fallback)."""
    import openai

    from vibeops.core.llm import LLMClient
    from vibeops.agents.iac import _real_pipeline
    from vibeops.models.state import FlowStage, GraphState

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")

    llm = LLMClient(api_key=api_key)
    state = GraphState(user_prompt="deploy T4 VM", deployment_spec=_spec())
    result = _real_pipeline(state, llm, gcp_ctx=None)

    assert result.stage == FlowStage.AWAITING_APPROVAL
    assert set(result.terraform_files.keys()) == {"main.tf", "variables.tf", "outputs.tf"}


@pytest.mark.live
def test_iac_live_fragment(tmp_path: Path) -> None:
    """Real LLM generates a startup-script fragment using quality='high'."""
    import os

    from vibeops.core.llm import LLMClient
    from vibeops.agents.iac import _real_pipeline
    from vibeops.models.spec import ComputeSpec, DeploymentSpec, GpuType, NetworkSpec, StorageSpec
    from vibeops.models.state import FlowStage, GraphState

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")

    spec = _spec()
    spec = spec.model_copy(
        update={
            "compute": spec.compute.model_copy(
                update={"custom_startup_script_request": "install PyTorch and CUDA toolkit"}
            )
        }
    )
    llm = LLMClient(api_key=api_key)
    state = GraphState(user_prompt="deploy T4 with pytorch", deployment_spec=spec)
    result = _real_pipeline(state, llm, gcp_ctx=None)

    assert result.stage == FlowStage.AWAITING_APPROVAL
    assert result.terraform_files.get("main.tf")


@pytest.mark.live
def test_cost_real_pricing(tmp_path: Path) -> None:
    """Estimate for a known shape must be within 15% of GCP pricing calculator reference.

    Reference (2026-05-11, us-central1-a, on-demand):
      n1-standard-4: ~$0.19/hr
      nvidia-tesla-t4: ~$0.35/hr
      100 GB SSD: ~$17/mo = ~$0.023/hr
      Total hourly ≈ $0.563, monthly ≈ $411

    Drift > 15% from $411/mo is a bug worth investigating.
    """
    from vibeops.cost import estimate as cost_estimate_fn

    from vibeops.terraform.render import render_templates

    render_templates(_spec(), tmp_path)

    result = cost_estimate_fn(tmp_path, _spec(), ctx=None)
    reference_monthly = 411.0
    tolerance = 0.15

    assert result.monthly_usd > 0, "Estimate must be positive"
    drift = abs(result.monthly_usd - reference_monthly) / reference_monthly
    assert drift <= tolerance, (
        f"Cost estimate ${result.monthly_usd:.2f}/mo drifts {drift:.0%} from "
        f"reference ${reference_monthly:.2f}/mo (>{tolerance:.0%} threshold). "
        f"Source: {result.source}. Update pricing_constants.py if GCP prices changed."
    )
