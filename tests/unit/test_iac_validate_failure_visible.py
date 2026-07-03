from __future__ import annotations

from unittest.mock import MagicMock, patch

from vibeops.models.iac import TerraformValidationResult
from vibeops.models.spec import ComputeSpec, DeploymentSpec, GpuType, NetworkSpec, StorageSpec
from vibeops.models.state import FlowStage, GraphState
from vibeops.terraform.runner import TerraformInitError


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
    return GraphState(
        user_prompt="deploy T4 VM",
        deployment_spec=_spec(),
        stage=FlowStage.IAC,
    )


def _run(init_side_effect: Exception | None, validate_return: object) -> GraphState:
    from langchain_core.runnables import RunnableConfig

    from vibeops.agents.iac import iac_agent

    llm = MagicMock()
    config: RunnableConfig = {"configurable": {"llm_client": llm, "gcp_context": None}}

    init_mock = MagicMock(side_effect=init_side_effect) if init_side_effect else MagicMock()

    with patch("vibeops.agents.iac.init", init_mock), patch(
        "vibeops.agents.iac.validate", return_value=validate_return
    ), patch(
        "vibeops.agents.iac.check_resource_allowlist",
        return_value=MagicMock(ok=True, violations=[]),
    ), patch(
        "vibeops.cost.infracost.run_infracost", return_value=None
    ):
        return iac_agent(_state(), config)


class TestIacValidateFailureVisible:
    def test_validate_errors_reach_state(self) -> None:
        result = _run(
            init_side_effect=None,
            validate_return=TerraformValidationResult(
                ok=False, errors=["Unknown resource type: google_magic_resource"]
            ),
        )
        assert result.validation_errors
        assert any("google_magic_resource" in e for e in result.validation_errors)

    def test_stage_still_awaiting_approval_on_failure(self) -> None:
        result = _run(
            init_side_effect=None,
            validate_return=TerraformValidationResult(
                ok=False, errors=["missing required argument"]
            ),
        )
        assert result.stage == FlowStage.AWAITING_APPROVAL

    def test_init_failure_captured_in_errors(self) -> None:
        result = _run(
            init_side_effect=TerraformInitError("terraform not found"),
            validate_return=TerraformValidationResult(ok=True),
        )
        assert result.validation_errors
        assert any("terraform not found" in e for e in result.validation_errors)
