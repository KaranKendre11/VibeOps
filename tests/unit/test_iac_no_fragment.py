from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from vibeops.models.spec import ComputeSpec, DeploymentSpec, GpuType, NetworkSpec, StorageSpec
from vibeops.models.state import FlowStage, GraphState


def _spec(custom_startup: str | None = None) -> DeploymentSpec:
    return DeploymentSpec(
        compute=ComputeSpec(
            machine_type="n1-standard-4",
            zone="us-central1-a",
            gpu_type=GpuType.T4,
            gpu_count=1,
            preemptible=False,
            custom_startup_script_request=custom_startup,
        ),
        storage=StorageSpec(
            disk_size_gb=100,
            os_image_family="common-cu121",
            os_image_project="deeplearning-platform-release",
        ),
        network=NetworkSpec(network_name="default"),
        project_id="test-project",
    )


def _state(spec: DeploymentSpec | None = None) -> GraphState:
    return GraphState(
        user_prompt="deploy a T4 VM",
        deployment_spec=spec or _spec(),
        stage=FlowStage.IAC,
    )


def _mock_llm() -> MagicMock:
    llm = MagicMock()
    return llm


def _mock_validate_ok() -> MagicMock:
    from vibeops.models.iac import TerraformValidationResult

    return TerraformValidationResult(ok=True)


@pytest.fixture()
def mock_subprocess() -> MagicMock:
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.returncode = 0
    proc.stdout = '{"valid": true, "diagnostics": []}'
    proc.stderr = ""
    return proc


class TestIacNoFragment:
    def _run(self, state: GraphState, llm: MagicMock) -> GraphState:
        from langchain_core.runnables import RunnableConfig

        from vibeops.agents.iac import iac_agent

        config: RunnableConfig = {"configurable": {"llm_client": llm, "gcp_context": None}}

        with patch("vibeops.agents.iac.init"), patch(
            "vibeops.agents.iac.validate", return_value=_mock_validate_ok()
        ), patch(
            "vibeops.agents.iac.check_resource_allowlist",
            return_value=MagicMock(ok=True, violations=[]),
        ), patch(
            "vibeops.cost.infracost.run_infracost", return_value=None
        ):
            return iac_agent(state, config)

    def test_stage_is_awaiting_approval(self) -> None:
        result = self._run(_state(), _mock_llm())
        assert result.stage == FlowStage.AWAITING_APPROVAL

    def test_terraform_files_populated(self) -> None:
        result = self._run(_state(), _mock_llm())
        assert set(result.terraform_files.keys()) == {"main.tf", "variables.tf", "outputs.tf"}
        for content in result.terraform_files.values():
            assert len(content) > 0

    def test_no_llm_calls_when_no_fragment_needed(self) -> None:
        llm = _mock_llm()
        self._run(_state(_spec(custom_startup=None)), llm)
        llm.chat_completion.assert_not_called()

    def test_original_files_stored(self) -> None:
        result = self._run(_state(), _mock_llm())
        assert result.terraform_files_original == result.terraform_files

    def test_chat_history_grows_by_one(self) -> None:
        state = _state()
        result = self._run(state, _mock_llm())
        assert len(result.chat_history) == len(state.chat_history) + 1
        assert result.chat_history[-1]["agent"] == "iac"

    def test_input_state_unmutated(self) -> None:
        state = _state()
        result = self._run(state, _mock_llm())
        assert result is not state
        assert state.stage == FlowStage.IAC

    def test_validation_errors_empty_on_success(self) -> None:
        result = self._run(_state(), _mock_llm())
        assert result.validation_errors == []

    def test_cost_estimate_stale_false_after_generation(self) -> None:
        result = self._run(_state(), _mock_llm())
        assert result.cost_estimate_stale is False
