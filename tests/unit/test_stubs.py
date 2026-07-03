from __future__ import annotations

from vibeops.agents.architecture import architecture_agent
from vibeops.agents.deployment import deployment_agent
from vibeops.agents.iac import iac_agent
from vibeops.agents.requirement import requirement_agent
from vibeops.models.requirement import RequirementDraft
from vibeops.models.spec import DeploymentSpec
from vibeops.models.state import FlowStage, GraphState


def _base() -> GraphState:
    return GraphState(user_prompt="get me a T4 GPU VM")


class TestRequirementStub:
    """Requirement agent without LLMClient in config uses stub fallback."""

    def test_stage_advances(self) -> None:
        result = requirement_agent(_base())
        assert result.stage == FlowStage.ARCHITECTURE

    def test_requirement_draft_populated(self) -> None:
        result = requirement_agent(_base())
        assert result.requirement_draft is not None
        assert isinstance(result.requirement_draft, RequirementDraft)
        assert result.requirement_draft.gpu_count >= 1
        assert result.requirement_draft.disk_size_gb >= 10

    def test_chat_history_grows_by_one(self) -> None:
        state = _base()
        result = requirement_agent(state)
        assert len(result.chat_history) == len(state.chat_history) + 1
        assert result.chat_history[-1]["agent"] == "requirement"

    def test_input_state_unmutated(self) -> None:
        state = _base()
        result = requirement_agent(state)
        assert result is not state
        assert state.stage == FlowStage.REQUIREMENT


class TestArchitectureStub:
    """Architecture agent without GcpContext in config uses stub fallback."""

    def test_stage_advances(self) -> None:
        state = requirement_agent(_base())
        result = architecture_agent(state)
        assert result.stage == FlowStage.IAC

    def test_deployment_spec_populated(self) -> None:
        state = requirement_agent(_base())
        result = architecture_agent(state)
        assert result.deployment_spec is not None
        assert isinstance(result.deployment_spec, DeploymentSpec)
        assert result.deployment_spec.compute.machine_type
        assert result.deployment_spec.compute.zone

    def test_chat_history_grows_by_one(self) -> None:
        state = requirement_agent(_base())
        result = architecture_agent(state)
        assert len(result.chat_history) == len(state.chat_history) + 1
        assert result.chat_history[-1]["agent"] == "architecture"

    def test_input_state_unmutated(self) -> None:
        state = requirement_agent(_base())
        result = architecture_agent(state)
        assert result is not state
        assert state.stage == FlowStage.ARCHITECTURE


class TestIacStub:
    def _setup(self) -> GraphState:
        return architecture_agent(requirement_agent(_base()))

    def test_stage_advances(self) -> None:
        assert iac_agent(self._setup()).stage == FlowStage.AWAITING_APPROVAL

    def test_terraform_files_populated(self) -> None:
        result = iac_agent(self._setup())
        assert set(result.terraform_files.keys()) == {"main.tf", "variables.tf", "outputs.tf"}
        for content in result.terraform_files.values():
            assert len(content) > 0

    def test_cost_estimate_set(self) -> None:
        result = iac_agent(self._setup())
        assert result.cost_estimate_usd == 0.0

    def test_chat_history_grows_by_one(self) -> None:
        state = self._setup()
        result = iac_agent(state)
        assert len(result.chat_history) == len(state.chat_history) + 1

    def test_input_state_unmutated(self) -> None:
        state = self._setup()
        result = iac_agent(state)
        assert result is not state
        assert state.stage == FlowStage.IAC


class TestDeploymentStub:
    """M4: deployment_agent is now real (terraform plan+apply). Verify M4 outcomes."""

    def _setup(self) -> GraphState:
        import tempfile
        state = iac_agent(architecture_agent(requirement_agent(_base())))
        tmp = tempfile.mkdtemp(prefix="vibeops_test_deploy_")
        return state.model_copy(update={"approved": True, "stage": FlowStage.DEPLOYMENT, "terraform_dir": tmp})

    def test_deployment_succeeds_with_mocked_runner(self) -> None:
        from unittest.mock import patch

        from vibeops.models.deployment import (
            ApplyResult,
            DeploymentOutcome,
            DeploymentPhase,
            PlanResult,
        )

        state = self._setup()
        with (
            patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file=f"{state.terraform_dir}/tfplan")),
            patch("vibeops.agents.deployment.runner.apply", return_value=ApplyResult(full_log="done", resources_created=1)),
            patch("vibeops.agents.deployment.runner.parse_state_resources", return_value=[]),
        ):
            result = deployment_agent(state)

        assert result.deployment_phase == DeploymentPhase.SUCCEEDED
        assert result.deployment_outcome == DeploymentOutcome.SUCCEEDED

    def test_input_state_unmutated(self) -> None:
        from unittest.mock import patch

        from vibeops.models.deployment import ApplyResult, PlanResult

        state = self._setup()
        with (
            patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file=f"{state.terraform_dir}/tfplan")),
            patch("vibeops.agents.deployment.runner.apply", return_value=ApplyResult(full_log="done", resources_created=0)),
            patch("vibeops.agents.deployment.runner.parse_state_resources", return_value=[]),
        ):
            result = deployment_agent(state)

        assert result is not state
