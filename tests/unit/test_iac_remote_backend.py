"""IaC agent wiring for the remote Terraform state backend (issue #3).

Verifies the real pipeline configures a GCS backend when ``VIBEOPS_TF_STATE_BUCKET`` is set:
``terraform init`` receives ``-backend-config`` flags, ``backend.tf`` is written, and the state
prefix is recorded on ``GraphState``. Also verifies the local-state path is unchanged when the
bucket is not configured. The terraform subprocess is fully mocked.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.runnables import RunnableConfig

from vibeops.agents.iac import iac_agent
from vibeops.models.iac import TerraformValidationResult
from vibeops.models.spec import ComputeSpec, DeploymentSpec, GpuType, NetworkSpec, StorageSpec
from vibeops.models.state import FlowStage, GraphState
from vibeops.terraform.backend import BACKEND_TF_FILENAME


def _spec() -> DeploymentSpec:
    return DeploymentSpec(
        compute=ComputeSpec(
            machine_type="n1-standard-4",
            zone="us-central1-a",
            gpu_type=GpuType.T4,
            gpu_count=1,
            preemptible=False,
        ),
        storage=StorageSpec(
            disk_size_gb=100,
            os_image_family="common-cu121",
            os_image_project="deeplearning-platform-release",
        ),
        network=NetworkSpec(network_name="default"),
        project_id="test-project",
    )


def _state() -> GraphState:
    return GraphState(user_prompt="deploy a T4 VM", deployment_spec=_spec(), stage=FlowStage.IAC)


def _run(config: RunnableConfig) -> tuple[GraphState, MagicMock]:
    with (
        patch("vibeops.agents.iac.init") as mock_init,
        patch("vibeops.agents.iac.validate", return_value=TerraformValidationResult(ok=True)),
        patch(
            "vibeops.agents.iac.check_resource_allowlist",
            return_value=MagicMock(ok=True, violations=[]),
        ),
        patch("vibeops.cost.infracost.run_infracost", return_value=None),
    ):
        result = iac_agent(_state(), config)
    return result, mock_init


def test_backend_configured_when_bucket_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIBEOPS_TF_STATE_BUCKET", "my-state-bucket")
    config: RunnableConfig = {"configurable": {"llm_client": MagicMock(), "gcp_context": None}}

    result, mock_init = _run(config)

    # terraform init received the -backend-config flags
    backend_config = mock_init.call_args.kwargs["backend_config"]
    assert backend_config is not None
    assert "-backend-config=bucket=my-state-bucket" in backend_config
    assert any(a.startswith("-backend-config=prefix=vibeops/test-project/") for a in backend_config)

    # state carries the unique prefix
    assert result.terraform_state_prefix is not None
    assert result.terraform_state_prefix.startswith("vibeops/test-project/")

    # backend.tf was written into the work dir
    assert result.terraform_dir is not None
    assert (Path(result.terraform_dir) / BACKEND_TF_FILENAME).is_file()


def test_local_state_path_unchanged_when_bucket_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIBEOPS_TF_STATE_BUCKET", raising=False)
    config: RunnableConfig = {"configurable": {"llm_client": MagicMock(), "gcp_context": None}}

    result, mock_init = _run(config)

    # init called with no backend config -> terraform uses local ephemeral state
    assert mock_init.call_args.kwargs["backend_config"] is None
    assert result.terraform_state_prefix is None
    assert result.terraform_dir is not None
    assert not (Path(result.terraform_dir) / BACKEND_TF_FILENAME).exists()
    assert result.stage == FlowStage.AWAITING_APPROVAL
