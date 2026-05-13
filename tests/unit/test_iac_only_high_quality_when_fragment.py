from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from vibeops.models.iac import TerraformValidationResult
from vibeops.models.spec import ComputeSpec, DeploymentSpec, GpuType, NetworkSpec, StorageSpec
from vibeops.models.state import FlowStage, GraphState


def _spec(custom_startup: str | None) -> DeploymentSpec:
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


def _state(custom_startup: str | None) -> GraphState:
    return GraphState(
        user_prompt="deploy vm",
        deployment_spec=_spec(custom_startup),
        stage=FlowStage.IAC,
    )


def _run(state: GraphState, llm: MagicMock) -> GraphState:
    from langchain_core.runnables import RunnableConfig

    from vibeops.agents.iac import iac_agent

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


class TestIacOnlyHighQualityWhenFragment:
    def test_fragment_call_uses_quality_high(self) -> None:
        llm = MagicMock()
        valid = json.dumps(
            {"metadata_block": '  metadata = {\n    startup-script = "#!/bin/bash"\n  }'}
        )
        llm.chat_completion.return_value = MagicMock(content=valid)
        _run(_state("install cuda"), llm)
        for c in llm.chat_completion.call_args_list:
            _, kwargs = c
            assert kwargs.get("quality") == "high", (
                f"IaC fragment call must use quality='high', got: {kwargs.get('quality')}"
            )

    def test_no_fragment_means_no_llm_calls(self) -> None:
        llm = MagicMock()
        _run(_state(None), llm)
        llm.chat_completion.assert_not_called()

    def test_no_standard_quality_calls_anywhere(self) -> None:
        """Confirms the IaC agent never uses quality='standard' (or omits it, which defaults to standard)."""
        llm = MagicMock()
        valid = json.dumps(
            {"metadata_block": '  metadata = {\n    startup-script = "#!/bin/bash"\n  }'}
        )
        llm.chat_completion.return_value = MagicMock(content=valid)
        _run(_state("run setup.py"), llm)
        for c in llm.chat_completion.call_args_list:
            _, kwargs = c
            assert kwargs.get("quality") != "standard", (
                "IaC agent must not use quality='standard' — only quality='high' for fragment."
            )
