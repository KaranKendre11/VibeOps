from __future__ import annotations

import json
from unittest.mock import MagicMock, call, patch

import pytest

from vibeops.models.spec import ComputeSpec, DeploymentSpec, GpuType, NetworkSpec, StorageSpec
from vibeops.models.state import FlowStage, GraphState


def _spec(custom_startup: str | None = "install pytorch") -> DeploymentSpec:
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
        user_prompt="deploy with pytorch",
        deployment_spec=spec or _spec(),
        stage=FlowStage.IAC,
    )


def _valid_fragment_json() -> str:
    return json.dumps({"metadata_block": '  metadata = {\n    startup-script = "#!/bin/bash"\n  }'})


def _mock_llm_result(content: str) -> MagicMock:
    result = MagicMock()
    result.content = content
    return result


def _run_with_fragment(state: GraphState, llm: MagicMock) -> GraphState:
    from langchain_core.runnables import RunnableConfig

    from vibeops.agents.iac import iac_agent
    from vibeops.models.iac import TerraformValidationResult

    config: RunnableConfig = {"configurable": {"llm_client": llm, "gcp_context": None}}

    with patch("vibeops.agents.iac.init"), patch(
        "vibeops.agents.iac.validate",
        return_value=TerraformValidationResult(ok=True),
    ), patch(
        "vibeops.agents.iac.check_resource_allowlist",
        return_value=MagicMock(ok=True, violations=[]),
    ), patch(
        "vibeops.cost.infracost.run_infracost", return_value=None
    ):
        return iac_agent(state, config)


class TestIacWithFragment:
    def test_llm_called_once_with_quality_high(self) -> None:
        llm = MagicMock()
        llm.chat_completion.return_value = _mock_llm_result(_valid_fragment_json())
        _run_with_fragment(_state(), llm)
        assert llm.chat_completion.call_count == 1
        _, kwargs = llm.chat_completion.call_args
        assert kwargs.get("quality") == "high"

    def test_stage_is_awaiting_approval(self) -> None:
        llm = MagicMock()
        llm.chat_completion.return_value = _mock_llm_result(_valid_fragment_json())
        result = _run_with_fragment(_state(), llm)
        assert result.stage == FlowStage.AWAITING_APPROVAL

    def test_terraform_files_populated(self) -> None:
        llm = MagicMock()
        llm.chat_completion.return_value = _mock_llm_result(_valid_fragment_json())
        result = _run_with_fragment(_state(), llm)
        assert set(result.terraform_files.keys()) == {"main.tf", "variables.tf", "outputs.tf"}

    def test_no_fragment_no_llm_call(self) -> None:
        llm = MagicMock()
        result = _run_with_fragment(_state(_spec(custom_startup=None)), llm)
        llm.chat_completion.assert_not_called()
        assert result.stage == FlowStage.AWAITING_APPROVAL


class TestIacFragmentRetry:
    def test_retries_on_invalid_hcl(self) -> None:
        """LLM returns invalid JSON first, valid fragment second → one retry, success."""
        llm = MagicMock()
        # First call: invalid (not parseable HCL)
        invalid_fragment = json.dumps({"metadata_block": "INVALID {{ not hcl"})
        # Second call: valid
        valid_fragment = _valid_fragment_json()
        llm.chat_completion.side_effect = [
            _mock_llm_result(invalid_fragment),
            _mock_llm_result(valid_fragment),
        ]
        result = _run_with_fragment(_state(), llm)
        assert llm.chat_completion.call_count == 2
        assert result.stage == FlowStage.AWAITING_APPROVAL
        # All quality="high"
        for c in llm.chat_completion.call_args_list:
            _, kwargs = c
            assert kwargs.get("quality") == "high"


class TestIacFragmentDoubleFail:
    def test_falls_back_to_empty_on_double_failure(self) -> None:
        """LLM returns invalid HCL twice → agent uses empty fragment and does not crash."""
        llm = MagicMock()
        invalid = json.dumps({"metadata_block": "INVALID {{ bad"})
        llm.chat_completion.return_value = _mock_llm_result(invalid)
        result = _run_with_fragment(_state(), llm)
        assert llm.chat_completion.call_count == 2
        # Should still reach AWAITING_APPROVAL (graceful fallback)
        assert result.stage == FlowStage.AWAITING_APPROVAL
        assert result.terraform_files  # files still generated with empty fragment
